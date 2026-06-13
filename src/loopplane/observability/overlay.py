"""The observability overlay: spans and low-cardinality metrics fed from
runtime events (FR-101, FR-102), strictly metadata-only (FR-103).

This module imports the OpenTelemetry API and is itself imported lazily;
the core never depends on it. Telemetry never raises into the event path,
and replayed events are never re-observed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.trace import Span, set_span_in_context

from loopplane.errors import ErrorCategory
from loopplane.events.emitter import EventSink
from loopplane.events.envelope import (
    RunTerminatedEvent,
    RuntimeEvent,
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
    TurnCompletedEvent,
    UserInputEvent,
)


@dataclass
class _SessionTrace:
    run_span: Span | None = None
    turn_span: Span | None = None
    turn_started_ns: int = 0
    tool_names: dict[str, str] = field(default_factory=dict)


class ObservabilitySink:
    def __init__(
        self,
        inner: EventSink,
        *,
        tracer_provider: otel_trace.TracerProvider | None = None,
        meter_provider: otel_metrics.MeterProvider | None = None,
        clock: Callable[[], int] = time.time_ns,
    ) -> None:
        self._inner = inner
        self._clock = clock
        tracer_provider = tracer_provider or otel_trace.get_tracer_provider()
        meter_provider = meter_provider or otel_metrics.get_meter_provider()
        self._tracer = tracer_provider.get_tracer("loopplane")
        meter = meter_provider.get_meter("loopplane")
        self._tokens = meter.create_counter("loopplane.tokens", unit="token")
        self._turns = meter.create_counter("loopplane.turns")
        self._tool_calls = meter.create_counter("loopplane.tool_calls")
        self._runs = meter.create_counter("loopplane.runs")
        self._sessions: dict[str, _SessionTrace] = {}

    async def __call__(self, event: RuntimeEvent) -> None:
        try:
            self._observe(event)
        except Exception:
            # Telemetry must never change runtime behavior (FR-100).
            pass
        await self._inner(event)

    def _observe(self, event: RuntimeEvent) -> None:
        if event.replay:
            return
        state = self._sessions.setdefault(event.session_id, _SessionTrace())
        now_ns = self._clock()

        if isinstance(event, UserInputEvent):
            if state.run_span is None:
                state.run_span = self._tracer.start_span(
                    "loopplane.run", start_time=now_ns
                )
                state.turn_started_ns = now_ns
        elif isinstance(event, TurnCompletedEvent):
            # Read the turn's start before _close_turn resets it to now, so
            # the turn and model-call spans carry a real duration (FR-101).
            started = state.turn_started_ns or now_ns
            self._close_turn(state, now_ns)
            turn = self._tracer.start_span(
                "loopplane.turn",
                context=(
                    set_span_in_context(state.run_span) if state.run_span else None
                ),
                start_time=started,
                attributes={"loopplane.turn_index": event.payload.turn_index},
            )
            model_call = self._tracer.start_span(
                "loopplane.model-call",
                context=set_span_in_context(turn),
                start_time=started,
                attributes={"loopplane.stop_reason": event.payload.stop_reason},
            )
            model_call.end(end_time=now_ns)
            state.turn_span = turn
            usage = event.payload.usage
            for kind, value in (
                ("input", usage.input_tokens),
                ("output", usage.output_tokens),
                ("cached", usage.cached_tokens),
                ("reasoning", usage.reasoning_tokens),
            ):
                if value:
                    self._tokens.add(value, {"kind": kind})
            self._turns.add(1)
        elif isinstance(event, ToolCallStartedEvent):
            state.tool_names[event.payload.call_id] = event.payload.tool_name
        elif isinstance(event, ToolCallCompletedEvent):
            self._observe_tool_call(state, event, now_ns)
        elif isinstance(event, RunTerminatedEvent):
            self._close_turn(state, now_ns)
            if state.run_span is not None:
                state.run_span.set_attribute(
                    "loopplane.termination_reason", event.payload.reason
                )
                state.run_span.set_attribute(
                    "loopplane.turns_taken", event.payload.turns_taken
                )
                state.run_span.end(end_time=now_ns)
            self._runs.add(1, {"reason": event.payload.reason})
            self._sessions.pop(event.session_id, None)

    def _observe_tool_call(
        self, state: _SessionTrace, event: ToolCallCompletedEvent, now_ns: int
    ) -> None:
        payload = event.payload
        tool_name = state.tool_names.pop(payload.call_id, "unknown")
        if payload.outcome == "success":
            outcome = "success"
        elif (
            payload.error is not None
            and payload.error.category == ErrorCategory.POLICY_DENIAL
        ):
            # Policy denials are not execution failures (FR-104).
            outcome = "policy-denied"
        else:
            outcome = "failed"

        attributes: dict[str, str] = {
            "loopplane.tool_name": tool_name,
            "loopplane.outcome": outcome,
        }
        metric_attributes: dict[str, str] = {"tool": tool_name, "outcome": outcome}
        if outcome == "failed" and payload.error is not None:
            # Error *type* only — never messages or stack traces (FR-103).
            attributes["loopplane.error_type"] = payload.error.category.value
            metric_attributes["error_type"] = payload.error.category.value

        parent = state.turn_span or state.run_span
        duration_ns = max(int(payload.duration_seconds * 1_000_000_000), 0)
        span = self._tracer.start_span(
            "loopplane.tool-call",
            context=set_span_in_context(parent) if parent else None,
            start_time=now_ns - duration_ns,
            attributes=attributes,
        )
        span.end(end_time=now_ns)
        self._tool_calls.add(1, metric_attributes)

    @staticmethod
    def _close_turn(state: _SessionTrace, end_ns: int) -> None:
        if state.turn_span is not None:
            state.turn_span.end(end_time=end_ns)
            state.turn_span = None
        state.turn_started_ns = end_ns
