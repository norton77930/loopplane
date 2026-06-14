"""The sidecar host contract for the studio host (012).

Run the studio over an embedded host through a start/stop lifecycle. An
in-process implementation ships; spawning a real OS process (an out-of-line host)
is a reserved extension point. A command before start / after stop returns an
explicit not-available view rather than raising (FR-040, FR-041).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from loopplane.host import LoopPlaneHost
from loopplane.studio.console import StudioHost
from loopplane.studio.views import ErrorView, RunResultView


@runtime_checkable
class SidecarHost(Protocol):
    """The sidecar lifecycle contract: start / stop and a command surface over a
    hosted studio."""

    @property
    def studio(self) -> StudioHost | None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def run(self, prompt: str) -> RunResultView | ErrorView: ...


class InProcessSidecar:
    """An in-process sidecar that hosts the studio over an embedded host. Real OS
    process spawning is reserved (a real out-of-line host process)."""

    def __init__(self, host: LoopPlaneHost) -> None:
        self._host = host
        self._studio: StudioHost | None = None

    @property
    def studio(self) -> StudioHost | None:
        return self._studio

    async def start(self) -> None:
        if self._studio is None:
            studio = StudioHost(self._host)
            await studio.__aenter__()
            self._studio = studio

    async def stop(self) -> None:
        # Idempotent: stopping a stopped sidecar is a no-op; no run is orphaned
        # (the studio's exit cancels and joins its task group) (FR-041).
        if self._studio is not None:
            studio = self._studio
            self._studio = None
            await studio.__aexit__(None, None, None)

    async def run(self, prompt: str) -> RunResultView | ErrorView:
        """Drive a run through the hosted studio, or a not-available view if the
        sidecar is not started (FR-040, FR-041)."""

        if self._studio is None:
            return ErrorView(kind="not-available", detail="sidecar not started")
        return await self._studio.run(prompt)
