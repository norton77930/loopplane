"""US4: read a debug timeline (spec US4; SC-007)."""

from __future__ import annotations

from loopplane.inspect import build_timeline
from tests.inspect_helpers import loop_event, tool_call_started


def test_timeline_is_ordered_by_sequence() -> None:
    events = [
        loop_event("loop_started", sequence=5),
        loop_event("loop_completed", sequence=1),
    ]
    timeline = build_timeline(events)
    assert [entry.sequence for entry in timeline.entries] == [1, 5]


def test_timeline_pairs_started_with_completed() -> None:
    events = [
        loop_event("loop_iteration_started", sequence=0, iteration_index=0),
        loop_event("loop_iteration_completed", sequence=1, iteration_index=0),
    ]
    timeline = build_timeline(events)
    started = next(e for e in timeline.entries if e.type == "loop_iteration_started")
    assert started.open is False


def test_timeline_unpaired_start_is_open() -> None:
    events = [loop_event("loop_iteration_started", sequence=0, iteration_index=0)]
    timeline = build_timeline(events)
    assert timeline.entries[0].open is True


def test_timeline_accepts_loop_and_runtime_events() -> None:
    events = [loop_event("loop_started", sequence=0), tool_call_started(1)]
    timeline = build_timeline(events)
    assert len(timeline.entries) == 2
    assert [entry.type for entry in timeline.entries] == [
        "loop_started",
        "tool-call-started",
    ]


def test_timeline_empty_is_empty() -> None:
    assert build_timeline([]).entries == ()


def test_timeline_is_deterministic() -> None:
    events = [
        loop_event("loop_started", sequence=0),
        loop_event("loop_completed", sequence=1),
    ]
    assert build_timeline(events) == build_timeline(events)
