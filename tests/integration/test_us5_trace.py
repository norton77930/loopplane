"""US5 acceptance 5.2: the trace of a tool-using run shows the run with
nested timed steps for each turn, each model call, and each tool call
(FR-101).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
)
from loopplane.observability.overlay import ObservabilitySink

from .conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


async def test_trace_shape_for_a_tool_using_run(tmp_path: Path) -> None:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])

    sink = EventCollector()
    wrapped = ObservabilitySink(
        sink, tracer_provider=tracer_provider, meter_provider=meter_provider
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    controller = RuntimeController(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[
                        TextIncrement(text="echoing twice"),
                        ToolCallRequest(
                            call_id="c1", tool_name="echo", input={"text": "one"}
                        ),
                        ToolCallRequest(
                            call_id="c2", tool_name="echo", input={"text": "two"}
                        ),
                    ],
                    stop_reason="tool-use",
                ),
                ScriptedTurn(increments=[TextIncrement(text="all done")]),
            ],
            context_capacity=100_000,
        ),
        gateway=gateway,
        event_sink=wrapped,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="echo both")])

    spans = list(span_exporter.get_finished_spans())
    by_name: dict[str, list[Any]] = {}
    for span in spans:
        by_name.setdefault(span.name, []).append(span)

    # One run, two turns, two model calls, two tool calls — all timed.
    assert len(by_name["loopplane.run"]) == 1
    assert len(by_name["loopplane.turn"]) == 2
    assert len(by_name["loopplane.model-call"]) == 2
    assert len(by_name["loopplane.tool-call"]) == 2

    run = by_name["loopplane.run"][0]
    turn_ids = {turn.context.span_id for turn in by_name["loopplane.turn"]}
    assert all(
        turn.parent is not None and turn.parent.span_id == run.context.span_id
        for turn in by_name["loopplane.turn"]
    )
    assert all(
        span.parent is not None and span.parent.span_id in turn_ids
        for span in by_name["loopplane.model-call"] + by_name["loopplane.tool-call"]
    )
    assert all(span.end_time >= span.start_time for span in spans)

    run_attributes = dict(run.attributes or {})
    assert run_attributes.get("loopplane.termination_reason") == "natural-completion"
    assert run_attributes.get("loopplane.turns_taken") == 2

    tool_attributes = dict(by_name["loopplane.tool-call"][0].attributes or {})
    assert tool_attributes.get("loopplane.tool_name") == "echo"
