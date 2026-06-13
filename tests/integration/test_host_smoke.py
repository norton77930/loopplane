"""US1: embed and start a run through the Host Application Interface
(spec US1; SC-001, FR-001/003/004/006).

A minimal config (scripted model + one echo tool) runs end-to-end through
``LoopPlaneHost`` and yields an ordered event stream plus a ``RunOutcome`` — with
no manual wiring of Phase-1 collaborators.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RunOutcome, RuntimeConfig, build_host
from loopplane.model import TextBlock, ToolResultBlock

from .conftest import (
    ECHO_TOOL,
    EventCollector,
    multi_text_model,
    text_model,
    tool_then_text_model,
)

pytestmark = pytest.mark.anyio


async def test_text_only_run(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(model=text_model("hello there")), working_scope=tmp_path
    )
    sink = EventCollector()

    outcome = await host.run("hi", sink)

    assert isinstance(outcome, RunOutcome)
    assert outcome.termination_reason == "natural-completion"
    assert sink.types[0] == "user-input"
    assert sink.types[-1] == "run-terminated"
    assert "assistant-output-increment" in sink.types
    roles = [entry.role for entry in outcome.history]
    assert roles == ["user", "assistant"]


async def test_tool_call_run_executes_through_the_gateway(tmp_path: Path) -> None:
    host = build_host(
        RuntimeConfig(model=tool_then_text_model(), tools=(ECHO_TOOL,)),
        working_scope=tmp_path,
    )
    sink = EventCollector()

    outcome = await host.run("please echo hello", sink)

    assert "tool-call-started" in sink.types
    assert "tool-call-completed" in sink.types
    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "success"
    assert outcome.termination_reason == "natural-completion"
    tool_result = next(
        block
        for entry in outcome.history
        for block in entry.blocks
        if isinstance(block, ToolResultBlock)
    )
    assert tool_result.outcome == "success"


async def test_run_returns_events_in_monotonic_order(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(model=tool_then_text_model(), tools=(ECHO_TOOL,)),
        working_scope=tmp_path,
    )
    sink = EventCollector()

    await host.run("go", sink)

    sequences = [event.sequence for event in sink.events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


async def test_sequential_runs_are_independent(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(model=multi_text_model("first", "second")),
        working_scope=tmp_path,
    )

    first = await host.run("one", EventCollector())
    second = await host.run("two", EventCollector())

    assert first.session_id != second.session_id
    assert first.termination_reason == "natural-completion"
    assert second.termination_reason == "natural-completion"
    # No leakage: each session's history holds only its own exchange.
    text_blocks = [
        b for e in second.history for b in e.blocks if isinstance(b, TextBlock)
    ]
    assert text_blocks == [TextBlock(text="two"), TextBlock(text="second")]
