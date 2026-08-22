"""``LoopPlaneHost``: the Host Application Interface (spec FR-001–FR-008).

The single documented seam an application uses to assemble the Phase-1 runtime
from a configuration, start runs, consume the normalized event stream, and drive
the interactive round-trip. It is built entirely on the Phase-1 public surface
and re-implements no runtime internal (FR-001, FR-060).
"""

from __future__ import annotations

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
from loopplane.host.agent_controls import (
    AcceptedRunPosture,
    AgentControlProjection,
    build_agent_control_projection,
    validate_browser_permission_mode,
)
from loopplane.host.assembly import AssembledRuntime, assemble
from loopplane.host.audit import TurnAuditEntry, checkpoint_records_to_audit_entries
from loopplane.host.capabilities import (
    CapabilityOperationResult,
    CapabilitySettingsStatus,
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
from loopplane.host.snapshot import (
    DesktopPortableSnapshotProvider,
    PortableSnapshotProvider,
    PortableSnapshotResult,
    UnavailablePortableSnapshotProvider,
)
from loopplane.loop.history import HistoryEntry
from loopplane.model import ContentBlock, TextBlock

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
        portable_snapshot_provider: PortableSnapshotProvider | None = None,
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
        self._session_contexts: dict[str, SessionContextBinding] = {}
        # Swarm (spec 050; ADR 0003): when this host runs a swarm MEMBER, it carries the
        # SHARED supervisor + the member's id so the member's run uses the same in-run
        # message registry and resolves "self". ``None`` for a top-level host.
        self._swarm_supervisor = swarm_supervisor
        self._swarm_member_id = swarm_member_id
        # 078 T075: default-unavailable portable snapshot; Desktop injects provider.
        self._snapshot_provider: PortableSnapshotProvider = (
            portable_snapshot_provider or UnavailablePortableSnapshotProvider()
        )

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
        permission_mode: str | None = None,
    ) -> RunOutcome:
        """Start a run and return its outcome (FR-003). ``on_event`` receives
        every normalized event in order (FR-004). ``output_schema`` is an optional
        per-run JSON schema for structured output (spec 045; default None =
        unconstrained)."""

        permission_mode = validate_browser_permission_mode(
            self._config, permission_mode
        )
        self._enter_run()
        try:
            await self._assembled.capability_manager.activate_principal(principal_id)
        except BaseException:
            self._active = False
            raise
        controller = self._assembled.controller
        sink = self._assembled.sink
        session_id = controller.create_session(
            working_scope=working_scope or self._working_scope,
            principal_id=principal_id,
            model=self._effective_model(model, principal_id),
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
                        permission_mode=permission_mode,
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
                    permission_mode=permission_mode,
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
        try:
            await self._assembled.capability_manager.activate_principal(principal_id)
        except BaseException:
            self._active = False
            raise
        controller = self._assembled.controller
        sink = self._assembled.sink
        session_id = controller.create_session(
            working_scope=working_scope or self._working_scope,
            principal_id=principal_id,
            model=self._effective_model(model, principal_id),
        )
        controller.attach_reviewer(session_id)
        self._bind(sink, controller, session_id, on_event, on_approval)
        session = Session(controller, session_id, sink, self._config)

        def cleanup() -> None:
            sink.unbind()
            self._active = False

        session._cleanup = cleanup
        try:
            yield session
        finally:
            await session.aclose()

    def list_sessions(self) -> list[SessionSummary]:
        return [
            self._overlay_session_context(summary)
            for summary in self._assembled.controller.list_sessions()
        ]

    async def resume(
        self,
        session_id: str,
        *,
        working_scope: Path | None = None,
    ) -> None:
        summary = next(
            (
                item
                for item in self._assembled.controller.list_sessions()
                if item.session_id == session_id
            ),
            None,
        )
        if summary is not None:
            await self._assembled.capability_manager.activate_principal(
                summary.principal_id
            )
        await self._assembled.controller.resume(session_id, working_scope=working_scope)

    @asynccontextmanager
    async def resume_session(
        self,
        session_id: str,
        on_event: EventSink,
        *,
        on_approval: OnApproval | None = None,
        working_scope: Path | None = None,
        principal_id: str | None = None,
    ) -> AsyncIterator[Session]:
        """Resume a durable session into an interactive ``Session`` handle (078 T022).

        Composes principal activation, controller resume (optional
        ``working_scope``), reviewer attachment, RunSink bind/replay, and the
        existing ``Session`` lifecycle. ``working_scope=None`` preserves
        controller default (``Path.cwd()``).
        """

        self._enter_run()
        try:
            summary = next(
                (
                    item
                    for item in self._assembled.controller.list_sessions()
                    if item.session_id == session_id
                ),
                None,
            )
            if summary is None or (
                principal_id is not None
                and summary.principal_id not in (None, principal_id)
            ):
                raise KeyError(f"unknown session: {session_id}")
            active_principal = (
                principal_id if principal_id is not None else summary.principal_id
            )
            await self._assembled.capability_manager.activate_principal(
                active_principal
            )
            controller = self._assembled.controller
            sink = self._assembled.sink
            await controller.resume(session_id, working_scope=working_scope)
            controller.attach_reviewer(session_id)
            self._bind(sink, controller, session_id, on_event, on_approval)
            session = Session(controller, session_id, sink, self._config)

            def cleanup() -> None:
                sink.unbind()
                self._active = False

            session._cleanup = cleanup
            yield session
        finally:
            if "session" in locals():
                await session.aclose()
            else:
                self._assembled.sink.unbind()
                self._active = False

    async def aclose(self) -> None:
        """Release managed adapters and retained storage authority."""

        first_error: Exception | None = None
        try:
            self._assembled.controller.retry_pending_artifact_deletions()
        except Exception as exc:
            first_error = exc
        try:
            await self._assembled.capability_manager.aclose()
        except Exception as exc:
            if first_error is None:
                first_error = exc
        lease = self._assembled.storage_lease
        if lease is not None and first_error is None:
            try:
                lease.close()
                self._assembled.storage_lease = None
            except Exception as exc:
                first_error = exc
        if first_error is not None:
            raise first_error

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
        await self._assembled.capability_manager.activate_principal(principal_id)
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

    def list_turn_audit(self, session_id: str) -> tuple[TurnAuditEntry, ...]:
        """Read checkpoint-derived metadata-only logical-turn audit rows.

        Audit is deliberately unavailable for non-durable sessions: reconstructing
        it from live history would both violate the durability contract and risk
        exposing content-derived metadata.  Checkpoint-store ``load`` is read-only.
        """

        checkpoint_store = self._assembled.checkpoint_store
        if checkpoint_store is None:
            return ()
        records, _problems = checkpoint_store.load(session_id)
        return checkpoint_records_to_audit_entries(records)

    def export_portable_snapshot(self, destination: Path) -> PortableSnapshotResult:
        """Export a portable profile snapshot (078 T075).

        Default-unavailable unless a Desktop provider was injected.
        """

        return self._snapshot_provider.export_snapshot(Path(destination))

    def validate_portable_snapshot(self, source: Path) -> PortableSnapshotResult:
        """Read-only validation of an inactive staged snapshot (078 T075)."""

        return self._snapshot_provider.validate_snapshot(Path(source))

    def set_portable_snapshot_provider(
        self, provider: PortableSnapshotProvider | None
    ) -> None:
        """Inject or clear the Desktop portable-snapshot provider."""

        self._snapshot_provider = provider or UnavailablePortableSnapshotProvider()

    def enable_desktop_portable_snapshot(self) -> None:
        """Inject the canonical Host-owned Desktop snapshot provider.

        Only Desktop composition calls this opt-in seam.  It preserves all
        non-Desktop defaults and keeps the configured storage root private to
        the Host/provider boundary.
        """

        storage = self._config.storage
        if storage is None or storage.checkpoint_backend != "sqlite":
            self._snapshot_provider = UnavailablePortableSnapshotProvider()
            return
        lease = self._assembled.storage_lease
        self._snapshot_provider = DesktopPortableSnapshotProvider(
            lease.root if lease is not None else storage.root,
            validate_root=lease.validate if lease is not None else None,
        )

    def session_cost(self, session_id: str) -> Decimal | None:
        """A session's accumulated USD, or ``None`` when not budget-tracked (064)."""

        return self._assembled.controller.session_cost(session_id)

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        """A principal's current-month USD from the durable ledger, or ``None`` when
        no ledger is configured (064)."""

        return self._assembled.controller.monthly_spend(principal_id)

    def agent_controls(self, session_id: str) -> AgentControlProjection:
        """Return an ephemeral safe projection for an existing owned session.

        Ownership remains a WebAPI concern. The controller only returns live memory;
        it never rebuilds posture from a checkpoint after a host restart.
        """

        active, settled = self._assembled.controller.agent_control_posture(session_id)
        active_view = (
            AcceptedRunPosture(mode=active[0], state="active", plan_active=active[1])
            if active is not None
            else None
        )
        settled_view = (
            AcceptedRunPosture(mode=settled[0], state="settled", plan_active=False)
            if settled is not None
            else None
        )
        read_upload_available = any(
            descriptor.name == "read_upload"
            for descriptor in self._assembled.gateway.descriptors()
        )
        return build_agent_control_projection(
            self._config,
            session_id=session_id,
            active_run=active_view,
            last_accepted_run=settled_view,
            budget=self._assembled.controller.budget_posture(session_id),
            read_upload_available=read_upload_available,
        )

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

    def capability_settings_status(
        self, *, principal_id: str | None = None
    ) -> CapabilitySettingsStatus:
        return self._assembled.capability_manager.settings_status(principal_id)

    def list_managed_memory(
        self, *, principal_id: str | None = None
    ) -> tuple[ManagedMemoryEntry, ...]:
        return self._assembled.capability_manager.list_memory(principal_id)

    def write_managed_memory(
        self,
        *,
        name: str,
        kind: str,
        description: str,
        content: str,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.write_memory(
            principal_id=principal_id,
            name=name,
            kind=kind,
            description=description,
            content=content,
        )

    def get_managed_memory(
        self, memory_id: str, *, principal_id: str | None = None
    ) -> ManagedMemoryDetail:
        return self._assembled.capability_manager.get_memory(memory_id, principal_id)

    def delete_managed_memory(
        self,
        memory_id: str,
        *,
        confirm: bool,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.delete_memory(
            memory_id,
            principal_id=principal_id,
            confirm=confirm,
        )

    def list_managed_skills(
        self, principal_id: str | None = None
    ) -> tuple[ManagedSkill, ...]:
        return self._assembled.capability_manager.list_skills(principal_id)

    def write_managed_skill(
        self,
        *,
        name: str,
        description: str,
        instructions: str,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.write_skill(
            principal_id=principal_id,
            name=name,
            description=description,
            instructions=instructions,
        )

    def import_managed_skill(
        self,
        definition: Mapping[str, object],
        *,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.import_skill(
            definition,
            principal_id=principal_id,
        )

    def get_managed_skill(
        self, skill_id: str, *, principal_id: str | None = None
    ) -> ManagedSkillDetail:
        return self._assembled.capability_manager.get_skill(skill_id, principal_id)

    def delete_managed_skill(
        self,
        skill_id: str,
        *,
        confirm: bool,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.delete_skill(
            skill_id,
            principal_id=principal_id,
            confirm=confirm,
        )

    def list_managed_mcp(
        self, principal_id: str | None = None
    ) -> tuple[ManagedMcpConfiguration, ...]:
        return self._assembled.capability_manager.list_mcp(principal_id)

    def get_managed_mcp(
        self, mcp_id: str, *, principal_id: str | None = None
    ) -> ManagedMcpConfiguration:
        return self._assembled.capability_manager.get_mcp(mcp_id, principal_id)

    def list_workspace_contexts(
        self, principal_id: str | None = None
    ) -> tuple[WorkspaceContext, ...]:
        return self._assembled.capability_manager.list_contexts(principal_id)

    async def upsert_managed_mcp(
        self,
        *,
        name: str,
        transport: str,
        url: str | None = None,
        command: str | None = None,
        args: Sequence[str] = (),
        principal_id: str | None = None,
        authorization: str | None = None,
    ) -> CapabilityOperationResult:
        return await self._assembled.capability_manager.upsert_mcp(
            name=name,
            transport=transport,
            url=url,
            command=command,
            args=args,
            principal_id=principal_id,
            authorization=authorization,
        )

    async def reconnect_managed_mcp(
        self, mcp_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return await self._assembled.capability_manager.reconnect_mcp(
            mcp_id,
            principal_id=principal_id,
        )

    async def delete_managed_mcp(
        self, mcp_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return await self._assembled.capability_manager.delete_mcp(
            mcp_id,
            principal_id=principal_id,
            confirm=confirm,
        )

    def upsert_workspace_context(
        self,
        *,
        name: str,
        description: str,
        workspace_label: str,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.upsert_context(
            name=name,
            description=description,
            workspace_label=workspace_label,
            principal_id=principal_id,
        )

    def get_workspace_context(
        self, context_id: str, *, principal_id: str | None = None
    ) -> WorkspaceContext:
        return self._assembled.capability_manager.get_context(context_id, principal_id)

    def delete_workspace_context(
        self, context_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.delete_context(
            context_id,
            principal_id=principal_id,
            confirm=confirm,
        )

    async def bind_session_context(
        self, session_id: str, context_id: str, *, principal_id: str | None = None
    ) -> SessionContextBinding:
        context = self.get_workspace_context(context_id, principal_id=principal_id)
        if "bind" not in context.actions:
            raise KeyError(context_id)
        binding = SessionContextBinding(
            session_id=session_id,
            context_id=context.id,
            name=context.name,
            workspace_label=context.workspace_label,
            status=context.status,
        )
        await self._assembled.controller.set_session_context(
            session_id,
            principal_id=principal_id,
            context_id=binding.context_id,
            context_name=binding.name,
            context_workspace_label=binding.workspace_label,
            context_status=binding.status,
        )
        self._session_contexts[session_id] = binding
        return binding

    def list_managed_schedules(
        self, principal_id: str | None = None
    ) -> tuple[ManagedSchedule, ...]:
        return self._assembled.capability_manager.list_schedules(principal_id)

    def upsert_managed_schedule(
        self,
        *,
        name: str,
        description: str,
        trigger: str,
        enabled: bool,
        instruction: str = "",
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.upsert_schedule(
            name=name,
            description=description,
            trigger=trigger,
            instruction=instruction,
            enabled=enabled,
            principal_id=principal_id,
        )

    def get_managed_schedule(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> ManagedSchedule:
        return self._assembled.capability_manager.get_schedule(
            schedule_id, principal_id
        )

    def enable_managed_schedule(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.enable_schedule(
            schedule_id, principal_id=principal_id
        )

    def disable_managed_schedule(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.disable_schedule(
            schedule_id, principal_id=principal_id
        )

    def run_managed_schedule_now(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.run_schedule_now(
            schedule_id, principal_id=principal_id
        )

    def delete_managed_schedule(
        self, schedule_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.delete_schedule(
            schedule_id,
            principal_id=principal_id,
            confirm=confirm,
        )

    def model_default(
        self,
        principal_id: str | None = None,
        *,
        available_models: Mapping[str, str] | None = None,
    ) -> ModelDefault:
        return self._assembled.capability_manager.model_default(
            principal_id,
            available_models=available_models,
        )

    def set_model_default(
        self,
        model_id: str,
        *,
        available_models: Mapping[str, str],
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.set_model_default(
            model_id,
            available_models=available_models,
            principal_id=principal_id,
        )

    def clear_model_default(
        self, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        return self._assembled.capability_manager.clear_model_default(
            principal_id=principal_id
        )

    def _effective_model(
        self, model: str | None, principal_id: str | None
    ) -> str | None:
        if model is not None:
            return model
        default = self._assembled.capability_manager.model_default(principal_id)
        return default.model_id if default.status == "available" else None

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
        self,
        controller: RuntimeController,
        session_id: str,
        sink: RunSink,
        config: RuntimeConfig,
    ) -> None:
        self._controller = controller
        self._session_id = session_id
        self._sink = sink
        self._config = config
        self._outcome: RunOutcome | None = None
        self._cleanup: Callable[[], Awaitable[None] | None] | None = None

    @property
    def session_id(self) -> str:
        return self._session_id

    async def submit(
        self,
        prompt: Prompt,
        output_schema: dict[str, object] | None = None,
        permission_mode: str | None = None,
    ) -> RunOutcome:
        permission_mode = validate_browser_permission_mode(
            self._config, permission_mode
        )
        await self._controller.drive(
            self._session_id,
            _coerce_blocks(prompt),
            output_schema=output_schema,
            permission_mode=permission_mode,
        )
        self._outcome = _build_outcome(self._controller, self._session_id, self._sink)
        return self._outcome

    def cancel(self) -> None:
        self._controller.cancel(self._session_id)
        # Resolve anything the loop is parked on (a pending approval/question)
        # so a cancelled interactive run can never hang on a reviewer (FR-115).
        self._controller.on_reviewer_disconnect(self._session_id)

    async def aclose(self) -> None:
        cleanup = self._cleanup
        if cleanup is None:
            return
        result = cleanup()
        if result is not None:
            await result
        self._cleanup = None

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
