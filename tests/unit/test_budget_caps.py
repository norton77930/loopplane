"""Unit tests for USD budget caps (spec 055; gap G22 Phase B; ADR 0005).

In-loop USD enforcement: a per-message / per-session cap, priced from each turn's
``TokenUsage`` via 053's ``PricingTable``, terminates the run ``budget-exceeded`` after
the crossing turn (its output retained). Default-off (no checker) is byte-identical; an
unpriced model is fail-soft (a warning diagnostic, no enforcement). Offline (scripted).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from loopplane.budget import BudgetChecker, UsdBudgetCaps
from loopplane.context import RunContext
from loopplane.events import (
    SCHEMA_VERSION,
    EventSequencer,
    RuntimeEvent,
    deserialize_event,
    serialize_event,
)
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.loop import AgentLoop, SessionHistory
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    TokenUsage,
)
from loopplane.pricing import PricingRate, PricingTable

pytestmark = pytest.mark.anyio

_MODEL = "test-model"


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]


def _emitter(sink: _Collector) -> EventEmitter:
    return EventEmitter(session_id="session-1", sequencer=EventSequencer(), sink=sink)


def _context(tmp_path: Path) -> RunContext:
    return RunContext(session_id="session-1", working_scope=tmp_path)


def _table(
    *,
    input_rate: str = "0.000001",
    output_rate: str = "0.000002",
    model: str = _MODEL,
) -> PricingTable:
    return PricingTable(
        rates={
            model: PricingRate(
                input_rate=Decimal(input_rate), output_rate=Decimal(output_rate)
            )
        }
    )


def _checker(
    *,
    per_message: Decimal | None = None,
    per_session: Decimal | None = None,
    table: PricingTable | None = None,
    model_id: str = _MODEL,
) -> BudgetChecker:
    return BudgetChecker(
        caps=UsdBudgetCaps(per_message_usd=per_message, per_session_usd=per_session),
        pricing=table or _table(),
        model_id=model_id,
    )


def _usage(inp: int, out: int) -> TokenUsage:
    return TokenUsage(input_tokens=inp, output_tokens=out)


async def _run(
    script: list[ScriptEntry],
    tmp_path: Path,
    *,
    budget_checker: BudgetChecker | None = None,
) -> tuple[list[RuntimeEvent], SessionHistory]:
    sink = _Collector()
    history = SessionHistory()
    loop = AgentLoop(
        model=ScriptedModel(script=script, context_capacity=100_000),
        gateway=ToolGateway(),
        emitter=_emitter(sink),
        history=history,
        budget_checker=budget_checker,
    )
    await loop.run([TextBlock(text="go")], _context(tmp_path))
    return sink.events, history


def _reasons(events: list[RuntimeEvent]) -> list[str]:
    return [e.payload.reason for e in events if e.type == "run-terminated"]


def _assistant_texts(history: SessionHistory) -> list[str]:
    texts: list[str] = []
    for entry in history.snapshot():
        if entry.role != "assistant":
            continue
        for block in entry.blocks:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                texts.append(text)
    return texts


# --- in-loop enforcement -----------------------------------------------------


async def test_per_message_cap_crossed_terminates_budget_exceeded(
    tmp_path: Path,
) -> None:
    # cost = 1000*0.000001 + 1000*0.000002 = 0.003, over the 0.002 per-message cap.
    checker = _checker(per_message=Decimal("0.002"))
    script: list[ScriptEntry] = [
        ScriptedTurn(
            increments=[TextIncrement(text="spending")], usage=_usage(1000, 1000)
        )
    ]
    events, history = await _run(script, tmp_path, budget_checker=checker)

    terminals = [e for e in events if e.type == "run-terminated"]
    assert len(terminals) == 1
    assert events[-1].type == "run-terminated"
    assert terminals[0].payload.reason == "budget-exceeded"
    # The crossing turn's output is retained (not orphaned).
    assert "spending" in _assistant_texts(history)


async def test_under_cap_completes_naturally(tmp_path: Path) -> None:
    # cost 0.003 < the 0.01 per-message cap → no enforcement.
    checker = _checker(per_message=Decimal("0.01"))
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="cheap")], usage=_usage(1000, 1000))
    ]
    events, _ = await _run(script, tmp_path, budget_checker=checker)

    assert _reasons(events) == ["natural-completion"]
    assert not any(e.type == "diagnostic" for e in events)


async def test_per_session_cap_accumulates_across_runs(tmp_path: Path) -> None:
    # Two runs on ONE loop (one persistent checker): each turn costs 0.003; the
    # per-session cap is 0.005, so run 1 (0.003) completes and run 2 (0.006) is cut off.
    checker = _checker(per_session=Decimal("0.005"))
    sink = _Collector()
    loop = AgentLoop(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[TextIncrement(text="r1")], usage=_usage(1000, 1000)
                ),
                ScriptedTurn(
                    increments=[TextIncrement(text="r2")], usage=_usage(1000, 1000)
                ),
            ],
            context_capacity=100_000,
        ),
        gateway=ToolGateway(),
        emitter=_emitter(sink),
        history=SessionHistory(),
        budget_checker=checker,
    )
    await loop.run([TextBlock(text="one")], _context(tmp_path))
    await loop.run([TextBlock(text="two")], _context(tmp_path))

    assert _reasons(sink.events) == ["natural-completion", "budget-exceeded"]


async def test_default_off_is_byte_identical(tmp_path: Path) -> None:
    # No checker → no cost accounting, no budget diagnostic, the exact plain-run stream.
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="hi")], usage=_usage(1000, 1000))
    ]
    events, _ = await _run(script, tmp_path, budget_checker=None)

    assert [e.type for e in events] == [
        "user-input",
        "assistant-output-increment",
        "turn-completed",
        "run-terminated",
    ]
    assert _reasons(events) == ["natural-completion"]
    assert not any(e.type == "diagnostic" for e in events)


async def test_unpriced_model_is_fail_soft(tmp_path: Path) -> None:
    # The checker's model-id is absent from the pricing table → cost None. Even with a
    # zero cap, nothing accumulates: a warning diagnostic, no budget termination.
    checker = _checker(per_message=Decimal("0"), model_id="unpriced-model")
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="x")], usage=_usage(1000, 1000))
    ]
    events, _ = await _run(script, tmp_path, budget_checker=checker)

    assert _reasons(events) == ["natural-completion"]
    diagnostics = [e for e in events if e.type == "diagnostic"]
    assert any(
        d.payload.severity == "warning" and d.payload.category == "budget"
        for d in diagnostics
    )


# --- the checker, unit -------------------------------------------------------


async def test_budget_checker_accumulates_and_detects_crossing() -> None:
    table = PricingTable(
        rates={
            "m": PricingRate(input_rate=Decimal("0.001"), output_rate=Decimal("0.002"))
        }
    )
    checker = BudgetChecker(
        caps=UsdBudgetCaps(per_message_usd=Decimal("0.01")),
        pricing=table,
        model_id="m",
    )
    checker.start_run()
    assert checker.spent == Decimal(0)
    assert not checker.exceeded()

    # 10 input tokens × 0.001 = 0.010 (exact); at the cap, not over (strictly greater).
    assert (
        await checker.record_turn(TokenUsage(input_tokens=10, output_tokens=0))
    ) == Decimal("0.01")
    assert checker.spent == Decimal("0.01")
    assert not checker.exceeded()

    # +5 output tokens × 0.002 = 0.010 → 0.020 total, now over.
    assert (
        await checker.record_turn(TokenUsage(input_tokens=0, output_tokens=5))
    ) == Decimal("0.01")
    assert checker.spent == Decimal("0.02")
    assert checker.exceeded()
    assert not checker.unpriced

    # start_run resets the per-message accumulator.
    checker.start_run()
    assert checker.spent == Decimal(0)


async def test_budget_checker_unpriced_is_fail_soft() -> None:
    table = PricingTable(
        rates={
            "m": PricingRate(input_rate=Decimal("0.001"), output_rate=Decimal("0.002"))
        }
    )
    checker = BudgetChecker(
        caps=UsdBudgetCaps(per_message_usd=Decimal("0")),
        pricing=table,
        model_id="absent-model",
    )
    checker.start_run()
    assert (
        await checker.record_turn(TokenUsage(input_tokens=10, output_tokens=10))
    ) is None
    assert checker.unpriced
    assert checker.spent == Decimal(0)
    assert not checker.exceeded()


# --- event vocabulary (additive, no SCHEMA_VERSION bump) ---------------------


async def test_budget_exceeded_event_serializes_and_schema_unchanged(
    tmp_path: Path,
) -> None:
    assert SCHEMA_VERSION == 1
    checker = _checker(per_message=Decimal("0.001"))
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="x")], usage=_usage(1000, 1000))
    ]
    events, _ = await _run(script, tmp_path, budget_checker=checker)

    term = next(e for e in events if e.type == "run-terminated")
    assert term.payload.reason == "budget-exceeded"
    restored = deserialize_event(serialize_event(term))
    assert restored == term
    document = json.loads(serialize_event(term))
    assert document["schema_version"] == 1
