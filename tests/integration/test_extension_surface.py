"""The extension surface (FR-120–FR-122; SC-009): a future-layer stub
consumer attaches and produces a per-run summary using only the public
extension surface, with zero references to Agent Loop internals.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.events import RuntimeEvent
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
)
from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway

from .conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
sys.path.insert(0, str(EXAMPLES_DIR))

from run_summary_consumer import RunSummaryConsumer  # noqa: E402

pytestmark = pytest.mark.anyio


async def test_consumer_summarizes_runs_from_the_event_stream_alone(
    tmp_path: Path,
) -> None:
    consumer = RunSummaryConsumer()
    collector = EventCollector()

    async def tee(event: RuntimeEvent) -> None:
        await collector(event)
        await consumer(event)

    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    controller = RuntimeController(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[
                        TextIncrement(text="echoing"),
                        ToolCallRequest(
                            call_id="c1", tool_name="echo", input={"text": "hi"}
                        ),
                        ToolCallRequest(
                            call_id="c2", tool_name="missing-tool", input={}
                        ),
                    ],
                    stop_reason="tool-use",
                    usage=TokenUsage(input_tokens=10, output_tokens=4),
                ),
                ScriptedTurn(
                    increments=[TextIncrement(text="done")],
                    usage=TokenUsage(input_tokens=20, output_tokens=2),
                ),
            ],
            context_capacity=100_000,
        ),
        gateway=gateway,
        event_sink=tee,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="go")])

    (summary,) = consumer.summaries
    assert summary.session_id == session_id
    assert summary.turns == 2
    assert summary.tool_calls == 2
    assert summary.tool_failures == 1  # the unknown tool
    assert summary.input_tokens == 30
    assert summary.output_tokens == 6
    assert summary.termination_reason == "natural-completion"
    assert session_id[:8] in summary.render()

    # The stream the consumer saw is the same sanctioned stream the host saw.
    assert any(e.type == "run-terminated" for e in collector.events)


def test_consumer_references_no_agent_loop_internals() -> None:
    """SC-009 structural audit: the example imports only the public event
    vocabulary — no loop, gateway, controller, or model internals.
    """
    source = (EXAMPLES_DIR / "run_summary_consumer.py").read_text("utf-8")
    forbidden = (
        "loopplane.loop",
        "loopplane.gateway",
        "loopplane.controller",
        "loopplane.model",
        "loopplane.checkpoint",
        "loopplane.approval",
        "loopplane.artifacts",
        "loopplane.memory",
        "loopplane.skills",
        "loopplane.tools",
        "loopplane.adapters",
    )
    for module in forbidden:
        assert module not in source, f"consumer must not reference {module}"
    assert "loopplane.events" in source  # the sanctioned vocabulary
