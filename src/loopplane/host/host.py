"""``LoopPlaneHost``: the Host Application Interface (spec FR-001–FR-008).

The single documented seam an application uses to assemble the Phase-1 runtime
from a configuration, start runs, consume the normalized event stream, and drive
the interactive round-trip. It is built entirely on the Phase-1 public surface
and re-implements no runtime internal (FR-001, FR-060).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from loopplane.checkpoint.base import SessionSummary
from loopplane.controller.controller import RuntimeController
from loopplane.events.emitter import EventSink
from loopplane.events.envelope import ApprovalRequestedPayload
from loopplane.host.assembly import AssembledRuntime, assemble
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
from loopplane.model import ContentBlock, TextBlock

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
        self, config: RuntimeConfig, *, working_scope: Path | None = None
    ) -> None:
        # Assembly validates the config and fails fast before any run (FR-005).
        self._assembled: AssembledRuntime = assemble(config)
        self._config = config
        self._working_scope = working_scope or Path.cwd()
        self._active = False

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
    ) -> RunOutcome:
        """Start a run and return its outcome (FR-003). ``on_event`` receives
        every normalized event in order (FR-004)."""

        self._enter_run()
        controller = self._assembled.controller
        sink = self._assembled.sink
        session_id = controller.create_session(
            working_scope=working_scope or self._working_scope,
            principal_id=principal_id,
        )
        self._bind(sink, controller, session_id, on_event, on_approval)
        try:
            await controller.drive(session_id, _coerce_blocks(prompt))
            outcome = _build_outcome(controller, session_id, sink)
        finally:
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
    ) -> AsyncIterator[Session]:
        """Open an interactive round-trip: submit input, answer approvals and
        questions, and cancel — over the Phase-1 controller (US3)."""

        self._enter_run()
        controller = self._assembled.controller
        sink = self._assembled.sink
        session_id = controller.create_session(
            working_scope=working_scope or self._working_scope,
            principal_id=principal_id,
        )
        controller.attach_reviewer(session_id)
        self._bind(sink, controller, session_id, on_event, on_approval)
        try:
            yield Session(controller, session_id, sink)
        finally:
            sink.unbind()
            self._active = False

    def list_sessions(self) -> list[SessionSummary]:
        return self._assembled.controller.list_sessions()

    async def resume(self, session_id: str) -> None:
        await self._assembled.controller.resume(session_id)

    def history_snapshot(self, session_id: str) -> tuple[HistoryEntry, ...]:
        """A point-in-time history snapshot for a session (FR-003)."""

        return self._assembled.controller.history_snapshot(session_id)

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

    async def submit(self, prompt: Prompt) -> RunOutcome:
        await self._controller.drive(self._session_id, _coerce_blocks(prompt))
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
