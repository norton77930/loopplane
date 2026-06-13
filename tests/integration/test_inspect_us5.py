"""US5: replay a recorded stream (spec US5; SC-009)."""

from __future__ import annotations

import pytest

from loopplane.inspect import replay
from tests.inspect_helpers import RecordingSink, loop_event, tool_call_started

pytestmark = pytest.mark.anyio


async def test_replay_delivers_every_event_in_recorded_order() -> None:
    events = [
        loop_event("loop_started", sequence=0),
        tool_call_started(1),
        loop_event("loop_completed", sequence=2),
    ]
    sink = RecordingSink()
    summary = await replay(events, sink)
    assert summary.delivered == 3
    assert summary.complete is True
    assert sink.events == events


async def test_replay_empty_stream() -> None:
    sink = RecordingSink()
    summary = await replay([], sink)
    assert summary.delivered == 0
    assert summary.complete is True
    assert sink.events == []
