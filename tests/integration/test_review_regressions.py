"""Regression tests for the code-review and security-review fixes."""

from __future__ import annotations

from itertools import count
from pathlib import Path

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from loopplane.adapters.mcp import MCPServerConfig, merge_layers
from loopplane.checkpoint import CheckpointStore
from loopplane.context import RunContext
from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.gateway.spi import ErrorOutput
from loopplane.gateway.validation import validate_input
from loopplane.loop import SessionHistory, compact_history
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    SummaryMarkerBlock,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
)
from loopplane.observability.overlay import ObservabilitySink
from loopplane.skills import Skill, SkillAdvertiser
from loopplane.tools import InternalToolAdapter

from .conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


# --- security: path traversal confinement (tools/internal.py) -----------------


async def _invoke_internal(
    adapter: InternalToolAdapter,
    name: str,
    call_input: dict[str, object],
    tmp_path: Path,
) -> list[OutputBlock]:
    context = RunContext(session_id="s1", working_scope=tmp_path)
    return [output async for output in adapter.invoke(name, call_input, context)]


async def test_read_outside_working_scope_is_rejected(tmp_path: Path) -> None:
    scope = tmp_path / "scope"
    scope.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    adapter = InternalToolAdapter()

    for path in (str(secret), "../secret.txt"):
        (output,) = await _invoke_internal(adapter, "read_file", {"path": path}, scope)
        assert isinstance(output, ErrorOutput)
        assert output.category == "validation"
        assert "working scope" in output.message


async def test_write_outside_working_scope_is_rejected(tmp_path: Path) -> None:
    scope = tmp_path / "scope"
    scope.mkdir()
    adapter = InternalToolAdapter()

    (output,) = await _invoke_internal(
        adapter,
        "write_file",
        {"path": "../escape.txt", "content": "owned"},
        scope,
    )
    assert isinstance(output, ErrorOutput)
    assert output.category == "validation"
    assert not (tmp_path / "escape.txt").exists()


async def test_in_scope_file_access_still_works(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    (written,) = await _invoke_internal(
        adapter, "write_file", {"path": "notes/a.txt", "content": "ok"}, tmp_path
    )
    assert not isinstance(written, ErrorOutput)
    (read,) = await _invoke_internal(
        adapter, "read_file", {"path": "notes/a.txt"}, tmp_path
    )
    assert isinstance(read, TextBlock)
    assert read.text == "ok"


# --- validation: undeclared params under composition (FR-022) ------------------


def test_undeclared_parameter_rejected_in_allof_schema() -> None:
    schema: dict[str, object] = {
        "allOf": [
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
            }
        ]
    }
    problem = validate_input(schema, {"text": "ok", "rogue": 1})
    assert problem is not None
    assert "rogue" in problem


def test_declared_param_under_composition_passes() -> None:
    schema: dict[str, object] = {
        "anyOf": [{"type": "object", "properties": {"text": {"type": "string"}}}]
    }
    assert validate_input(schema, {"text": "ok"}) is None


# --- skills: oversized skill must not starve later skills -----------------------


def test_oversized_skill_does_not_starve_later_skills() -> None:
    giant = Skill(name="aaa", description="x" * 500, instructions="do aaa")
    small = Skill(name="bbb", description="short", instructions="do bbb")
    advertiser = SkillAdvertiser([giant, small], prompt_budget_chars=80)

    advertised = advertiser.augment_for("anything")

    assert advertised is not None
    assert "skill:bbb" in advertised  # the small one is not blocked
    assert "skill:aaa" not in advertised  # the giant one never fit


# --- compaction: short-but-large histories can compact (FR-008) -----------------


async def test_short_history_can_compact() -> None:
    history = SessionHistory()
    await history.append("user", [TextBlock(text="x" * 5000)])
    await history.append("assistant", [TextBlock(text="a brief reply")])
    await history.append("user", [TextBlock(text="another turn")])

    compacted = compact_history(history, keep_last=4)

    assert compacted is True
    entries = history.snapshot()
    assert any(
        isinstance(block, SummaryMarkerBlock)
        for entry in entries
        for block in entry.blocks
    )


# --- MCP layered config: malformed override keeps the broader valid one ---------


def test_malformed_override_keeps_broader_valid_config() -> None:
    broad = {"srv": {"transport": "stdio", "command": "good-command"}}
    specific = {"srv": {"transport": "stdio"}}  # malformed: stdio without command

    configs, problems = merge_layers([broad, specific])

    by_name = {config.name: config for config in configs}
    assert "srv" in by_name  # the broader valid definition survives
    assert by_name["srv"].command == "good-command"
    assert len(problems) == 1 and "srv" in problems[0]
    assert isinstance(by_name["srv"], MCPServerConfig)


# --- controller: replay event sequences are monotonic in delivery order ---------


async def test_replay_sequences_are_monotonic(tmp_path: Path) -> None:
    sink = EventCollector()
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    controller = RuntimeController(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[
                        TextIncrement(text="using a tool"),
                        ToolCallRequest(
                            call_id="c1", tool_name="echo", input={"text": "hi"}
                        ),
                    ],
                    stop_reason="tool-use",
                ),
                ScriptedTurn(increments=[TextIncrement(text="done")]),
            ],
            context_capacity=100_000,
        ),
        gateway=gateway,
        event_sink=sink,
        checkpoint_store=CheckpointStore(tmp_path / "sessions"),
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="please echo")])
    sink.events.clear()

    await controller.attach(session_id)

    replay_sequences = [event.sequence for event in sink.events if event.replay]
    assert replay_sequences == sorted(replay_sequences)
    assert len(replay_sequences) == len(set(replay_sequences))  # gap-free, no dupes
    assert sink.events[0].type == "replay-started"
    assert sink.events[-1].type == "replay-completed"
    assert sink.events[0].sequence < sink.events[-1].sequence


# --- observability: model-call spans carry a real duration (FR-101) -------------


async def test_model_call_spans_have_nonzero_duration(tmp_path: Path) -> None:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    meter_provider = MeterProvider(metric_readers=[InMemoryMetricReader()])

    # A deterministic, strictly increasing clock — real wall-clock resolution
    # is too coarse to prove the model-call span spans the turn rather than
    # collapsing to a point (the bug was `started` read after it was reset).
    ticks = count(1)

    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    controller = RuntimeController(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[TextIncrement(text=f"chunk-{i}") for i in range(8)],
                    usage=TokenUsage(input_tokens=4, output_tokens=8),
                )
            ],
            context_capacity=100_000,
        ),
        gateway=gateway,
        event_sink=ObservabilitySink(
            EventCollector(),
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            clock=lambda: next(ticks),
        ),
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="go")])

    model_calls = [
        span
        for span in span_exporter.get_finished_spans()
        if span.name == "loopplane.model-call"
    ]
    assert model_calls
    assert all(span.end_time > span.start_time for span in model_calls)
