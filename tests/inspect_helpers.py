"""Deterministic, public-safe test helpers for the inspect layer (010).

Scripted Loop Events and a recording replay sink. Runtime-event builders are added
with the run-diagnostics phase (US2).
"""

from __future__ import annotations

from datetime import UTC, datetime

from loopplane.engineering import LoopEvent
from loopplane.events import (
    DiagnosticEvent,
    DiagnosticPayload,
    RunTerminatedEvent,
    RunTerminatedPayload,
    ToolCallStartedEvent,
    ToolCallStartedPayload,
    TurnCompletedEvent,
    TurnCompletedPayload,
)
from loopplane.model import TokenUsage

_AT = datetime(2026, 1, 1, tzinfo=UTC)


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


def tool_call_started(sequence: int, *, session_id: str = "s1") -> ToolCallStartedEvent:
    return ToolCallStartedEvent(
        session_id=session_id,
        sequence=sequence,
        occurred_at=_AT,
        payload=ToolCallStartedPayload(call_id="c", tool_name="t", input={}),
    )


def turn_completed(sequence: int, *, session_id: str = "s1") -> TurnCompletedEvent:
    return TurnCompletedEvent(
        session_id=session_id,
        sequence=sequence,
        occurred_at=_AT,
        payload=TurnCompletedPayload(
            turn_index=0, stop_reason="end", usage=TokenUsage()
        ),
    )


def diagnostic(sequence: int, *, session_id: str = "s1") -> DiagnosticEvent:
    return DiagnosticEvent(
        session_id=session_id,
        sequence=sequence,
        occurred_at=_AT,
        payload=DiagnosticPayload(severity="error", category="x", message="m"),
    )


def run_terminated(
    sequence: int, *, session_id: str = "s1", reason: str = "natural-completion"
) -> RunTerminatedEvent:
    return RunTerminatedEvent(
        session_id=session_id,
        sequence=sequence,
        occurred_at=_AT,
        payload=RunTerminatedPayload(reason=reason, turns_taken=1),  # type: ignore[arg-type]
    )


class RecordingSink:
    """A replay sink that records each event it receives."""

    def __init__(self) -> None:
        self.events: list[object] = []

    async def __call__(self, event: object) -> None:
        self.events.append(event)
