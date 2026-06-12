"""Unit tests for partitioning, snapshot immutability, and terminal reasons
(T019; FR-001, FR-005, FR-006).
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest
from pydantic import ValidationError

from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.loop import AgentLoop, SessionHistory, partition_calls
from loopplane.model import (
    OutputBlock,
    ScriptedFailure,
    ScriptedModel,
    ScriptedOverflow,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)

pytestmark = pytest.mark.anyio


def _descriptor(name: str, *, concurrency_safe: bool) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=f"test tool {name}",
        input_schema={"type": "object"},
        concurrency_safe=concurrency_safe,
    )


def _call(call_id: str, tool_name: str) -> ToolCallRequest:
    return ToolCallRequest(call_id=call_id, tool_name=tool_name, input={})


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]


def _emitter(sink: _Collector) -> EventEmitter:
    return EventEmitter(session_id="session-1", sequencer=EventSequencer(), sink=sink)


def _context(tmp_path: Path, *, turn_budget: int | None = None) -> RunContext:
    return RunContext(
        session_id="session-1", working_scope=tmp_path, turn_budget=turn_budget
    )


# --- partitioning -----------------------------------------------------------


def test_partition_preserves_request_order_within_each_partition() -> None:
    calls = [_call("c1", "safe-a"), _call("c2", "unsafe-x"), _call("c3", "safe-b")]
    safe, sequential = partition_calls(calls, lambda name: name.startswith("safe"))
    assert [c.call_id for c in safe] == ["c1", "c3"]
    assert [c.call_id for c in sequential] == ["c2"]


def test_partition_treats_unknown_tools_as_sequential() -> None:
    gateway = ToolGateway()
    assert gateway.is_concurrency_safe("never-registered") is False


async def test_parallel_batch_overlaps_execution(tmp_path: Path) -> None:
    """Two concurrency-safe calls meet at a rendezvous: only truly parallel
    execution can pass it (a sequential runner would trip the fail_after).
    """
    gateway = ToolGateway()
    first_arrived = anyio.Event()
    second_arrived = anyio.Event()

    async def first_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        first_arrived.set()
        await second_arrived.wait()
        return [TextBlock(text="first")]

    async def second_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        second_arrived.set()
        await first_arrived.wait()
        return [TextBlock(text="second")]

    gateway.register(_descriptor("first", concurrency_safe=True), first_handler)
    gateway.register(_descriptor("second", concurrency_safe=True), second_handler)

    sink = _Collector()
    with anyio.fail_after(5):
        results = await gateway.execute_batch(
            [_call("c1", "first"), _call("c2", "second")],
            parallel=True,
            context=_context(tmp_path),
            emitter=_emitter(sink),
        )

    assert [r.call_id for r in results] == ["c1", "c2"]
    assert sink.types == [
        "tool-call-started",
        "tool-call-started",
        "tool-call-completed",
        "tool-call-completed",
    ]


async def test_sequential_batch_never_overlaps(tmp_path: Path) -> None:
    gateway = ToolGateway()
    in_flight = 0
    max_in_flight = 0

    async def tracking_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await anyio.lowlevel.checkpoint()
        in_flight -= 1
        return [TextBlock(text="done")]

    gateway.register(_descriptor("alpha", concurrency_safe=False), tracking_handler)
    gateway.register(_descriptor("beta", concurrency_safe=False), tracking_handler)

    sink = _Collector()
    results = await gateway.execute_batch(
        [_call("c1", "alpha"), _call("c2", "beta")],
        parallel=False,
        context=_context(tmp_path),
        emitter=_emitter(sink),
    )

    assert max_in_flight == 1
    assert [r.call_id for r in results] == ["c1", "c2"]
    assert sink.types == [
        "tool-call-started",
        "tool-call-completed",
        "tool-call-started",
        "tool-call-completed",
    ]


# --- snapshot immutability ---------------------------------------------------


def test_snapshot_is_point_in_time_and_immutable() -> None:
    history = SessionHistory()
    history.append("user", [TextBlock(text="a")])
    snapshot = history.snapshot()

    history.append("assistant", [TextBlock(text="b")])

    assert len(snapshot) == 1
    assert len(history.snapshot()) == 2
    assert isinstance(snapshot, tuple)
    assert isinstance(snapshot[0].blocks, tuple)
    with pytest.raises(ValidationError):
        snapshot[0].role = "assistant"  # type: ignore[misc]


def test_rollback_drops_only_entries_after_the_mark() -> None:
    history = SessionHistory()
    history.append("user", [TextBlock(text="kept")])
    mark = len(history)
    history.append("user", [TextBlock(text="dropped")])

    history.rollback_to(mark)

    assert [entry.blocks[0] for entry in history.snapshot()] == [TextBlock(text="kept")]
    assert history.has_assistant_entry_since(0) is False


# --- terminal reasons --------------------------------------------------------


async def _run_loop(
    script: list[ScriptEntry],
    tmp_path: Path,
    *,
    turn_budget: int | None = None,
    cancel_first: bool = False,
) -> list[RuntimeEvent]:
    sink = _Collector()
    history = SessionHistory()
    loop = AgentLoop(
        model=ScriptedModel(script=script, context_capacity=1000),
        gateway=ToolGateway(),
        emitter=_emitter(sink),
        history=history,
    )
    context = _context(tmp_path, turn_budget=turn_budget)
    if cancel_first:
        context.cancellation.set()
    await loop.run([TextBlock(text="go")], context)
    return sink.events


@pytest.mark.parametrize(
    ("script", "turn_budget", "cancel_first", "expected_reason"),
    [
        (
            [ScriptedTurn(increments=[TextIncrement(text="hi")])],
            None,
            False,
            "natural-completion",
        ),
        (
            [ScriptedTurn(increments=[TextIncrement(text="hi")])],
            0,
            False,
            "turn-budget-exhausted",
        ),
        (
            [ScriptedTurn(increments=[TextIncrement(text="hi")])],
            None,
            True,
            "cancelled",
        ),
        (
            [ScriptedFailure(error=RuntimeError("boom"))],
            None,
            False,
            "unrecoverable-error",
        ),
        ([ScriptedOverflow()], None, False, "unrecoverable-error"),
    ],
    ids=["natural", "budget", "cancelled", "model-failure", "context-overflow"],
)
async def test_every_run_ends_with_exactly_one_terminal_event(
    tmp_path: Path,
    script: list[ScriptEntry],
    turn_budget: int | None,
    cancel_first: bool,
    expected_reason: str,
) -> None:
    events = await _run_loop(
        script, tmp_path, turn_budget=turn_budget, cancel_first=cancel_first
    )

    terminals = [event for event in events if event.type == "run-terminated"]
    assert len(terminals) == 1
    assert events[-1].type == "run-terminated"
    assert terminals[0].payload.reason == expected_reason
