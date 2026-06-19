"""Unit tests for the exit_plan_mode internal tool (spec 038): it submits a plan
through the existing human round-trip (the broker that ask_user uses); on approve it
clears the per-run plan-mode holder (so a subsequent non-read-only tool is allowed); on
reject or no human it leaves plan mode active and returns a clear normalized outcome.
All deterministic and offline (a scripted InteractionBroker; no real reviewer/model).
"""

from __future__ import annotations

from pathlib import Path

import anyio
import anyio.lowlevel
import pytest

from loopplane.approval import InteractionBroker, PolicyAllow, PolicyDeny
from loopplane.context import PlanModeState, RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.governance import plan_mode_policy
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor
from loopplane.model.content import TextBlock
from loopplane.tools import InternalToolAdapter
from tests.governance_helpers import decide_with_context

pytestmark = pytest.mark.anyio


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    def of_type(self, event_type: str) -> list[RuntimeEvent]:
        return [event for event in self.events if event.type == event_type]


def _broker(sink: _Collector, *, reviewer: bool) -> InteractionBroker:
    emitter = EventEmitter(session_id="s", sequencer=EventSequencer(), sink=sink)
    broker = InteractionBroker(emitter=emitter)
    if reviewer:
        broker.attach_reviewer()
    return broker


def _context(
    tmp_path: Path, broker: InteractionBroker | None, state: PlanModeState | None
) -> RunContext:
    return RunContext(
        session_id="s",
        working_scope=tmp_path,
        interactions=broker,
        plan_mode=state,
    )


def _write_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        name="write_file", description="", input_schema={}, read_only=False
    )


async def _invoke_with_answer(
    adapter: InternalToolAdapter,
    call_input: dict[str, object],
    context: RunContext,
    sink: _Collector,
    broker: InteractionBroker,
    *,
    answer: list[str],
) -> list[AdapterOutput]:
    """Drive exit_plan_mode while concurrently answering its one question (the
    established broker round-trip pattern from tests/contract/test_approval.py)."""

    outputs: list[AdapterOutput] = []

    async def run() -> None:
        async for output in adapter.invoke("exit_plan_mode", call_input, context):
            outputs.append(output)

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(run)
        with anyio.fail_after(5):
            while not sink.of_type("question-asked"):
                await anyio.lowlevel.checkpoint()
        request_id = sink.of_type("question-asked")[0].payload.request_id
        assert broker.answer_question(request_id, answer) is True

    return outputs


# --- US2: approve clears plan mode; subsequent write_file is then allowed -----------


async def test_approve_clears_plan_mode_and_returns_success(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink, reviewer=True)
    state = PlanModeState(active=True)
    context = _context(tmp_path, broker, state)
    adapter = InternalToolAdapter()

    outputs = await _invoke_with_answer(
        adapter, {"plan": "1. do the thing"}, context, sink, broker, answer=["approve"]
    )

    assert state.active is False
    assert all(not isinstance(output, ErrorOutput) for output in outputs)
    assert any(isinstance(output, TextBlock) for output in outputs)


async def test_after_approval_a_write_file_is_allowed(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink, reviewer=True)
    state = PlanModeState(active=True)
    context = _context(tmp_path, broker, state)
    adapter = InternalToolAdapter()

    await _invoke_with_answer(
        adapter, {"plan": "the plan"}, context, sink, broker, answer=["approve"]
    )

    verdict = await decide_with_context(
        plan_mode_policy(),
        ToolCallRequest(call_id="c", tool_name="write_file", input={}),
        _write_descriptor(),
        context,
    )
    assert isinstance(verdict, PolicyAllow)


# --- US3: reject / no human keeps plan mode active ---------------------------------


async def test_reject_keeps_plan_mode_active(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink, reviewer=True)
    state = PlanModeState(active=True)
    context = _context(tmp_path, broker, state)
    adapter = InternalToolAdapter()

    outputs = await _invoke_with_answer(
        adapter, {"plan": "the plan"}, context, sink, broker, answer=["reject"]
    )

    assert state.active is True
    # A clear (non-approval) text outcome, not a crash.
    assert any(isinstance(output, TextBlock) for output in outputs)
    verdict = await decide_with_context(
        plan_mode_policy(),
        ToolCallRequest(call_id="c", tool_name="write_file", input={}),
        _write_descriptor(),
        context,
    )
    assert isinstance(verdict, PolicyDeny)


async def test_no_reviewer_keeps_plan_mode_active_and_errors(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink, reviewer=False)  # no reviewer attached
    state = PlanModeState(active=True)
    context = _context(tmp_path, broker, state)
    adapter = InternalToolAdapter()

    # ask_question returns None immediately when no reviewer is attached, so no
    # concurrent answerer is needed.
    outputs = [
        output
        async for output in adapter.invoke(
            "exit_plan_mode", {"plan": "the plan"}, context
        )
    ]

    assert state.active is True
    assert any(isinstance(output, ErrorOutput) for output in outputs)
    verdict = await decide_with_context(
        plan_mode_policy(),
        ToolCallRequest(call_id="c", tool_name="write_file", input={}),
        _write_descriptor(),
        context,
    )
    assert isinstance(verdict, PolicyDeny)


async def test_no_interactions_broker_errors_without_flipping(tmp_path: Path) -> None:
    state = PlanModeState(active=True)
    context = _context(tmp_path, None, state)  # no broker at all
    adapter = InternalToolAdapter()

    outputs = [
        output
        async for output in adapter.invoke(
            "exit_plan_mode", {"plan": "the plan"}, context
        )
    ]

    assert state.active is True
    assert any(isinstance(output, ErrorOutput) for output in outputs)


async def test_exit_plan_mode_descriptor_is_allowlistable_and_not_read_only() -> None:
    adapter = InternalToolAdapter()
    by_name = {descriptor.name: descriptor for descriptor in adapter.describe()}
    assert "exit_plan_mode" in by_name
    descriptor = by_name["exit_plan_mode"]
    assert descriptor.read_only is False
    assert descriptor.network is False
