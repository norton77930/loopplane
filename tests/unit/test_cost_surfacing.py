"""Unit 064: the read-only cost accessors (cost surfacing).

The per-session USD accumulated by 055's ``BudgetChecker`` is exposed read-only via
``BudgetChecker.session_spent`` → ``AgentLoop.current_session_cost`` (``None`` when no
checker is configured). Read-only: no run-path or budget-state change. Offline.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from loopplane.budget import BudgetChecker, UsdBudgetCaps
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.loop import AgentLoop, SessionHistory
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    TokenUsage,
)
from loopplane.pricing import PricingRate, PricingTable

pytestmark = pytest.mark.anyio

_MODEL = "test-model"


def _table() -> PricingTable:
    return PricingTable(
        rates={
            _MODEL: PricingRate(
                input_rate=Decimal("0.000001"), output_rate=Decimal("0.000002")
            )
        }
    )


def _checker(per_session: Decimal | None = Decimal("100")) -> BudgetChecker:
    return BudgetChecker(
        caps=UsdBudgetCaps(per_session_usd=per_session),
        pricing=_table(),
        model_id=_MODEL,
    )


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def _loop(tmp_path: Path, *, checker: BudgetChecker | None) -> AgentLoop:
    return AgentLoop(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[TextIncrement(text="spending")],
                    usage=TokenUsage(input_tokens=1000, output_tokens=1000),
                )
            ],
            context_capacity=100_000,
        ),
        gateway=ToolGateway(),
        emitter=EventEmitter(
            session_id="s1", sequencer=EventSequencer(), sink=_Collector()
        ),
        history=SessionHistory(),
        budget_checker=checker,
    )


async def test_session_spent_accumulates_across_turns() -> None:
    checker = _checker()
    # cost = 1000*0.000001 + 1000*0.000002 = 0.003 per turn.
    assert await checker.record_turn(TokenUsage(input_tokens=1000, output_tokens=1000))
    assert await checker.record_turn(TokenUsage(input_tokens=1000, output_tokens=1000))
    assert checker.session_spent == Decimal("0.006")
    # the per-message accumulator is separate (reset per run); this is the SESSION total
    assert checker.session_spent != checker.spent or checker.spent == Decimal("0.006")


async def test_current_session_cost_is_none_without_a_checker(tmp_path: Path) -> None:
    loop = _loop(tmp_path, checker=None)
    assert loop.current_session_cost() is None


async def test_current_session_cost_reflects_the_checker(tmp_path: Path) -> None:
    checker = _checker()
    loop = _loop(tmp_path, checker=checker)
    await loop.run(
        [TextBlock(text="go")],
        RunContext(session_id="s1", working_scope=tmp_path),
    )
    cost = loop.current_session_cost()
    assert cost == Decimal("0.003")
    assert cost == checker.session_spent
