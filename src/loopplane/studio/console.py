"""``StudioHost``: the desktop/studio host console core (012).

A local, in-process developer console over an embedded ``LoopPlaneHost``: an
async context manager that owns a task group (which holds interactive sessions
open) and maps console commands to public-safe metadata-only view models. It
drives no runtime internal, executes no tool, and re-emits no live event bus —
its only event path is a discard sink (Constitution V & VI).
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from types import TracebackType

import anyio
from anyio.abc import TaskGroup

from loopplane.host import LoopPlaneHost
from loopplane.studio.views import ErrorView, RunResultView


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
