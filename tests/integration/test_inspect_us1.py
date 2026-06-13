"""US1: see what happened in a loop (spec US1; SC-001/002/008)."""

from __future__ import annotations

from loopplane.engineering import reconstruct_state
from loopplane.inspect import loop_diagnostics
from tests.inspect_helpers import loop_event


def _stream() -> list[object]:
    return [
        loop_event("loop_started", sequence=0),
        loop_event("loop_iteration_started", sequence=1, iteration_index=0),
        loop_event(
            "loop_iteration_completed",
            sequence=2,
            iteration_index=0,
            session_id="s1",
            payload={"termination_reason": "done"},
        ),
        loop_event(
            "validation_completed",
            sequence=3,
            payload={"status": "needs_repair", "reason": "fix"},
        ),
        loop_event("repair_requested", sequence=4),
        loop_event("retry_scheduled", sequence=5),
        loop_event("loop_iteration_started", sequence=6, iteration_index=1),
        loop_event(
            "loop_iteration_completed",
            sequence=7,
            iteration_index=1,
            session_id="s2",
            payload={"termination_reason": "done"},
        ),
        loop_event("validation_completed", sequence=8, payload={"status": "pass"}),
        loop_event("evaluation_completed", sequence=9, payload={"label": "good"}),
        loop_event("loop_completed", sequence=10, payload={"stop_reason": "passed"}),
    ]


def test_loop_diagnostics_counts_and_outcomes() -> None:
    diagnostics = loop_diagnostics(_stream())
    assert diagnostics.iterations == 2
    assert diagnostics.runs == 2
    assert diagnostics.retries == 1
    assert diagnostics.repairs == 1
    assert diagnostics.human_reviews == 0
    assert diagnostics.latest_validation_status == "pass"
    assert diagnostics.latest_evaluation_label == "good"
    assert diagnostics.terminal_status == "loop_completed"


def test_loop_diagnostics_matches_reconstruct_state() -> None:
    events = _stream()
    state = reconstruct_state(events)
    diagnostics = loop_diagnostics(events)
    assert diagnostics.runs == len(state.run_refs)
    expected_status = (
        state.latest_validation.status if state.latest_validation is not None else None
    )
    assert diagnostics.latest_validation_status == expected_status


def test_loop_diagnostics_empty_is_empty() -> None:
    diagnostics = loop_diagnostics([])
    assert diagnostics.iterations == 0
    assert diagnostics.runs == 0
    assert diagnostics.terminal_status is None


def test_loop_diagnostics_is_deterministic() -> None:
    events = _stream()
    assert loop_diagnostics(events) == loop_diagnostics(events)


def test_loop_diagnostics_skips_unknown_type() -> None:
    events = [
        loop_event("loop_started", sequence=0),
        loop_event("some_future_event", sequence=1),
        loop_event("loop_completed", sequence=2, payload={"stop_reason": "ok"}),
    ]
    diagnostics = loop_diagnostics(events)
    assert diagnostics.terminal_status == "loop_completed"
