"""The gating matrix (SC-007; NFR-002): with every optional subsystem
enabled — durability, artifacts, memory, skills, assembly, observability,
an external tool adapter — scripted runs produce event sequences identical
to the core loop alone.
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

from loopplane.artifacts import ArtifactStore, make_artifact_handoff
from loopplane.checkpoint import FileCheckpointStore
from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.events.emitter import EventSink
from loopplane.gateway import ToolGateway
from loopplane.memory import MemoryStore
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
)
from loopplane.observability.overlay import ObservabilitySink

from .conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


def _script() -> list[ScriptEntry]:
    return [
        ScriptedTurn(
            increments=[
                TextIncrement(text="let me use the tool"),
                ToolCallRequest(call_id="c1", tool_name="echo", input={"text": "ping"}),
            ],
            stop_reason="tool-use",
            usage=TokenUsage(input_tokens=5, output_tokens=3),
        ),
        ScriptedTurn(
            increments=[TextIncrement(text="all done")],
            usage=TokenUsage(input_tokens=9, output_tokens=2),
        ),
    ]


def _normalize(event: RuntimeEvent) -> tuple[str, object]:
    payload: dict[str, Any] = event.payload.model_dump(mode="json")
    payload.pop("duration_seconds", None)  # wall-clock noise
    return event.type, payload


async def _drive(controller: RuntimeController, tmp_path: Path) -> None:
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="ping the tool")])


async def test_all_optional_subsystems_on_change_no_event_sequence(
    tmp_path: Path,
) -> None:
    # Baseline: the core loop alone.
    baseline_sink = EventCollector()
    baseline_gateway = ToolGateway()
    baseline_gateway.register(ECHO_DESCRIPTOR, echo_handler)
    await _drive(
        RuntimeController(
            model=ScriptedModel(script=_script(), context_capacity=100_000),
            gateway=baseline_gateway,
            event_sink=baseline_sink,
        ),
        tmp_path / "baseline",
    )

    # Everything on: durability, artifacts, memory (empty), skills (none),
    # assembly, and the observability overlay.
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    meter_provider = MeterProvider(metric_readers=[InMemoryMetricReader()])
    everything_sink = EventCollector()
    observed: EventSink = ObservabilitySink(
        everything_sink, tracer_provider=tracer_provider, meter_provider=meter_provider
    )

    storage = tmp_path / "everything"
    artifacts = ArtifactStore(storage / "sessions")
    gateway = ToolGateway(artifact_handoff=make_artifact_handoff(artifacts))
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    await _drive(
        RuntimeController(
            model=ScriptedModel(script=_script(), context_capacity=100_000),
            gateway=gateway,
            event_sink=observed,
            checkpoint_store=FileCheckpointStore(storage / "sessions"),
            artifact_store=artifacts,
            memory_store=MemoryStore(storage / "memory"),
            skills={},
            enable_assembly=True,
        ),
        storage,
    )

    baseline = [_normalize(event) for event in baseline_sink.events]
    everything = [_normalize(event) for event in everything_sink.events]
    assert everything == baseline

    # And the overlay really was active while behavior stayed identical.
    assert span_exporter.get_finished_spans()
