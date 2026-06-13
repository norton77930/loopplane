"""Runnable example: inspect a recorded loop and its run.

Public-safe and credential-free. Scripted Loop and Runtime event streams are turned
into metadata-only inspection structures — loop and run diagnostics, a trace, a
timeline, and a replay — with no run driven and no live-bus re-emission.

Run::

    python examples/inspect_quickstart.py
"""

from __future__ import annotations

from datetime import UTC, datetime

import anyio

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
from loopplane.inspect import (
    build_timeline,
    build_trace,
    loop_diagnostics,
    replay,
    run_diagnostics,
)
from loopplane.model import TokenUsage

_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _loop(event_type: str, sequence: int, **fields: object) -> LoopEvent:
    return LoopEvent(
        type=event_type,  # type: ignore[arg-type]
        sequence=sequence,
        loop_id="demo-loop",
        loop_definition_id="demo-def",
        **fields,  # type: ignore[arg-type]
    )


def _runtime_events() -> list[object]:
    return [
        ToolCallStartedEvent(
            session_id="s1",
            sequence=0,
            occurred_at=_AT,
            payload=ToolCallStartedPayload(call_id="c", tool_name="search", input={}),
        ),
        TurnCompletedEvent(
            session_id="s1",
            sequence=1,
            occurred_at=_AT,
            payload=TurnCompletedPayload(
                turn_index=0, stop_reason="end", usage=TokenUsage()
            ),
        ),
        DiagnosticEvent(
            session_id="s1",
            sequence=2,
            occurred_at=_AT,
            payload=DiagnosticPayload(severity="warning", category="demo", message="m"),
        ),
        RunTerminatedEvent(
            session_id="s1",
            sequence=3,
            occurred_at=_AT,
            payload=RunTerminatedPayload(reason="natural-completion", turns_taken=1),
        ),
    ]


def _print_span(span: object, depth: int) -> None:
    if span is None:
        return
    print(f"  {'  ' * depth}{span.kind}:{span.identifier}")  # type: ignore[attr-defined]
    for child in span.children:  # type: ignore[attr-defined]
        _print_span(child, depth + 1)


async def run_demo() -> None:
    loop_events = [
        _loop("loop_started", 0),
        _loop("loop_iteration_started", 1, iteration_index=0),
        _loop(
            "loop_iteration_completed",
            2,
            iteration_index=0,
            session_id="s1",
            payload={"termination_reason": "done"},
        ),
        _loop("validation_completed", 3, payload={"status": "pass"}),
        _loop("loop_completed", 4, payload={"stop_reason": "passed"}),
    ]
    run_events = _runtime_events()

    print("Loop diagnostics:", loop_diagnostics(loop_events))
    print("Run diagnostics:", run_diagnostics(run_events))

    trace = build_trace(loop_events, {"s1": run_events})
    print("\nTrace:")
    _print_span(trace.root, 0)

    print("\nTimeline:")
    for entry in build_timeline(loop_events).entries:
        marker = " (open)" if entry.open else ""
        print(f"  #{entry.sequence} depth={entry.depth} {entry.type}{marker}")

    delivered: list[str] = []

    async def sink(event: object) -> None:
        delivered.append(event.type)  # type: ignore[attr-defined]

    summary = await replay(run_events, sink)
    print(f"\nReplay: delivered {summary.delivered} events in recorded order")


if __name__ == "__main__":
    anyio.run(run_demo)
