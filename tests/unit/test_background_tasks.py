"""Background task tool tests (spec 048; ADR 0002). Offline + deterministic."""

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
from loopplane.tools.background import (
    BackgroundTasksAdapter,
    BackgroundTaskSupervisor,
)

pytestmark = pytest.mark.anyio


def _completing(text: str = "done"):
    async def run_child(
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: object = None,
    ) -> str:
        del fanout
        return f"{text}:{instruction}"

    return run_child


def _gated(gate: anyio.Event):
    async def run_child(
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: object = None,
    ) -> str:
        del fanout
        await gate.wait()
        return f"done:{instruction}"

    return run_child


async def _raising(
    instruction: str,
    allowed_tools: tuple[str, ...] | None,
    child_depth: int,
    working_scope: Path,
    fanout: object = None,
) -> str:
    del fanout
    raise RuntimeError("boom in the child")


def _ctx(supervisor: BackgroundTaskSupervisor | None, *, depth: int = 0) -> RunContext:
    return RunContext(
        session_id="s",
        working_scope=Path("."),
        subagent_depth=depth,
        background_tasks=supervisor,
    )


async def _invoke(
    adapter: BackgroundTasksAdapter,
    name: str,
    call_input: dict[str, object],
    ctx: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, ctx)]


# --- US1: non-blocking launch ------------------------------------------------


async def test_create_is_nonblocking_then_completes() -> None:
    gate = anyio.Event()
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_gated(gate), max_tasks=3
        )
        task_id = sup.create(
            "x", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert task_id is not None
        await anyio.sleep(0)  # let the task start (now waiting on the gate)
        running = sup.get(task_id)
        assert running is not None and running.status == "running"
        gate.set()  # release; the task group then awaits completion at scope exit
    done = sup.get(task_id)
    assert done is not None
    assert done.status == "completed"
    assert done.result == "done:x"


async def test_completed_result_retrievable_via_output() -> None:
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_completing("R"), max_tasks=3
        )
        adapter = BackgroundTasksAdapter(max_subagent_depth=1)
        (started,) = await _invoke(
            adapter, "task_create", {"instruction": "job"}, _ctx(sup)
        )
        assert isinstance(started, TextBlock)
        task_id = started.text.rsplit(": ", 1)[-1]
    (out,) = await _invoke(adapter, "task_output", {"task_id": task_id}, _ctx(sup))
    assert isinstance(out, TextBlock)
    assert out.text == "R:job"


# --- US2: inspect & control --------------------------------------------------


async def test_list_and_get_report_status() -> None:
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_completing(), max_tasks=3
        )
        tid = sup.create(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert tid is not None
    adapter = BackgroundTasksAdapter(max_subagent_depth=1)
    (listing,) = await _invoke(adapter, "task_list", {}, _ctx(sup))
    assert isinstance(listing, TextBlock)
    assert tid in listing.text and "completed" in listing.text
    (got,) = await _invoke(adapter, "task_get", {"task_id": tid}, _ctx(sup))
    assert isinstance(got, TextBlock)
    assert "completed" in got.text


async def test_stop_cancels_a_running_task() -> None:
    gate = anyio.Event()
    adapter = BackgroundTasksAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_gated(gate), max_tasks=3
        )
        tid = sup.create(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert tid is not None
        await anyio.sleep(0)
        (stopped,) = await _invoke(adapter, "task_stop", {"task_id": tid}, _ctx(sup))
        assert isinstance(stopped, TextBlock)
        assert "stopped" in stopped.text
        gate.set()  # the (cancelled) task unwinds cleanly at scope exit
    task = sup.get(tid)
    assert task is not None and task.status == "stopped"


async def test_unknown_task_id_is_a_clear_error() -> None:
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_completing(), max_tasks=3
        )
        adapter = BackgroundTasksAdapter(max_subagent_depth=1)
        (err,) = await _invoke(adapter, "task_get", {"task_id": "nope"}, _ctx(sup))
        assert isinstance(err, ErrorOutput)
        assert err.category == "validation"


# --- US3: bounded, contained, lifecycle --------------------------------------


async def test_count_cap_denies_extra_tasks() -> None:
    gate = anyio.Event()
    adapter = BackgroundTasksAdapter(max_subagent_depth=2)
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_gated(gate), max_tasks=1
        )
        first = sup.create(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert first is not None
        await anyio.sleep(0)  # first is now running, occupying the only slot
        (denied,) = await _invoke(
            adapter, "task_create", {"instruction": "b"}, _ctx(sup)
        )
        assert isinstance(denied, ErrorOutput)
        assert "cap" in denied.message
        gate.set()


async def test_depth_cap_denies_create() -> None:
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_completing(), max_tasks=3
        )
        adapter = BackgroundTasksAdapter(max_subagent_depth=1)
        # A run already at the depth cap may not launch a (deeper) background task.
        (denied,) = await _invoke(
            adapter, "task_create", {"instruction": "x"}, _ctx(sup, depth=1)
        )
        assert isinstance(denied, ErrorOutput)
        assert denied.category == "policy-denial"


async def test_failing_child_is_contained_as_failed() -> None:
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(task_group=tg, run_child=_raising, max_tasks=3)
        tid = sup.create(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert tid is not None
    task = sup.get(tid)
    assert task is not None
    assert task.status == "failed"
    assert task.result == "background task failed"


async def test_pending_tasks_cancelled_at_scope_exit() -> None:
    gate = anyio.Event()  # never set: the task stays running until cancelled
    async with anyio.create_task_group() as tg:
        sup = BackgroundTaskSupervisor(
            task_group=tg, run_child=_gated(gate), max_tasks=3
        )
        tid = sup.create(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert tid is not None
        await anyio.sleep(0)
        sup.cancel_all()  # cancel pending before the scope exits → no leak / no hang
    task = sup.get(tid)
    assert task is not None and task.status == "stopped"


async def test_adapter_errors_when_not_enabled() -> None:
    adapter = BackgroundTasksAdapter(max_subagent_depth=1)
    (err,) = await _invoke(adapter, "task_create", {"instruction": "x"}, _ctx(None))
    assert isinstance(err, ErrorOutput)
    assert err.category == "validation"


# --- Default-off assembly (byte-identical) -----------------------------------


class _StubModel:
    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        return
        yield  # pragma: no cover - never run; makes this an async generator


async def test_default_off_registers_no_background_tools() -> None:
    assembled = assemble(RuntimeConfig(model=_StubModel()))
    names = {d.name for d in assembled.gateway.descriptors()}
    assert "task_create" not in names


async def test_enabled_registers_the_five_tools() -> None:
    assembled = assemble(
        RuntimeConfig(model=_StubModel(), max_background_tasks=2, max_subagent_depth=1)
    )
    names = {d.name for d in assembled.gateway.descriptors()}
    assert {
        "task_create",
        "task_get",
        "task_list",
        "task_stop",
        "task_output",
    } <= names
