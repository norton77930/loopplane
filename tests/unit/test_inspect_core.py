"""Foundational unit tests for the inspect layer (010): the sequenced-event
protocol and the count helper. Host-free.
"""

from __future__ import annotations

from loopplane.inspect import SequencedEvent
from loopplane.inspect.base import count_by_type
from tests.inspect_helpers import loop_event


def test_loop_event_satisfies_sequenced_event() -> None:
    event = loop_event("loop_started", sequence=0)
    assert isinstance(event, SequencedEvent)
    assert event.type == "loop_started"
    assert event.sequence == 0


def test_count_by_type() -> None:
    events = [loop_event("retry_scheduled", sequence=i) for i in range(3)]
    events.append(loop_event("loop_completed", sequence=3))
    assert count_by_type(events, "retry_scheduled") == 3
    assert count_by_type(events, "loop_completed") == 1
    assert count_by_type(events, "unknown_future_type") == 0
    assert count_by_type(events, "retry_scheduled", "loop_completed") == 4


def test_count_by_type_empty() -> None:
    assert count_by_type([], "retry_scheduled") == 0
