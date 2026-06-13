"""US3: condition trigger from a host predicate (spec US3; SC-004).

A condition trigger evaluates a host predicate on each poll and fires a Loop Run
when satisfied, in edge or level mode; a raising predicate is a non-fatal
diagnostic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.scheduling import Scheduler, VirtualClock
from tests.scheduling_helpers import (
    SchedulerEventRecorder,
    pass_loop_definition,
    raising_predicate,
    scripted_predicate,
)

pytestmark = pytest.mark.anyio


async def test_false_predicate_starts_no_run(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_condition(
        "c",
        pass_loop_definition(working_scope=tmp_path),
        predicate=scripted_predicate(False),
    )

    assert await scheduler.poll() == []
    assert scheduler.trigger_state("c").fire_count == 0


async def test_rising_edge_fires_exactly_once(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_condition(
        "c",
        pass_loop_definition(working_scope=tmp_path),
        predicate=scripted_predicate(False, True, True),
        mode="edge",
    )

    total = 0
    for _ in range(3):
        total += len(await scheduler.poll())

    assert total == 1  # only on the false->true edge, not on the plateau
    assert scheduler.trigger_state("c").fire_count == 1


async def test_level_mode_fires_on_every_satisfied_poll(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_condition(
        "c",
        pass_loop_definition(working_scope=tmp_path),
        predicate=scripted_predicate(True, True),
        mode="level",
    )

    total = 0
    for _ in range(2):
        total += len(await scheduler.poll())

    assert total == 2
    assert scheduler.trigger_state("c").fire_count == 2


async def test_raising_predicate_is_a_non_fatal_diagnostic(tmp_path: Path) -> None:
    recorder = SchedulerEventRecorder()
    scheduler = Scheduler(VirtualClock(), on_event=recorder)
    scheduler.register_condition(
        "c", pass_loop_definition(working_scope=tmp_path), predicate=raising_predicate
    )

    outcomes = await scheduler.poll()

    assert outcomes == []  # no spurious run
    assert "condition_error" in recorder.types
    assert scheduler.trigger_state("c").fire_count == 0
    # The scheduler continues: a later satisfied poll still works.
    scheduler.register_condition(
        "c2",
        pass_loop_definition(working_scope=tmp_path),
        predicate=scripted_predicate(True),
        mode="level",
    )
    assert len(await scheduler.poll()) == 1
