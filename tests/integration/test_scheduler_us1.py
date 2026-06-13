"""US1: manual trigger registry (spec US1; SC-001, SC-002).

Register a Loop Definition under a trigger id and start it on demand; the
Scheduler starts exactly one Scheduled Loop Run through `run_loop`, records it in
Trigger State, and returns the loop outcome.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.scheduling import Scheduler, SchedulerError, VirtualClock
from tests.scheduling_helpers import (
    SchedulerEventRecorder,
    pass_loop_definition,
    pausing_loop_definition,
)

pytestmark = pytest.mark.anyio


async def test_register_manual_and_start_fires_one_run(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))

    outcome = await scheduler.start("job")

    assert outcome.terminal_event == "loop_completed"
    state = scheduler.trigger_state("job")
    assert state.fire_count == 1
    assert state.last_fired == 0.0  # the Clock time at fire
    assert state.last_run_ref is not None
    assert state.last_run_ref.paused is False


async def test_unknown_trigger_id_raises_and_starts_nothing(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    with pytest.raises(SchedulerError, match="unknown trigger id"):
        await scheduler.start("missing")


async def test_duplicate_registration_is_rejected(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))
    with pytest.raises(SchedulerError, match="already registered"):
        scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))


async def test_paused_run_is_recorded_and_counts_as_one_fire(tmp_path: Path) -> None:
    # A registered loop that pauses for human review records the paused outcome
    # in Trigger State and still counts as exactly one fire (catch-up is
    # tick-based, not outcome-based — spec Edge Case).
    scheduler = Scheduler(VirtualClock())
    scheduler.register_manual("review", pausing_loop_definition(working_scope=tmp_path))

    outcome = await scheduler.start("review")

    assert outcome.paused
    state = scheduler.trigger_state("review")
    assert state.fire_count == 1
    assert state.last_run_ref is not None
    assert state.last_run_ref.paused is True


async def test_run_goes_through_run_loop_to_a_real_agent_run(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))

    outcome = await scheduler.start("job")

    # The fired Loop Run drove a real Agent Run through `run_loop` -> host: its
    # Loop State references the run by session id (SC-002).
    assert len(outcome.state.run_refs) == 1
    assert outcome.state.run_refs[0].termination_reason == "natural-completion"


async def test_scheduler_events_record_registration_and_fire(tmp_path: Path) -> None:
    recorder = SchedulerEventRecorder()
    scheduler = Scheduler(VirtualClock(), on_event=recorder)
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))

    await scheduler.start("job")

    assert "trigger_registered" in recorder.types
    assert "trigger_fired" in recorder.types
    fired = next(e for e in recorder.events if e.type == "trigger_fired")
    assert fired.trigger_id == "job"
    assert fired.payload["terminal_event"] == "loop_completed"
