"""US4: missed-run policy and Trigger State (spec US4; SC-005, SC-006).

A clock jump past several due ticks starts the number of Loop Runs dictated by
the missed-run policy (skip / catch-up-once / coalesce, each <=1 per advance),
and Trigger State reconstructs from the Scheduler Event stream.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.scheduling import Scheduler, VirtualClock, reconstruct_states
from tests.scheduling_helpers import SchedulerEventRecorder, pass_loop_definition

pytestmark = pytest.mark.anyio


async def test_skip_policy_runs_once_and_advances_past_the_jump(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv",
        pass_loop_definition(working_scope=tmp_path),
        interval_seconds=10.0,
        missed_run_policy="skip",
    )

    clock.advance(35.0)  # next_due=10; ticks at 10,20,30 are due => 3 ticks
    outcomes = await scheduler.poll()

    assert len(outcomes) == 1
    state = scheduler.trigger_state("iv")
    assert state.fire_count == 1
    assert state.missed_ticks == 2
    assert state.next_due == 40.0  # advanced past the jump


async def test_catch_up_once_runs_one_make_up(tmp_path: Path) -> None:
    recorder = SchedulerEventRecorder()
    clock = VirtualClock()
    scheduler = Scheduler(clock, on_event=recorder)
    scheduler.register_interval(
        "iv",
        pass_loop_definition(working_scope=tmp_path),
        interval_seconds=10.0,
        missed_run_policy="catch_up_once",
    )

    clock.advance(35.0)
    outcomes = await scheduler.poll()

    assert len(outcomes) == 1
    assert "run_caught_up" in recorder.types
    assert scheduler.trigger_state("iv").missed_ticks == 2


async def test_coalesce_collapses_and_rebases_next_due(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv",
        pass_loop_definition(working_scope=tmp_path),
        interval_seconds=10.0,
        missed_run_policy="coalesce",
    )

    clock.advance(35.0)
    outcomes = await scheduler.poll()

    assert len(outcomes) == 1
    state = scheduler.trigger_state("iv")
    assert state.next_due == 45.0  # now (35) + period (10)
    assert state.missed_ticks == 2


async def test_trigger_state_reconstructs_from_the_event_stream(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )
    for _ in range(2):
        clock.advance(10.0)
        await scheduler.poll()

    rebuilt = reconstruct_states(scheduler.events)["iv"]
    live = scheduler.trigger_state("iv")

    assert rebuilt.fire_count == live.fire_count == 2
    assert rebuilt.next_due == live.next_due
    assert rebuilt.missed_ticks == live.missed_ticks
    assert rebuilt.last_run_ref == live.last_run_ref
