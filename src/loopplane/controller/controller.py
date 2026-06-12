"""The Runtime Controller: session lifecycle — create, drive, terminate —
with in-memory state (contracts/run-lifecycle.md; FR-010).

Attach/detach/resume/list arrive with durability in a later phase; the
Controller is already the only owner of session state and event emission.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import anyio

from loopplane.context import RunContext
from loopplane.events.emitter import EventEmitter, EventSink
from loopplane.events.sequencer import EventSequencer
from loopplane.gateway.gateway import ToolGateway
from loopplane.loop.history import HistoryEntry, SessionHistory
from loopplane.loop.loop import AgentLoop
from loopplane.model.boundary import ModelBoundary
from loopplane.model.content import ContentBlock

SessionState = Literal["created", "active", "suspended", "terminated"]


@dataclass
class _Session:
    session_id: str
    working_scope: Path
    label: str | None
    created_at: datetime
    last_active_at: datetime
    state: SessionState
    turn_budget: int | None
    history: SessionHistory
    emitter: EventEmitter
    loop: AgentLoop
    approval_memory: dict[str, Literal["allow", "deny"]]
    cancellation: anyio.Event
    driving: bool = False


class RuntimeController:
    def __init__(
        self, *, model: ModelBoundary, gateway: ToolGateway, event_sink: EventSink
    ) -> None:
        self._model = model
        self._gateway = gateway
        self._event_sink = event_sink
        self._sessions: dict[str, _Session] = {}

    def create_session(
        self,
        *,
        working_scope: Path,
        label: str | None = None,
        turn_budget: int | None = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        history = SessionHistory()
        emitter = EventEmitter(
            session_id=session_id, sequencer=EventSequencer(), sink=self._event_sink
        )
        now = datetime.now(UTC)
        self._sessions[session_id] = _Session(
            session_id=session_id,
            working_scope=working_scope,
            label=label,
            created_at=now,
            last_active_at=now,
            state="created",
            turn_budget=turn_budget,
            history=history,
            emitter=emitter,
            loop=AgentLoop(
                model=self._model,
                gateway=self._gateway,
                emitter=emitter,
                history=history,
            ),
            approval_memory={},
            cancellation=anyio.Event(),
        )
        return session_id

    async def drive(
        self, session_id: str, input_blocks: Sequence[ContentBlock]
    ) -> None:
        """Run one complete turn cycle; ends with exactly one run-terminated
        event (FR-001).
        """
        session = self._require(session_id)
        if session.state == "terminated":
            raise RuntimeError(f"session is terminated: {session_id}")
        if session.driving:
            raise RuntimeError(f"a run is already active for session: {session_id}")
        session.driving = True
        session.state = "active"
        context = RunContext(
            session_id=session_id,
            working_scope=session.working_scope,
            cancellation=session.cancellation,
            turn_budget=session.turn_budget,
            session_approval_memory=session.approval_memory,
        )
        try:
            await session.loop.run(input_blocks, context)
        finally:
            session.driving = False
            session.last_active_at = datetime.now(UTC)
            # The signal is one-shot; arm a fresh one for the next run.
            session.cancellation = anyio.Event()

    def cancel(self, session_id: str) -> None:
        """Request cancellation: takes effect pre-turn and mid-stream and
        never raises to the caller (FR-003).
        """
        self._require(session_id).cancellation.set()

    def history_snapshot(self, session_id: str) -> tuple[HistoryEntry, ...]:
        """A point-in-time history snapshot that cannot mutate internal
        state (FR-006).
        """
        return self._require(session_id).history.snapshot()

    def terminate(self, session_id: str) -> None:
        session = self._require(session_id)
        session.cancellation.set()
        session.state = "terminated"

    async def emit_diagnostic(
        self,
        session_id: str,
        severity: Literal["info", "warning", "error"],
        category: str,
        message: str,
    ) -> None:
        await self._require(session_id).emitter.diagnostic(severity, category, message)

    def _require(self, session_id: str) -> _Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        return session
