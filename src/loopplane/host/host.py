"""``LoopPlaneHost``: the Host Application Interface (spec FR-001–FR-008).

The single documented seam an application uses to assemble the Phase-1 runtime
from a configuration, start runs, consume the normalized event stream, and drive
the interactive round-trip. It is built entirely on the Phase-1 public surface
and re-implements no runtime internal (FR-001, FR-060).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anyio

from loopplane.checkpoint.base import SessionSummary
from loopplane.controller.controller import RuntimeController
from loopplane.events.emitter import EventSink
from loopplane.events.envelope import ApprovalRequestedPayload
from loopplane.host.assembly import AssembledRuntime, assemble
from loopplane.host.capabilities import (
    CapabilityOperationResult,
    ManagedMcpConfiguration,
    ManagedMemoryDetail,
    ManagedMemoryEntry,
    ManagedSchedule,
    ManagedSkill,
    ManagedSkillDetail,
    ModelDefault,
    SessionContextBinding,
    WorkspaceContext,
)
from loopplane.host.config import RuntimeConfig
from loopplane.host.inspect import (
    McpServerInfo,
    MemoryEntryInfo,
    SkillInfo,
    ToolInfo,
    mcp_view,
    memory_view,
    skills_view,
    tools_view,
)
from loopplane.host.sink import RunSink
from loopplane.loop.history import HistoryEntry
from loopplane.memory import MemoryEntry
from loopplane.model import ContentBlock, TextBlock
from loopplane.skills.loader import LoadedSkill, load_skills
from loopplane.skills.models import Skill

if TYPE_CHECKING:
    from loopplane.context import SwarmSupervisor

Prompt = str | Sequence[ContentBlock]


@dataclass(frozen=True)
class ApprovalDecision:
    """A host's answer to an ``ask`` approval request (FR-014)."""

    allow: bool
    scope: Literal["once", "session"] = "once"
    reason: str | None = None


OnApproval = Callable[[ApprovalRequestedPayload], Awaitable[ApprovalDecision]]


@dataclass(frozen=True)
class RunOutcome:
    """What a run returns to the host (FR-003): the terminal reason and a
    point-in-time history snapshot, plus run metadata."""

    session_id: str
    termination_reason: str
    turns_taken: int
    history: tuple[HistoryEntry, ...]
    consumer_failures: tuple[str, ...] = field(default=())


def _coerce_blocks(prompt: Prompt) -> list[ContentBlock]:
    if isinstance(prompt, str):
        return [TextBlock(text=prompt)]
    return list(prompt)


def _build_outcome(
    controller: RuntimeController, session_id: str, sink: RunSink
) -> RunOutcome:
    """Snapshot the run's outcome while the sink is still bound, so a retained
    handle can never later read another run's fields."""
    return RunOutcome(
        session_id=session_id,
        termination_reason=sink.terminal_reason or "unknown",
        turns_taken=sink.turns_taken,
        history=controller.history_snapshot(session_id),
        consumer_failures=tuple(sink.consumer_failures),
    )


class LoopPlaneHost:
    """Assemble once, run many times. One configured host drives independent
    sequential runs/sessions with no cross-run state leakage (FR-006)."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        working_scope: Path | None = None,
        subagent_depth: int = 0,
        swarm_supervisor: SwarmSupervisor | None = None,
        swarm_member_id: str | None = None,
    ) -> None:
        # Assembly validates the config and fails fast before any run (FR-005).
        # ``subagent_depth`` (spec 043) is this host's recursion depth; 0 for a
        # top-level host, parent + 1 for a child host built to run a spawned subagent.
        self._assembled: AssembledRuntime = assemble(
            config, subagent_depth=subagent_depth
        )
        self._config = config
        self._working_scope = working_scope or Path.cwd()
        self._active = False
        self._managed_mcp: dict[str, ManagedMcpConfiguration] = {}
        self._workspace_contexts: dict[str, WorkspaceContext] = {}
        self._session_contexts: dict[str, SessionContextBinding] = {}
        # Swarm (spec 050; ADR 0003): when this host runs a swarm MEMBER, it carries the
        # SHARED supervisor + the member's id so the member's run uses the same in-run
        # message registry and resolves "self". ``None`` for a top-level host.
        self._swarm_supervisor = swarm_supervisor
        self._swarm_member_id = swarm_member_id

    @property
    def skill_problems(self) -> tuple[str, ...]:
        return self._assembled.skill_problems

    async def run(
        self,
        prompt: Prompt,
        on_event: EventSink,
        *,
        on_approval: OnApproval | None = None,
        working_scope: Path | None = None,
        principal_id: str | None = None,
        output_schema: dict[str, object] | None = None,
        model: str | None = None,
    ) -> RunOutcome:
        """Start a run and return its outcome (FR-003). ``on_event`` receives
        every normalized event in order (FR-004). ``output_schema`` is an optional
        per-run JSON schema for structured output (spec 045; default None =
        unconstrained)."""

        self._enter_run()
        controller = self._assembled.controller
        sink = self._assembled.sink
        session_id = controller.create_session(
            working_scope=working_scope or self._working_scope,
            principal_id=principal_id,
            model=model,
        )
        self._bind(sink, controller, session_id, on_event, on_approval)
        # Worktree isolation (spec 051): a per-session manager from the working scope
        # (no task group — synchronous git ops); cleaned up in the finally below.
        # ``None`` when worktrees are disabled.
        worktree_manager = controller.make_worktree_manager(session_id)
        try:
            if (
                controller.max_background_tasks >= 1
                or controller.max_schedules >= 1
                or controller.max_swarm_members >= 1
            ):
                # Background tasks (048) + schedules (049) + swarm (050): own a task
                # group so the tools can launch child runs; cancel pending work at end
                # (an interval timer / running member would otherwise block exit).
                async with anyio.create_task_group() as task_group:
                    supervisor = controller.make_background_supervisor(task_group)
                    schedule_supervisor = controller.make_schedule_supervisor(
                        task_group
                    )
                    # A MEMBER child host carries the SHARED supervisor (it runs as that
                    # member); a top-level run builds its own. Cancel only what we own.
                    swarm_supervisor: SwarmSupervisor | None
                    if self._swarm_supervisor is not None:
                        swarm_supervisor = self._swarm_supervisor
                        own_swarm = False
                    else:
                        swarm_supervisor = controller.make_swarm_supervisor(task_group)
                        own_swarm = True
                    await controller.drive(
                        session_id,
                        _coerce_blocks(prompt),
                        output_schema=output_schema,
                        background_supervisor=supervisor,
                        schedule_supervisor=schedule_supervisor,
                        swarm_supervisor=swarm_supervisor,
                        swarm_member_id=self._swarm_member_id,
                        worktree_manager=worktree_manager,
                    )
                    if supervisor is not None:
                        supervisor.cancel_all()
                    if schedule_supervisor is not None:
                        schedule_supervisor.cancel_all()
                    if own_swarm and swarm_supervisor is not None:
                        swarm_supervisor.cancel_all()
            else:
                await controller.drive(
                    session_id,
                    _coerce_blocks(prompt),
                    output_schema=output_schema,
                    worktree_manager=worktree_manager,
                )
            outcome = _build_outcome(controller, session_id, sink)
        finally:
            if worktree_manager is not None:
                await worktree_manager.cleanup()
            sink.unbind()
            self._active = False
        return outcome

    @asynccontextmanager
    async def session(
        self,
        on_event: EventSink,
        *,
        on_approval: OnApproval | None = None,
        working_scope: Path | None = None,
        principal_id: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[Session]:
        """Open an interactive round-trip: submit input, answer approvals and
        questions, and cancel — over the Phase-1 controller (US3)."""

        self._enter_run()
        controller = self._assembled.controller
        sink = self._assembled.sink
        session_id = controller.create_session(
            working_scope=working_scope or self._working_scope,
            principal_id=principal_id,
            model=model,
        )
        controller.attach_reviewer(session_id)
        self._bind(sink, controller, session_id, on_event, on_approval)
        try:
            yield Session(controller, session_id, sink)
        finally:
            sink.unbind()
            self._active = False

    def list_sessions(self) -> list[SessionSummary]:
        return [
            self._overlay_session_context(summary)
            for summary in self._assembled.controller.list_sessions()
        ]

    async def resume(self, session_id: str) -> None:
        await self._assembled.controller.resume(session_id)

    async def set_session_title(self, session_id: str, title: str) -> None:
        """Persist a new title for a session (030)."""
        await self._assembled.controller.set_session_title(session_id, title)

    async def set_session_starred(self, session_id: str, starred: bool) -> None:
        """Persist a session's starred flag."""
        await self._assembled.controller.set_session_starred(session_id, starred)

    async def fork_session(
        self,
        source_session_id: str,
        *,
        principal_id: str | None,
        source_sequence: int,
        title: str | None = None,
        model: str | None = None,
    ) -> str:
        """Create a new owned fork summary from an existing session point."""
        return await self._assembled.controller.fork_session(
            source_session_id,
            principal_id=principal_id,
            source_sequence=source_sequence,
            title=title,
            model=model,
        )

    def search_sessions(
        self, query: str, principal_id: str | None
    ) -> list[SessionSummary]:
        """Search sessions visible to the supplied principal."""
        return self._assembled.controller.search_sessions(query, principal_id)

    def bulk_delete_sessions(
        self, session_ids: Sequence[str], *, principal_id: str | None
    ) -> list[str]:
        """Delete owned sessions from a caller-supplied set of ids."""
        return self._assembled.controller.bulk_delete_sessions(
            session_ids, principal_id=principal_id
        )

    def delete_session(self, session_id: str) -> None:
        """Delete a session and its durable records (030)."""
        self._assembled.controller.delete_session(session_id)

    def history_snapshot(self, session_id: str) -> tuple[HistoryEntry, ...]:
        """A point-in-time history snapshot for a session (FR-003)."""

        return self._assembled.controller.history_snapshot(session_id)

    def session_cost(self, session_id: str) -> Decimal | None:
        """A session's accumulated USD, or ``None`` when not budget-tracked (064)."""

        return self._assembled.controller.session_cost(session_id)

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        """A principal's current-month USD from the durable ledger, or ``None`` when
        no ledger is configured (064)."""

        return self._assembled.controller.monthly_spend(principal_id)

    def compact_session(self, session_id: str) -> bool:
        """Compact a session's history via the existing compaction seam (065
        ``/compact``); returns whether anything was compacted."""

        return self._assembled.controller.compact_session(session_id)

    def retrieve_artifact(self, session_id: str, reference: str) -> str | None:
        """Full content of an offloaded tool result by its stable reference;
        ``None`` when no artifact backend is configured or the reference is
        unknown (FR-042, reuses the Phase-1 artifact guarantee)."""

        store = self._assembled.artifact_store
        if store is None:
            return None
        return store.retrieve(session_id, reference)

    # --- Read-only inspection (027): metadata-only, executes no tool ---------

    def inspect_skills(self) -> tuple[SkillInfo, ...]:
        """Loaded skills as safe metadata (load problems are ``skill_problems``)."""
        return skills_view(self._assembled.skills)

    def inspect_tools(self) -> tuple[ToolInfo, ...]:
        """Registered tool descriptors as safe metadata — reads, never invokes."""
        return tools_view(self._assembled.gateway.descriptors())

    def inspect_mcp(self) -> tuple[McpServerInfo, ...]:
        """Connected MCP servers + their tools, derived from descriptor source."""
        return mcp_view(self._assembled.gateway.descriptors())

    def inspect_memory(self, query: str | None = None) -> tuple[MemoryEntryInfo, ...]:
        """Memory entries (source + snippet); ``query`` filters when given."""
        store = self._assembled.memory_store
        if store is None:
            return ()
        return memory_view(store.list_entries(), query)

    # --- 075: capability management foundation ------------------------------

    def list_managed_memory(self) -> tuple[ManagedMemoryEntry, ...]:
        return tuple(
            ManagedMemoryEntry(
                id=info.name,
                name=info.name,
                kind=info.type,
                description=info.description,
                snippet=info.snippet,
            )
            for info in self.inspect_memory()
        )

    def write_managed_memory(
        self, *, name: str, kind: str, description: str, content: str
    ) -> CapabilityOperationResult:
        store = self._assembled.memory_store
        if store is None:
            return CapabilityOperationResult(
                ok=False,
                resource_id=None,
                status="unavailable",
                message="memory management unavailable",
            )
        entry = MemoryEntry(
            type=kind.strip(), name=name.strip(), description=description, body=content
        )
        store.write(entry)
        return CapabilityOperationResult(
            ok=True,
            resource_id=entry.name,
            status="available",
            message="memory saved",
        )

    def get_managed_memory(self, memory_id: str) -> ManagedMemoryDetail:
        store = self._assembled.memory_store
        if store is None:
            raise KeyError(memory_id)
        entry = store.get(memory_id)
        if entry is None:
            raise KeyError(memory_id)
        return ManagedMemoryDetail(
            id=entry.name,
            name=entry.name,
            kind=entry.type,
            description=entry.description,
            snippet=entry.body[:160],
            content=entry.body,
        )

    def delete_managed_memory(
        self, memory_id: str, *, confirm: bool
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=memory_id,
                status="invalid",
                message="confirmation required",
            )
        store = self._assembled.memory_store
        if store is None or not store.delete(memory_id):
            return CapabilityOperationResult(
                ok=False,
                resource_id=memory_id,
                status="unavailable",
                message="memory entry not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=memory_id,
            status="deleted",
            message="memory deleted",
        )

    def list_managed_skills(self) -> tuple[ManagedSkill, ...]:
        loaded, _problems = self._load_managed_skills()
        return tuple(
            ManagedSkill(
                id=name,
                name=name,
                description=loaded_skill.skill.description,
                source=loaded_skill.source,
            )
            for name, loaded_skill in sorted(loaded.items())
        )

    def write_managed_skill(
        self, *, name: str, description: str, instructions: str
    ) -> CapabilityOperationResult:
        skill = Skill(
            name=name.strip(),
            description=description,
            instructions=instructions,
        )
        self._write_managed_skill(skill)
        return CapabilityOperationResult(
            ok=True,
            resource_id=skill.name,
            status="available",
            message="skill saved",
        )

    def import_managed_skill(
        self, definition: Mapping[str, object]
    ) -> CapabilityOperationResult:
        skill = Skill.model_validate(definition)
        self._write_managed_skill(skill)
        return CapabilityOperationResult(
            ok=True,
            resource_id=skill.name,
            status="available",
            message="skill imported",
        )

    def get_managed_skill(self, skill_id: str) -> ManagedSkillDetail:
        loaded, _problems = self._load_managed_skills()
        loaded_skill = loaded.get(skill_id)
        if loaded_skill is None:
            raise KeyError(skill_id)
        skill = loaded_skill.skill
        return ManagedSkillDetail(
            id=skill.name,
            name=skill.name,
            description=skill.description,
            source=loaded_skill.source,
            instructions=skill.instructions,
        )

    def delete_managed_skill(
        self, skill_id: str, *, confirm: bool
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=skill_id,
                status="invalid",
                message="confirmation required",
            )
        path = self._managed_skill_path(skill_id)
        if path is None or not path.exists():
            return CapabilityOperationResult(
                ok=False,
                resource_id=skill_id,
                status="unavailable",
                message="skill not found",
            )
        path.unlink()
        return CapabilityOperationResult(
            ok=True,
            resource_id=skill_id,
            status="deleted",
            message="skill deleted",
        )

    def list_managed_mcp(
        self, principal_id: str | None = None
    ) -> tuple[ManagedMcpConfiguration, ...]:
        inspected = {
            info.name: ManagedMcpConfiguration(
                id=info.name,
                name=info.name,
                status="connected" if info.tools else "unavailable",
                tool_count=len(info.tools),
                tools=info.tools,
            )
            for info in self.inspect_mcp()
        }
        inspected.update(
            (mcp_id, config)
            for mcp_id, config in self._managed_mcp.items()
            if self._visible_to(config.owner_id, principal_id)
        )
        return tuple(config for _id, config in sorted(inspected.items()))

    def list_workspace_contexts(
        self, principal_id: str | None = None
    ) -> tuple[WorkspaceContext, ...]:
        return tuple(
            context
            for _id, context in sorted(self._workspace_contexts.items())
            if self._visible_to(context.owner_id, principal_id)
        )

    def upsert_managed_mcp(
        self,
        *,
        name: str,
        transport: str,
        url: str | None = None,
        command: str | None = None,
        args: Sequence[str] = (),
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        del url, command, args
        mcp_id = name.strip()
        if not mcp_id or transport not in {"http", "sse", "stdio", "websocket"}:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id or None,
                status="invalid",
                message="mcp configuration invalid",
            )
        self._managed_mcp[mcp_id] = ManagedMcpConfiguration(
            id=mcp_id,
            name=mcp_id,
            status="disconnected",
            tool_count=0,
            owner_id=principal_id,
        )
        return CapabilityOperationResult(
            ok=True,
            resource_id=mcp_id,
            status="available",
            message="mcp configuration saved",
        )

    def reconnect_managed_mcp(
        self, mcp_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        config = self._managed_mcp.get(mcp_id)
        if config is None or not self._visible_to(config.owner_id, principal_id):
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="unavailable",
                message="mcp configuration not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=mcp_id,
            status=config.status,
            message="mcp reconnect requested",
        )

    def delete_managed_mcp(
        self, mcp_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="invalid",
                message="confirmation required",
            )
        config = self._managed_mcp.get(mcp_id)
        if config is None or not self._visible_to(config.owner_id, principal_id):
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="unavailable",
                message="mcp configuration not found",
            )
        del self._managed_mcp[mcp_id]
        return CapabilityOperationResult(
            ok=True,
            resource_id=mcp_id,
            status="deleted",
            message="mcp configuration deleted",
        )

    def upsert_workspace_context(
        self,
        *,
        name: str,
        description: str,
        workspace_label: str,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        context_id = name.strip()
        label = workspace_label.strip()
        if not context_id or not label:
            return CapabilityOperationResult(
                ok=False,
                resource_id=context_id or None,
                status="invalid",
                message="workspace context invalid",
            )
        self._workspace_contexts[context_id] = WorkspaceContext(
            id=context_id,
            name=context_id,
            description=description,
            workspace_label=label,
            owner_id=principal_id,
        )
        return CapabilityOperationResult(
            ok=True,
            resource_id=context_id,
            status="available",
            message="workspace context saved",
        )

    def get_workspace_context(
        self, context_id: str, *, principal_id: str | None = None
    ) -> WorkspaceContext:
        context = self._workspace_contexts.get(context_id)
        if context is None or not self._visible_to(context.owner_id, principal_id):
            raise KeyError(context_id)
        return context

    def delete_workspace_context(
        self, context_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=context_id,
                status="invalid",
                message="confirmation required",
            )
        context = self._workspace_contexts.get(context_id)
        if context is None or not self._visible_to(context.owner_id, principal_id):
            return CapabilityOperationResult(
                ok=False,
                resource_id=context_id,
                status="unavailable",
                message="workspace context not found",
            )
        del self._workspace_contexts[context_id]
        return CapabilityOperationResult(
            ok=True,
            resource_id=context_id,
            status="deleted",
            message="workspace context deleted",
        )

    async def bind_session_context(
        self, session_id: str, context_id: str, *, principal_id: str | None = None
    ) -> SessionContextBinding:
        context = self.get_workspace_context(context_id, principal_id=principal_id)
        summary = next(
            (
                item
                for item in self._assembled.controller.list_sessions()
                if item.session_id == session_id
            ),
            None,
        )
        if summary is None:
            live = self._assembled.controller._sessions.get(session_id)
            if live is None or live.principal_id != principal_id:
                raise KeyError(session_id)
            if self._assembled.checkpoint_store is not None:
                await self._assembled.checkpoint_store.create_session_metadata(
                    session_id,
                    created_at=live.created_at,
                    label=live.label,
                    principal_id=live.principal_id,
                    model=live.model,
                )
        elif summary.principal_id != principal_id:
            raise KeyError(session_id)
        binding = SessionContextBinding(
            session_id=session_id,
            context_id=context.id,
            name=context.name,
            workspace_label=context.workspace_label,
            status=context.status,
        )
        if self._assembled.checkpoint_store is not None:
            await self._assembled.checkpoint_store.update_session_metadata(
                session_id,
                context_id=binding.context_id,
                context_name=binding.name,
                context_workspace_label=binding.workspace_label,
                context_status=binding.status,
            )
        self._session_contexts[session_id] = binding
        return binding

    def list_managed_schedules(self) -> tuple[ManagedSchedule, ...]:
        return ()

    def model_default(self) -> ModelDefault:
        return ModelDefault(model_id=None, label=None, status="fallback")

    @staticmethod
    def _visible_to(owner_id: str | None, principal_id: str | None) -> bool:
        return owner_id is None or owner_id == principal_id

    def _overlay_session_context(self, summary: SessionSummary) -> SessionSummary:
        binding = self._session_contexts.get(summary.session_id)
        if binding is None:
            return summary
        return replace(
            summary,
            context_id=binding.context_id,
            context_name=binding.name,
            context_workspace_label=binding.workspace_label,
            context_status=binding.status,
        )

    def _load_managed_skills(self) -> tuple[dict[str, LoadedSkill], list[str]]:
        if self._config.skills is None:
            return {}, []
        return load_skills(self._config.skills.sources)

    def _write_managed_skill(self, skill: Skill) -> None:
        source = self._managed_skill_source()
        if source is None:
            raise RuntimeError("skill management unavailable")
        source.mkdir(parents=True, exist_ok=True)
        path = self._managed_skill_path(skill.name)
        if path is None:
            raise RuntimeError("skill management unavailable")
        path.write_text(skill.model_dump_json(), encoding="utf-8")

    def _managed_skill_source(self) -> Path | None:
        if self._config.skills is None or not self._config.skills.sources:
            return None
        return self._config.skills.sources[-1]

    def _managed_skill_path(self, name: str) -> Path | None:
        source = self._managed_skill_source()
        if source is None:
            return None
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        return source / f"{safe}-{suffix}.json"

    def _enter_run(self) -> None:
        if self._active:
            raise RuntimeError(
                "a run is already active on this host; runs are sequential"
            )
        self._active = True

    def _bind(
        self,
        sink: RunSink,
        controller: RuntimeController,
        session_id: str,
        on_event: EventSink,
        on_approval: OnApproval | None,
    ) -> None:
        if on_approval is None:
            sink.bind(on_event)
            return
        controller.attach_reviewer(session_id)

        async def relay(payload: ApprovalRequestedPayload) -> None:
            # A failing approval handler must neither crash nor hang the run:
            # deny the call and let the run continue (FR-014 / FR-007 posture).
            try:
                decision = await on_approval(payload)
            except Exception:
                controller.resolve_approval(
                    session_id,
                    payload.request_id,
                    decision="deny",
                    scope="once",
                    reason="approval handler raised",
                )
                return
            controller.resolve_approval(
                session_id,
                payload.request_id,
                decision="allow" if decision.allow else "deny",
                scope=decision.scope,
                reason=decision.reason,
            )

        sink.bind(on_event, approval_relay=relay)


class Session:
    """A live interactive session handle (US3)."""

    def __init__(
        self, controller: RuntimeController, session_id: str, sink: RunSink
    ) -> None:
        self._controller = controller
        self._session_id = session_id
        self._sink = sink
        self._outcome: RunOutcome | None = None

    @property
    def session_id(self) -> str:
        return self._session_id

    async def submit(
        self, prompt: Prompt, output_schema: dict[str, object] | None = None
    ) -> RunOutcome:
        await self._controller.drive(
            self._session_id, _coerce_blocks(prompt), output_schema=output_schema
        )
        self._outcome = _build_outcome(self._controller, self._session_id, self._sink)
        return self._outcome

    def cancel(self) -> None:
        self._controller.cancel(self._session_id)
        # Resolve anything the loop is parked on (a pending approval/question)
        # so a cancelled interactive run can never hang on a reviewer (FR-115).
        self._controller.on_reviewer_disconnect(self._session_id)

    def answer_approval(
        self,
        request_id: str,
        *,
        allow: bool,
        scope: Literal["once", "session"] = "once",
        reason: str | None = None,
    ) -> bool:
        return self._controller.resolve_approval(
            self._session_id,
            request_id,
            decision="allow" if allow else "deny",
            scope=scope,
            reason=reason,
        )

    def answer_question(self, request_id: str, answers: Sequence[str]) -> bool:
        return self._controller.answer_question(self._session_id, request_id, answers)

    def outcome(self) -> RunOutcome:
        if self._outcome is None:
            raise RuntimeError("no run has completed in this session yet")
        return self._outcome


def build_host(
    config: RuntimeConfig, *, working_scope: Path | None = None
) -> LoopPlaneHost:
    """Factory alias for :class:`LoopPlaneHost` — the Reference Runner entry
    point (FR-024)."""

    return LoopPlaneHost(config, working_scope=working_scope)
