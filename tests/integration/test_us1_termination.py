"""US1 acceptance 1.3-1.5: cancellation pre-turn and mid-stream, turn-budget
exhaustion, unknown tool, and no orphaned input on empty turns (FR-003,
FR-004, FR-007). Also covers the minimal Dispatcher round-trip (FR-011).
"""

from __future__ import annotations

import math
from pathlib import Path

import anyio
import pytest

from loopplane.controller.controller import RuntimeController
from loopplane.controller.dispatcher import (
    Cancel,
    ConsumerRequest,
    Dispatcher,
    SubmitInput,
)
from loopplane.events import RuntimeEvent
from loopplane.gateway import ToolGateway
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolResultBlock,
)

from .conftest import ECHO_DESCRIPTOR, EventCollector, HarnessFactory, echo_handler

pytestmark = pytest.mark.anyio


async def test_cancellation_before_the_first_turn(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    controller, session_id = harness(
        [ScriptedTurn(increments=[TextIncrement(text="never streamed")])], collector
    )

    controller.cancel(session_id)
    await controller.drive(session_id, [TextBlock(text="hi")])

    assert collector.types == ["run-terminated"]
    assert collector.events[-1].payload.reason == "cancelled"
    assert collector.events[-1].payload.turns_taken == 0
    assert controller.history_snapshot(session_id) == ()


async def test_cancellation_mid_stream_keeps_partial_output(
    harness: HarnessFactory,
) -> None:
    script = [
        ScriptedTurn(
            increments=[TextIncrement(text=f"chunk-{i}") for i in range(10)],
        )
    ]

    class CancellingCollector(EventCollector):
        controller: RuntimeController
        session_id: str

        async def __call__(self, event: RuntimeEvent) -> None:
            await super().__call__(event)
            if event.type == "assistant-output-increment":
                self.controller.cancel(self.session_id)

    sink = CancellingCollector()
    controller, session_id = harness(script, sink)
    sink.controller = controller
    sink.session_id = session_id

    await controller.drive(session_id, [TextBlock(text="hi")])

    assert sink.types == ["user-input", "assistant-output-increment", "run-terminated"]
    assert sink.events[-1].payload.reason == "cancelled"

    history = controller.history_snapshot(session_id)
    assert [entry.role for entry in history] == ["user", "assistant"]
    assert history[1].blocks == (TextBlock(text="chunk-0"),)


async def test_cancellation_mid_stream_before_any_output_leaves_no_orphaned_input(
    harness: HarnessFactory,
) -> None:
    script = [
        ScriptedTurn(
            increments=[TextIncrement(text="reasoning only never shown")],
        )
    ]

    class CancelOnUserInput(EventCollector):
        controller: RuntimeController
        session_id: str

        async def __call__(self, event: RuntimeEvent) -> None:
            await super().__call__(event)
            if event.type == "user-input":
                self.controller.cancel(self.session_id)

    sink = CancelOnUserInput()
    controller, session_id = harness(script, sink)
    sink.controller = controller
    sink.session_id = session_id

    await controller.drive(session_id, [TextBlock(text="hi")])

    assert sink.types == ["user-input", "run-terminated"]
    assert sink.events[-1].payload.reason == "cancelled"
    assert controller.history_snapshot(session_id) == ()


async def test_zero_turn_budget_leaves_no_orphaned_input(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    controller, session_id = harness(
        [ScriptedTurn(increments=[TextIncrement(text="never")])],
        collector,
        turn_budget=0,
    )

    await controller.drive(session_id, [TextBlock(text="hi")])

    assert collector.types == ["run-terminated"]
    assert collector.events[-1].payload.reason == "turn-budget-exhausted"
    assert collector.events[-1].payload.turns_taken == 0
    assert controller.history_snapshot(session_id) == ()


async def test_turn_budget_exhaustion_when_the_model_keeps_calling_tools(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id=f"call-{i}", tool_name="echo", input={"text": "again"}
                )
            ],
            stop_reason="tool-use",
        )
        for i in range(5)
    ]
    controller, session_id = harness(script, collector, turn_budget=2)

    await controller.drive(session_id, [TextBlock(text="loop forever")])

    assert collector.events[-1].payload.reason == "turn-budget-exhausted"
    assert collector.events[-1].payload.turns_taken == 2
    assert collector.types.count("turn-completed") == 2
    assert collector.types.count("tool-call-completed") == 2


async def test_unknown_tool_yields_error_result_and_the_run_continues(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(call_id="call-1", tool_name="missing-tool", input={})
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="recovered")]),
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="hi")])

    completed = next(e for e in collector.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "failure"
    assert completed.payload.error is not None
    assert completed.payload.error.category == "unknown-tool"
    assert "missing-tool" in completed.payload.error.reason

    assert collector.events[-1].payload.reason == "natural-completion"

    history = controller.history_snapshot(session_id)
    (result_block,) = history[2].blocks
    assert isinstance(result_block, ToolResultBlock)
    assert result_block.outcome == "failure"
    assert result_block.error is not None
    assert result_block.error.category == "unknown-tool"


async def test_dispatcher_round_trip_with_mid_run_cancel(tmp_path: Path) -> None:
    script = [
        ScriptedTurn(
            increments=[TextIncrement(text=f"chunk-{i}") for i in range(50)],
        )
    ]
    model = ScriptedModel(script=script, context_capacity=100_000)
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)

    send_events, receive_events = anyio.create_memory_object_stream[RuntimeEvent](
        math.inf
    )
    send_requests, receive_requests = anyio.create_memory_object_stream[
        ConsumerRequest
    ](math.inf)

    controller = RuntimeController(
        model=model, gateway=gateway, event_sink=send_events.send
    )
    session_id = controller.create_session(working_scope=tmp_path)
    dispatcher = Dispatcher(
        controller=controller, session_id=session_id, inbound=receive_requests
    )

    received: list[RuntimeEvent] = []
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(dispatcher.run)
        await send_requests.send(SubmitInput(blocks=[TextBlock(text="hi")]))
        with anyio.fail_after(5):
            async for event in receive_events:
                received.append(event)
                if event.type == "assistant-output-increment":
                    await send_requests.send(Cancel())
                if event.type == "run-terminated":
                    break
        send_requests.close()

    types = [event.type for event in received]
    assert types[0] == "user-input"
    assert types[-1] == "run-terminated"
    assert received[-1].payload.reason == "cancelled"
    assert types.count("assistant-output-increment") < 50
