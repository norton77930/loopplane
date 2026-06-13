"""US5: scheduler lifecycle and honest edges (spec US5; SC-007).

Start/stop the Scheduler, pause/resume a trigger, and drain it; serialize the
Loop Runs it starts (one in flight at a time); fire same-tick triggers in
deterministic registration order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.scheduling import Scheduler, SchedulerError, VirtualClock
from tests.scheduling_helpers import SchedulerEventRecorder, pass_loop_definition

pytestmark = pytest.mark.anyio


async def test_paused_trigger_fires_nothing_until_resumed(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )
    scheduler.pause("iv")

    clock.advance(20.0)
    assert await scheduler.poll() == []
    assert scheduler.trigger_state("iv").fire_count == 0

    scheduler.resume("iv")
    assert len(await scheduler.poll()) == 1


async def test_same_tick_triggers_fire_in_registration_order(tmp_path: Path) -> None:
    recorder = SchedulerEventRecorder()
    clock = VirtualClock()
    scheduler = Scheduler(clock, on_event=recorder)
    scheduler.register_interval(
        "a", pass_loop_definition("a", working_scope=tmp_path), interval_seconds=10.0
    )
    scheduler.register_interval(
        "b", pass_loop_definition("b", working_scope=tmp_path), interval_seconds=10.0
    )

    clock.advance(10.0)
    outcomes = await scheduler.poll()

    assert len(outcomes) == 2
    fired = [e.trigger_id for e in recorder.events if e.type == "trigger_fired"]
    assert fired == ["a", "b"]  # deterministic registration order


async def test_in_flight_guard_serializes_runs(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))
    # Simulate a Scheduled Loop Run already in flight: a concurrent start must be
    # rejected, so two runs are never in flight at once (FR-072, SC-007).
    scheduler._in_flight = True  # noqa: SLF001 - white-box serialization probe
    with pytest.raises(SchedulerError, match="already in flight"):
        await scheduler.start("job")


async def test_drain_stops_starting_new_runs(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )
    clock.advance(10.0)
    assert len(await scheduler.poll()) == 1

    await scheduler.drain()

    clock.advance(10.0)
    assert await scheduler.poll() == []  # no new run after drain


async def test_stopped_scheduler_fires_nothing_and_keeps_next_due(
    tmp_path: Path,
) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )
    scheduler.stop()

    clock.advance(20.0)
    assert await scheduler.poll() == []
    assert scheduler.trigger_state("iv").next_due == 10.0  # unchanged
