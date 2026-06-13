"""US2: interval trigger on a virtual clock (spec US2; SC-003, SC-008).

An interval trigger fires once per elapsed period as the virtual clock advances,
deterministically, with no real sleeping.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.scheduling import Scheduler, VirtualClock
from tests.scheduling_helpers import pass_loop_definition

pytestmark = pytest.mark.anyio


async def test_interval_fires_once_per_elapsed_period(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )

    fires = 0
    for _ in range(3):
        clock.advance(10.0)
        fires += len(await scheduler.poll())

    assert fires == 3
    assert scheduler.trigger_state("iv").fire_count == 3


async def test_not_due_before_the_period(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )

    clock.advance(5.0)
    assert await scheduler.poll() == []
    assert scheduler.trigger_state("iv").fire_count == 0


async def test_next_due_advances_by_one_period(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
    )
    assert scheduler.trigger_state("iv").next_due == 10.0

    clock.advance(10.0)
    await scheduler.poll()

    assert scheduler.trigger_state("iv").next_due == 20.0
    assert scheduler.trigger_state("iv").fire_count == 1


async def test_two_identical_schedulers_fire_identically(tmp_path: Path) -> None:
    async def run() -> tuple[list[int], list[str]]:
        clock = VirtualClock()
        scheduler = Scheduler(clock)
        scheduler.register_interval(
            "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
        )
        counts: list[int] = []
        for _ in range(3):
            clock.advance(10.0)
            counts.append(len(await scheduler.poll()))
        return counts, [event.type for event in scheduler.events]

    first = await run()
    second = await run()
    assert first == second
    assert first[0] == [1, 1, 1]


async def test_start_immediately_fires_at_t0(tmp_path: Path) -> None:
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "iv",
        pass_loop_definition(working_scope=tmp_path),
        interval_seconds=10.0,
        start_immediately=True,
    )

    assert len(await scheduler.poll()) == 1  # fires at t0
    clock.advance(10.0)
    assert len(await scheduler.poll()) == 1  # then every period
    assert scheduler.trigger_state("iv").fire_count == 2
