"""US1 acceptance 1.2: tool-using run event order and coherent history with
an echo-style tool (FR-005, FR-006).
"""

from __future__ import annotations

import pytest

from loopplane.model import (
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallBlock,
    ToolCallRequest,
    ToolResultBlock,
)

from .conftest import EventCollector, HarnessFactory

pytestmark = pytest.mark.anyio


def _tool_using_script() -> list[ScriptedTurn]:
    return [
        ScriptedTurn(
            increments=[
                TextIncrement(text="Let me echo."),
                ToolCallRequest(
                    call_id="call-1", tool_name="echo", input={"text": "ping"}
                ),
            ],
            stop_reason="tool-use",
            usage=TokenUsage(input_tokens=5, output_tokens=3),
        ),
        ScriptedTurn(
            increments=[TextIncrement(text="Echoed: ping")],
            stop_reason="end-turn",
            usage=TokenUsage(input_tokens=9, output_tokens=4),
        ),
    ]


async def test_tool_run_event_order_between_two_reasoning_turns(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    controller, session_id = harness(_tool_using_script(), collector)

    await controller.drive(session_id, [TextBlock(text="please echo ping")])

    assert collector.types == [
        "user-input",
        "assistant-output-increment",
        "turn-completed",
        "tool-call-started",
        "tool-call-completed",
        "assistant-output-increment",
        "turn-completed",
        "run-terminated",
    ]


async def test_tool_call_event_payloads(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    controller, session_id = harness(_tool_using_script(), collector)

    await controller.drive(session_id, [TextBlock(text="please echo ping")])

    started = next(e for e in collector.events if e.type == "tool-call-started")
    completed = next(e for e in collector.events if e.type == "tool-call-completed")
    assert started.payload.call_id == "call-1"
    assert started.payload.tool_name == "echo"
    assert started.payload.input == {"text": "ping"}
    assert completed.payload.call_id == "call-1"
    assert completed.payload.outcome == "success"
    assert list(completed.payload.outputs) == [TextBlock(text="ping")]
    assert completed.payload.error is None
    assert completed.payload.duration_seconds >= 0

    terminated = collector.events[-1]
    assert terminated.type == "run-terminated"
    assert terminated.payload.reason == "natural-completion"
    assert terminated.payload.turns_taken == 2


async def test_final_history_interleaves_coherently(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    controller, session_id = harness(_tool_using_script(), collector)

    await controller.drive(session_id, [TextBlock(text="please echo ping")])

    history = controller.history_snapshot(session_id)
    assert [entry.role for entry in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    assert history[0].blocks == (TextBlock(text="please echo ping"),)
    assert history[1].blocks == (
        TextBlock(text="Let me echo."),
        ToolCallBlock(call_id="call-1", tool_name="echo", input={"text": "ping"}),
    )
    (result_block,) = history[2].blocks
    assert isinstance(result_block, ToolResultBlock)
    assert result_block.call_id == "call-1"
    assert result_block.outcome == "success"
    assert list(result_block.outputs) == [TextBlock(text="ping")]
    assert history[3].blocks == (TextBlock(text="Echoed: ping"),)
