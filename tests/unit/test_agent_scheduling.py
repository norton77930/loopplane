"""Agent scheduling tool tests (spec 049). Offline + deterministic (a fake Sleeper
the test advances — no real sleeping)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.host.assembly import assemble
from loopplane.host.config import RuntimeConfig
from loopplane.model.boundary import ModelIncrement, ModelRequest
from loopplane.model.content import TextBlock
from loopplane.tools.scheduling import ScheduleSupervisor, SchedulingToolsAdapter

pytestmark = pytest.mark.anyio


class ManualSleeper:
    """A controllable sleeper: each ``sleep`` parks until the test calls ``advance``."""

    def __init__(self) -> None:
        self._waiters: list[anyio.Event] = []

    async def sleep(self, seconds: float) -> None:
        event = anyio.Event()
        self._waiters.append(event)
        await event.wait()

    def advance(self) -> int:
        """Release every currently-parked sleep (one tick each); return how many."""
        waiters, self._waiters = self._waiters, []
        for event in waiters:
            event.set()
        return len(waiters)


async def _settle() -> None:
    """Yield enough checkpoints for a released timer to fire and re-park."""
    for _ in range(10):
        await anyio.sleep(0)


def _completing(text: str = "done"):
    async def run_child(
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> str:
        return f"{text}:{instruction}"

    return run_child


async def _raising(
    instruction: str,
    allowed_tools: tuple[str, ...] | None,
    child_depth: int,
    working_scope: Path,
) -> str:
    raise RuntimeError("boom in the scheduled child")


def _ctx(supervisor: ScheduleSupervisor | None, *, depth: int = 0) -> RunContext:
    return RunContext(
        session_id="s",
        working_scope=Path("."),
        subagent_depth=depth,
        schedules=supervisor,
    )


async def _invoke(
    adapter: SchedulingToolsAdapter,
    name: str,
    call_input: dict[str, object],
    ctx: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, ctx)]


# --- US1: schedule deferred / recurring work ---------------------------------


async def test_interval_fires_each_tick() -> None:
    sleeper = ManualSleeper()
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        sid = sup.create(
            "x",
            delay_seconds=None,
            interval_seconds=5,
            allowed_tools=None,
            child_depth=1,
            working_scope=Path("."),
        )
        assert sid is not None
        await _settle()  # timer started, now parked on the first sleep
        first = sup.get(sid)
        assert first is not None and first.status == "active" and first.occurrences == 0
        sleeper.advance()
        await _settle()
        assert sup.get(sid).occurrences == 1  # type: ignore[union-attr]
        sleeper.advance()
        await _settle()
        assert sup.get(sid).occurrences == 2  # type: ignore[union-attr]
        sup.cancel_all()  # stop the infinite interval before the scope exits
    final = sup.get(sid)
    assert final is not None and final.status == "cancelled"


async def test_delay_fires_once_then_completed() -> None:
    sleeper = ManualSleeper()
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing("R"), max_schedules=3, sleeper=sleeper
        )
        sid = sup.create(
            "job",
            delay_seconds=5,
            interval_seconds=None,
            allowed_tools=None,
            child_depth=1,
            working_scope=Path("."),
        )
        await _settle()
        sleeper.advance()
        await _settle()
    done = sup.get(sid)
    assert done is not None
    assert done.status == "completed" and done.occurrences == 1
    assert done.last_result == "R:job"


async def test_adapter_create_returns_id_nonblocking() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        (started,) = await _invoke(
            adapter,
            "schedule_create",
            {"instruction": "job", "interval_seconds": 5},
            _ctx(sup),
        )
        assert isinstance(started, TextBlock)
        assert "schedule started" in started.text
        sup.cancel_all()


# --- US2: inspect & cancel ---------------------------------------------------


async def test_get_and_list_report_metadata() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        sid = sup.create(
            "a",
            delay_seconds=None,
            interval_seconds=5,
            allowed_tools=None,
            child_depth=1,
            working_scope=Path("."),
        )
        assert sid is not None
        (listing,) = await _invoke(adapter, "schedule_list", {}, _ctx(sup))
        assert isinstance(listing, TextBlock)
        assert sid in listing.text and "interval" in listing.text
        (got,) = await _invoke(adapter, "schedule_get", {"schedule_id": sid}, _ctx(sup))
        assert isinstance(got, TextBlock) and "active" in got.text
        sup.cancel_all()


async def test_cancel_stops_further_firing() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        sid = sup.create(
            "a",
            delay_seconds=None,
            interval_seconds=5,
            allowed_tools=None,
            child_depth=1,
            working_scope=Path("."),
        )
        assert sid is not None
        await _settle()
        (cancelled,) = await _invoke(
            adapter, "schedule_cancel", {"schedule_id": sid}, _ctx(sup)
        )
        assert isinstance(cancelled, TextBlock) and "cancelled" in cancelled.text
    schedule = sup.get(sid)
    assert schedule is not None and schedule.status == "cancelled"


async def test_unknown_schedule_id_is_a_clear_error() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        (err,) = await _invoke(
            adapter, "schedule_get", {"schedule_id": "nope"}, _ctx(sup)
        )
        assert isinstance(err, ErrorOutput) and err.category == "validation"


# --- US3: bounded, contained, lifecycle --------------------------------------


async def test_count_cap_denies_extra_schedules() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=2)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=1, sleeper=sleeper
        )
        first = sup.create(
            "a",
            delay_seconds=None,
            interval_seconds=5,
            allowed_tools=None,
            child_depth=1,
            working_scope=Path("."),
        )
        assert first is not None
        (denied,) = await _invoke(
            adapter,
            "schedule_create",
            {"instruction": "b", "interval_seconds": 5},
            _ctx(sup),
        )
        assert isinstance(denied, ErrorOutput) and "cap" in denied.message
        sup.cancel_all()


async def test_depth_cap_denies_create() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        (denied,) = await _invoke(
            adapter,
            "schedule_create",
            {"instruction": "x", "interval_seconds": 5},
            _ctx(sup, depth=1),
        )
        assert isinstance(denied, ErrorOutput) and denied.category == "policy-denial"


async def test_bad_cadence_is_denied() -> None:
    sleeper = ManualSleeper()
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
        )
        (neither,) = await _invoke(
            adapter, "schedule_create", {"instruction": "x"}, _ctx(sup)
        )
        (both,) = await _invoke(
            adapter,
            "schedule_create",
            {"instruction": "x", "delay_seconds": 5, "interval_seconds": 5},
            _ctx(sup),
        )
        (zero,) = await _invoke(
            adapter,
            "schedule_create",
            {"instruction": "x", "delay_seconds": 0},
            _ctx(sup),
        )
        for err in (neither, both, zero):
            assert isinstance(err, ErrorOutput) and err.category == "validation"


async def test_failing_occurrence_is_contained() -> None:
    sleeper = ManualSleeper()
    async with anyio.create_task_group() as tg:
        sup = ScheduleSupervisor(
            task_group=tg, run_child=_raising, max_schedules=3, sleeper=sleeper
        )
        sid = sup.create(
            "a",
            delay_seconds=5,
            interval_seconds=None,
            allowed_tools=None,
            child_depth=1,
            working_scope=Path("."),
        )
        await _settle()
        sleeper.advance()
        await _settle()
    schedule = sup.get(sid)
    assert schedule is not None
    assert schedule.occurrences == 1
    assert schedule.last_result == "scheduled task failed"
    assert schedule.status == "completed"


async def test_active_interval_cancelled_at_scope_exit() -> None:
    sleeper = ManualSleeper()
    with anyio.fail_after(2):  # without cancel_all an infinite interval would hang here
        async with anyio.create_task_group() as tg:
            sup = ScheduleSupervisor(
                task_group=tg, run_child=_completing(), max_schedules=3, sleeper=sleeper
            )
            sid = sup.create(
                "a",
                delay_seconds=None,
                interval_seconds=5,
                allowed_tools=None,
                child_depth=1,
                working_scope=Path("."),
            )
            assert sid is not None
            await _settle()
            sup.cancel_all()
    schedule = sup.get(sid)
    assert schedule is not None and schedule.status == "cancelled"


async def test_adapter_errors_when_not_enabled() -> None:
    adapter = SchedulingToolsAdapter(max_subagent_depth=1)
    (err,) = await _invoke(
        adapter,
        "schedule_create",
        {"instruction": "x", "interval_seconds": 5},
        _ctx(None),
    )
    assert isinstance(err, ErrorOutput) and err.category == "validation"


# --- Default-off assembly (byte-identical) -----------------------------------


class _StubModel:
    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        return
        yield  # pragma: no cover - never run; makes this an async generator


async def test_default_off_registers_no_scheduling_tools() -> None:
    assembled = assemble(RuntimeConfig(model=_StubModel()))
    names = {d.name for d in assembled.gateway.descriptors()}
    assert "schedule_create" not in names


async def test_enabled_registers_the_four_tools() -> None:
    assembled = assemble(
        RuntimeConfig(model=_StubModel(), max_schedules=2, max_subagent_depth=1)
    )
    names = {d.name for d in assembled.gateway.descriptors()}
    assert {
        "schedule_create",
        "schedule_get",
        "schedule_list",
        "schedule_cancel",
    } <= names
