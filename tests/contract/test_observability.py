"""Contract tests for the observability overlay (FR-100–FR-104; SC-004).

Disabled (the default): the sink passes through untouched and event
sequences are identical. Enabled: nested run/turn/model-call/tool-call
spans with durations, low-cardinality metrics, sentinel content absent from
every span and metric, failures recorded by error type only, and policy
denials excluded from execution-failure counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from loopplane.approval import HumanApproval, PermissionRule
from loopplane.controller.controller import RuntimeController
from loopplane.events.emitter import EventSink
from loopplane.gateway import ToolGateway
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
)
from loopplane.observability import maybe_attach
from loopplane.observability.overlay import ObservabilitySink
from tests.integration.conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio

SENTINEL = "SENTINEL-7f3a9c-DO-NOT-EXPORT"


def _tool_script(text: str = "hello") -> list[ScriptEntry]:
    return [
        ScriptedTurn(
            increments=[
                TextIncrement(text=f"let me echo {text}"),
                ToolCallRequest(call_id="c1", tool_name="echo", input={"text": text}),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text=f"echoed {text}")]),
    ]


async def _run_session(
    script: list[ScriptEntry],
    sink: EventSink,
    tmp_path: Path,
    *,
    decide: HumanApproval | None = None,
    extra_tools: list[tuple[Any, Any]] | None = None,
    user_text: str = "please echo",
) -> None:
    gateway = ToolGateway(decide=decide)
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    for descriptor, handler in extra_tools or []:
        gateway.register(descriptor, handler)
    controller = RuntimeController(
        model=ScriptedModel(script=script, context_capacity=100_000),
        gateway=gateway,
        event_sink=sink,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text=user_text)])


def _telemetry(
    span_exporter: InMemorySpanExporter, metric_reader: InMemoryMetricReader
) -> tuple[list[Any], list[tuple[str, dict[str, Any], Any]]]:
    spans = list(span_exporter.get_finished_spans())
    points: list[tuple[str, dict[str, Any], Any]] = []
    data = metric_reader.get_metrics_data()
    if data is not None:
        for resource_metrics in data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    for point in metric.data.data_points:
                        points.append(
                            (metric.name, dict(point.attributes), point.value)
                        )
    return spans, points


def _providers() -> tuple[
    InMemorySpanExporter, TracerProvider, InMemoryMetricReader, MeterProvider
]:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    return span_exporter, tracer_provider, metric_reader, meter_provider


# --- disabled by default (FR-100) ---------------------------------------------------


def test_disabled_is_the_unchanged_sink_no_overhead_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    async def sink(event: object) -> None: ...

    assert maybe_attach(sink) is sink


def test_env_gated_exporter_enables_the_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    async def sink(event: object) -> None: ...

    assert isinstance(maybe_attach(sink), ObservabilitySink)


async def test_enabled_changes_no_event_sequence(tmp_path: Path) -> None:
    plain = EventCollector()
    await _run_session(_tool_script(), plain, tmp_path / "plain")

    observed = EventCollector()
    span_exporter, tracer_provider, metric_reader, meter_provider = _providers()
    wrapped = ObservabilitySink(
        observed, tracer_provider=tracer_provider, meter_provider=meter_provider
    )
    await _run_session(_tool_script(), wrapped, tmp_path / "observed")

    assert observed.types == plain.types
    stable = [
        (e.type, e.payload)
        for e in plain.events
        if e.type not in ("tool-call-completed",)  # durations vary run to run
    ]
    stable_observed = [
        (e.type, e.payload)
        for e in observed.events
        if e.type not in ("tool-call-completed",)
    ]
    assert stable_observed == stable


# --- enabled: nested timed spans (FR-101) ---------------------------------------------


async def test_nested_run_turn_and_call_spans_with_durations(tmp_path: Path) -> None:
    sink = EventCollector()
    span_exporter, tracer_provider, metric_reader, meter_provider = _providers()
    wrapped = ObservabilitySink(
        sink, tracer_provider=tracer_provider, meter_provider=meter_provider
    )

    await _run_session(_tool_script(), wrapped, tmp_path)

    spans, _ = _telemetry(span_exporter, metric_reader)
    by_name: dict[str, list[Any]] = {}
    for span in spans:
        by_name.setdefault(span.name, []).append(span)

    assert len(by_name["loopplane.run"]) == 1
    assert len(by_name["loopplane.turn"]) == 2
    assert len(by_name["loopplane.model-call"]) == 2
    assert len(by_name["loopplane.tool-call"]) == 1

    run = by_name["loopplane.run"][0]
    for turn in by_name["loopplane.turn"]:
        assert turn.parent is not None
        assert turn.parent.span_id == run.context.span_id
    for model_call in by_name["loopplane.model-call"]:
        assert model_call.parent is not None
    tool = by_name["loopplane.tool-call"][0]
    assert tool.parent is not None
    assert tool.parent.span_id in {t.context.span_id for t in by_name["loopplane.turn"]}
    for span in spans:
        assert span.end_time is not None and span.start_time is not None
        assert span.end_time >= span.start_time


# --- metadata-only (FR-103; SC-004) --------------------------------------------


async def test_sentinel_content_is_absent_from_all_telemetry(tmp_path: Path) -> None:
    async def leaky_tool(
        call_input: dict[str, object], context: object
    ) -> list[OutputBlock]:
        raise ValueError(f"failed while reading {SENTINEL}")

    leaky_descriptor = ECHO_DESCRIPTOR.model_copy(update={"name": "leaky"})
    script: list[ScriptEntry] = [
        ScriptedTurn(
            increments=[
                TextIncrement(text=f"about to use {SENTINEL}"),
                ToolCallRequest(
                    call_id="c1", tool_name="echo", input={"text": SENTINEL}
                ),
                ToolCallRequest(call_id="c2", tool_name="leaky", input={"text": "x"}),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text=f"done with {SENTINEL}")]),
    ]
    sink = EventCollector()
    span_exporter, tracer_provider, metric_reader, meter_provider = _providers()
    wrapped = ObservabilitySink(
        sink, tracer_provider=tracer_provider, meter_provider=meter_provider
    )

    await _run_session(
        script,
        wrapped,
        tmp_path,
        extra_tools=[(leaky_descriptor, leaky_tool)],
        user_text=f"the user mentions {SENTINEL} too",
    )

    spans, points = _telemetry(span_exporter, metric_reader)
    blob = json.dumps(
        [
            {"name": span.name, "attributes": dict(span.attributes or {})}
            for span in spans
        ]
        + [{"metric": name, "attributes": attrs} for name, attrs, _ in points],
        default=str,
    )
    assert SENTINEL not in blob
    assert "failed while reading" not in blob  # no exception messages either


async def test_failures_record_error_type_only_and_denials_are_not_failures(
    tmp_path: Path,
) -> None:
    """FR-103 + FR-104: error *type* only; policy denials never count as
    execution failures.
    """

    async def broken_tool(
        call_input: dict[str, object], context: object
    ) -> list[OutputBlock]:
        raise ValueError("secret detail that must not export")

    broken_descriptor = ECHO_DESCRIPTOR.model_copy(update={"name": "broken"})
    script: list[ScriptEntry] = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(call_id="c1", tool_name="broken", input={"text": "x"}),
                ToolCallRequest(call_id="c2", tool_name="echo", input={"text": "y"}),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]
    sink = EventCollector()
    span_exporter, tracer_provider, metric_reader, meter_provider = _providers()
    wrapped = ObservabilitySink(
        sink, tracer_provider=tracer_provider, meter_provider=meter_provider
    )

    await _run_session(
        script,
        wrapped,
        tmp_path,
        decide=HumanApproval(
            rules=[
                PermissionRule(matcher="broken", effect="allow", scope="project"),
                PermissionRule(matcher="echo", effect="deny", scope="project"),
            ]
        ),
        extra_tools=[(broken_descriptor, broken_tool)],
    )

    _, points = _telemetry(span_exporter, metric_reader)
    tool_points = [
        (attrs, value)
        for name, attrs, value in points
        if name == "loopplane.tool_calls"
    ]
    outcomes = {attrs.get("outcome"): value for attrs, value in tool_points}

    assert outcomes.get("failed") == 1
    assert outcomes.get("policy-denied") == 1
    failed_attrs = next(
        attrs for attrs, _ in tool_points if attrs.get("outcome") == "failed"
    )
    assert (
        failed_attrs.get("error_type") == "execution"
    )  # the category, never the message


async def test_token_usage_exports_as_low_cardinality_metrics(tmp_path: Path) -> None:
    script: list[ScriptEntry] = [
        ScriptedTurn(
            increments=[TextIncrement(text="hi")],
            usage=TokenUsage(input_tokens=7, output_tokens=3, cached_tokens=2),
        )
    ]
    sink = EventCollector()
    span_exporter, tracer_provider, metric_reader, meter_provider = _providers()
    wrapped = ObservabilitySink(
        sink, tracer_provider=tracer_provider, meter_provider=meter_provider
    )

    await _run_session(script, wrapped, tmp_path)

    _, points = _telemetry(span_exporter, metric_reader)
    token_points = [
        (attrs, value) for name, attrs, value in points if name == "loopplane.tokens"
    ]
    assert token_points, "token usage must export as metrics"
    for attrs, _ in token_points:
        assert set(attrs) <= {"kind"}  # no per-session label values (FR-102)
