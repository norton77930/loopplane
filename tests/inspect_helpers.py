"""Deterministic, public-safe test helpers for the inspect layer (010).

Scripted Loop Events and a recording replay sink. Runtime-event builders are added
with the run-diagnostics phase (US2).
"""

from __future__ import annotations

from loopplane.engineering import LoopEvent


def loop_event(
    event_type: str,
    *,
    sequence: int,
    loop_id: str = "L",
    loop_definition_id: str = "defL",
    iteration_index: int | None = None,
    session_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> LoopEvent:
    return LoopEvent(
        type=event_type,  # type: ignore[arg-type]
        sequence=sequence,
        loop_id=loop_id,
        loop_definition_id=loop_definition_id,
        iteration_index=iteration_index,
        session_id=session_id,
        payload=payload if payload is not None else {},
    )


class RecordingSink:
    """A replay sink that records each event it receives."""

    def __init__(self) -> None:
        self.events: list[object] = []

    async def __call__(self, event: object) -> None:
        self.events.append(event)
