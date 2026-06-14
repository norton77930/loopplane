"""``StudioHost``: the desktop/studio host console core (012).

A local, in-process developer console over an embedded ``LoopPlaneHost``: an
async context manager that owns a task group (which holds interactive sessions
open) and maps console commands to public-safe metadata-only view models. It
drives no runtime internal, executes no tool, and re-emits no live event bus —
its only event path is a discard sink (Constitution V & VI).
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Literal

import anyio
from anyio.abc import TaskGroup

from loopplane.host import LoopPlaneHost
from loopplane.studio.sessions import OnApproval, SessionEntry, run_session
from loopplane.studio.views import ErrorView, RunResultView, SessionSummaryView


async def _discard(event: object) -> None:
    """A run sink that drops events — the studio surfaces outcomes, not the live
    stream, so it names no event type and re-emits nothing (Constitution VI)."""

    return None


class StudioHost:
    """A local console over an embedded host. Enter it as an async context
    manager; it owns the task group that holds interactive sessions open."""

    def __init__(self, host: LoopPlaneHost) -> None:
        self._host = host
        self._stack: AsyncExitStack | None = None
        self._task_group: TaskGroup | None = None
        self._sessions: dict[str, SessionEntry] = {}

    async def __aenter__(self) -> StudioHost:
        self._stack = AsyncExitStack()
        self._task_group = await self._stack.enter_async_context(
            anyio.create_task_group()
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Cancel anything still held (an open session's background task) and join.
        if self._task_group is not None:
            self._task_group.cancel_scope.cancel()
        if self._stack is not None:
            await self._stack.aclose()
        self._task_group = None
        self._stack = None

    async def run(self, prompt: str) -> RunResultView | ErrorView:
        """Drive one run on the embedded host and return its metadata-only view.

        An empty prompt → an ``invalid`` view; a sequential-run conflict → a
        ``conflict`` view (FR-001-FR-003)."""

        if not prompt:
            return ErrorView(kind="invalid", detail="invalid request")
        try:
            outcome = await self._host.run(prompt, _discard)
        except RuntimeError:
            return ErrorView(kind="conflict", detail="a run is already active")
        return RunResultView.from_outcome(outcome)

    async def open_session(
        self, *, on_approval: OnApproval | None = None
    ) -> str | ErrorView:
        """Open an interactive session, held open in the task group; returns its
        public session id, or a conflict view if a run/session is already active
        (FR-010, FR-003)."""

        if self._task_group is None:
            return ErrorView(kind="not-available", detail="not started")
        ready = anyio.Event()
        box: dict[str, str] = {}
        self._task_group.start_soon(
            run_session, self._host, self._sessions, ready, box, _discard, on_approval
        )
        await ready.wait()
        if box.get("error"):
            return ErrorView(kind="conflict", detail="a run is already active")
        return box["sid"]

    def list_sessions(self) -> tuple[SessionSummaryView, ...]:
        """Public-safe summaries of the host's known sessions (FR-010)."""

        return tuple(
            SessionSummaryView.from_summary(summary)
            for summary in self._host.list_sessions()
        )

    def select(self, session_id: str) -> str | ErrorView:
        """Confirm a held session by id; an unknown id → a not-found view
        (FR-011)."""

        if session_id not in self._sessions:
            return ErrorView(kind="not-found", detail="not found")
        return session_id

    async def cancel(self, session_id: str) -> ErrorView | None:
        """Cancel and close a held session (never hangs); an unknown id → a
        not-found view (FR-011, FR-022)."""

        entry = self._sessions.get(session_id)
        if entry is None:
            return ErrorView(kind="not-found", detail="not found")
        entry.session.cancel()
        entry.close.set()
        return None

    async def submit(self, session_id: str, prompt: str) -> RunResultView | ErrorView:
        """Submit input to a held session and return its outcome view; a pending
        approval/question is answered by the session's injected handler or
        out-of-band. An unknown session → a not-found view (FR-020)."""

        entry = self._sessions.get(session_id)
        if entry is None:
            return ErrorView(kind="not-found", detail="not found")
        outcome = await entry.session.submit(prompt)
        return RunResultView.from_outcome(outcome)

    def answer_approval(
        self,
        session_id: str,
        request_id: str,
        *,
        allow: bool,
        scope: Literal["once", "session"] = "once",
        reason: str | None = None,
    ) -> bool | ErrorView:
        """Answer a pending approval out-of-band (false if the request id is
        unknown); an unknown session → a not-found view (FR-021)."""

        entry = self._sessions.get(session_id)
        if entry is None:
            return ErrorView(kind="not-found", detail="not found")
        return entry.session.answer_approval(
            request_id, allow=allow, scope=scope, reason=reason
        )

    def answer_question(
        self, session_id: str, request_id: str, answers: Sequence[str]
    ) -> bool | ErrorView:
        """Answer a pending question out-of-band (false if the request id is
        unknown); an unknown session → a not-found view (FR-021)."""

        entry = self._sessions.get(session_id)
        if entry is None:
            return ErrorView(kind="not-found", detail="not found")
        return entry.session.answer_question(request_id, answers)
