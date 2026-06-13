"""US3: build a trace of a loop and its runs (spec US3; SC-003)."""

from __future__ import annotations

from loopplane.inspect import build_trace
from tests.inspect_helpers import loop_event, tool_call_started, turn_completed


def _loop_events() -> list[object]:
    return [
        loop_event("loop_started", sequence=0),
        loop_event("loop_iteration_started", sequence=1, iteration_index=0),
        loop_event(
            "loop_iteration_completed", sequence=2, iteration_index=0, session_id="s1"
        ),
        loop_event("loop_completed", sequence=3),
    ]


def test_build_trace_nests_loop_iteration_run() -> None:
    runs = {
        "s1": [
            tool_call_started(0, session_id="s1"),
            turn_completed(1, session_id="s1"),
        ]
    }
    trace = build_trace(_loop_events(), runs)
    assert trace.root is not None
    assert trace.root.kind == "loop"
    iteration = trace.root.children[0]
    assert iteration.kind == "iteration"
    assert iteration.identifier == "0"
    run = iteration.children[0]
    assert run.kind == "run"
    assert run.identifier == "s1"
    assert {child.kind for child in run.children} == {"tool_call", "turn"}


def test_build_trace_is_metadata_only() -> None:
    runs = {"s1": [tool_call_started(5, session_id="s1")]}
    trace = build_trace(_loop_events(), runs)
    assert trace.root is not None
    tool_span = trace.root.children[0].children[0].children[0]
    assert set(vars(tool_span)) <= {"kind", "identifier", "sequence", "children"}


def test_build_trace_session_without_run_stream() -> None:
    trace = build_trace(_loop_events(), {})
    assert trace.root is not None
    run = trace.root.children[0].children[0]
    assert run.kind == "run"
    assert run.children == ()


def test_build_trace_empty_is_none() -> None:
    assert build_trace([], {}).root is None


def test_build_trace_is_deterministic() -> None:
    runs = {"s1": [tool_call_started(0, session_id="s1")]}
    assert build_trace(_loop_events(), runs) == build_trace(_loop_events(), runs)
