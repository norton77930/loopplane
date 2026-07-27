"""Unit 063: per-user-monthly USD cap enforcement (G22 Phase C; ADR 0010).

Extends 055's in-loop ``BudgetChecker`` with the optional durable monthly dimension
backed by 062's ``loopplane.ledger.UsdLedger``: the monthly cap rides the SAME
enforcement point + the SAME ``budget-exceeded`` reason, is FAIL-OPEN on a ledger
outage, and enforces on create AND resume. Offline (a ``FileUsdLedger`` + a model).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from loopplane.budget import BudgetChecker, UsdBudgetCaps
from loopplane.checkpoint import FileCheckpointStore
from loopplane.context import RunContext
from loopplane.controller.controller import RuntimeController
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.ledger import FileUsdLedger
from loopplane.ledger.base import UsdLedger
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

_MODEL = "m"
_MONTH = "2026-06"


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def _table() -> PricingTable:
    return PricingTable(
        rates={
            _MODEL: PricingRate(
                input_rate=Decimal("0.000001"), output_rate=Decimal("0.000002")
            )
        }
    )


def _ledger(tmp_path: Path) -> FileUsdLedger:
    return FileUsdLedger(tmp_path / "ledger")


def _checker(
    ledger: UsdLedger | None,
    *,
    principal_id: str | None,
    cap: Decimal | None,
    month: str = _MONTH,
) -> BudgetChecker:
    return BudgetChecker(
        caps=UsdBudgetCaps(),
        pricing=_table(),
        model_id=_MODEL,
        ledger=ledger,
        principal_id=principal_id,
        per_user_monthly_usd=cap,
        month=lambda: month,
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
        emitter=EventEmitter(session_id="s", sequencer=EventSequencer(), sink=sink),
        history=history,
        budget_checker=budget_checker,
    )
    await loop.run(
        [TextBlock(text="go")], RunContext(session_id="s", working_scope=tmp_path)
    )
    return sink.events, history


def _reasons(events: list[RuntimeEvent]) -> list[str]:
    return [e.payload.reason for e in events if e.type == "run-terminated"]


# --- BudgetChecker monthly dimension (unit) ----------------------------------


async def test_record_turn_accumulates_to_the_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    checker = _checker(ledger, principal_id="alice", cap=Decimal("999"))
    await checker.record_turn(_usage(1000, 1000))  # 0.003
    await checker.record_turn(_usage(1000, 1000))  # +0.003
    assert ledger.get("alice", _MONTH) == Decimal("0.006")
    assert not checker.exceeded()
    assert not checker.ledger_unavailable


async def test_monthly_cap_crossed_is_exceeded(tmp_path: Path) -> None:
    checker = _checker(_ledger(tmp_path), principal_id="alice", cap=Decimal("0.005"))
    await checker.record_turn(_usage(1000, 1000))  # 0.003, under
    assert not checker.exceeded()
    await checker.record_turn(_usage(1000, 1000))  # 0.006, over
    assert checker.exceeded()


async def test_monthly_cap_counts_a_prior_ledger_total(tmp_path: Path) -> None:
    # A pre-seeded month total (a prior session) is counted across sessions.
    ledger = _ledger(tmp_path)
    await ledger.add("alice", _MONTH, Decimal("0.004"))
    checker = _checker(ledger, principal_id="alice", cap=Decimal("0.005"))
    await checker.record_turn(_usage(1000, 1000))  # +0.003 → 0.007, over
    assert checker.exceeded()


# --- in-loop enforcement -----------------------------------------------------


async def test_monthly_cap_terminates_budget_exceeded(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    await ledger.add("alice", _MONTH, Decimal("0.004"))  # near the cap
    checker = _checker(ledger, principal_id="alice", cap=Decimal("0.005"))
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="spend")], usage=_usage(1000, 1000))
    ]
    events, history = await _run(script, tmp_path, budget_checker=checker)

    assert _reasons(events) == ["budget-exceeded"]
    # the crossing turn's output is retained
    texts = [
        getattr(block, "text", "")
        for entry in history.snapshot()
        if entry.role == "assistant"
        for block in entry.blocks
    ]
    assert "spend" in texts
    # the cost was durably added (0.004 + 0.003)
    assert ledger.get("alice", _MONTH) == Decimal("0.007")
    # public-safe: the principal id is never echoed in any event payload
    assert not any("alice" in repr(e.payload) for e in events)


async def test_fail_open_on_a_ledger_outage(tmp_path: Path) -> None:
    class _FailingLedger:
        async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
            raise RuntimeError("ledger down")

        def get(self, principal_id: str, month: str) -> Decimal:
            return Decimal(0)

    # cap 0 → any accumulated spend would cross; fail-open means nothing accumulates.
    checker = _checker(_FailingLedger(), principal_id="alice", cap=Decimal("0"))
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="ok")], usage=_usage(1000, 1000))
    ]
    events, _ = await _run(script, tmp_path, budget_checker=checker)

    assert _reasons(events) == ["natural-completion"]  # NOT terminated (fail-open)
    diagnostics = [e for e in events if e.type == "diagnostic"]
    assert any("ledger is unavailable" in e.payload.message for e in diagnostics)
    assert checker.ledger_unavailable
    assert not any("alice" in repr(e.payload) for e in events)


async def test_monthly_posture_stays_unknown_after_an_unrecorded_turn() -> None:
    class _FlappingLedger:
        def __init__(self) -> None:
            self.fail = True
            self.total = Decimal(0)

        async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
            if self.fail:
                self.fail = False
                raise RuntimeError("ledger down")
            self.total += usd
            return self.total

        def get(self, principal_id: str, month: str) -> Decimal:
            return self.total

    ledger = _FlappingLedger()
    checker = _checker(ledger, principal_id="alice", cap=Decimal("1"))

    await checker.record_turn(_usage(1000, 1000))
    assert checker.guard_posture().tracking == "unavailable"
    assert checker.guard_posture().monthly_guard == "unknown"

    await checker.record_turn(_usage(1000, 1000))
    assert checker.guard_posture().tracking == "unavailable"
    assert checker.guard_posture().monthly_guard == "unknown"
    assert "alice" not in repr(checker.guard_posture())
    assert _MONTH not in repr(checker.guard_posture())


async def test_default_off_no_monthly_dim_is_byte_identical(tmp_path: Path) -> None:
    # A checker with no ledger / principal / monthly cap behaves like 055.
    checker = BudgetChecker(caps=UsdBudgetCaps(), pricing=_table(), model_id=_MODEL)
    script: list[ScriptEntry] = [
        ScriptedTurn(increments=[TextIncrement(text="hi")], usage=_usage(1000, 1000))
    ]
    events, _ = await _run(script, tmp_path, budget_checker=checker)

    assert _reasons(events) == ["natural-completion"]
    assert not any(e.type == "diagnostic" for e in events)


# --- resume enforces (the closed gap) ----------------------------------------


async def test_monthly_cap_enforces_on_resume(tmp_path: Path) -> None:
    # The real current month (the controller's default clock); seed alice near the cap.
    month = datetime.now(UTC).strftime("%Y-%m")
    ledger = FileUsdLedger(tmp_path / "ledger")
    await ledger.add("alice", month, Decimal("0.004"))

    def _ctrl(script: list[ScriptEntry], sink: _Collector) -> RuntimeController:
        return RuntimeController(
            model=ScriptedModel(script=script, context_capacity=100_000),
            gateway=ToolGateway(),
            event_sink=sink,
            checkpoint_store=FileCheckpointStore(tmp_path / "sessions"),
            pricing_table=_table(),
            model_id=_MODEL,
            per_user_monthly_usd=Decimal("0.005"),
            usd_ledger=ledger,
        )

    # Create + a benign first run (no usage → no accrual; the session persists with
    # principal_id="alice"). Then "kill the process".
    first = _ctrl([ScriptedTurn(increments=[TextIncrement(text="r1")])], _Collector())
    sid = first.create_session(
        working_scope=tmp_path, principal_id="alice", label="resumable"
    )
    await first.drive(sid, [TextBlock(text="one")])
    del first

    # Resume in a fresh controller; a crossing turn must terminate budget-exceeded —
    # which only happens if principal_id was re-threaded from the persisted records.
    sink = _Collector()
    second = _ctrl(
        [ScriptedTurn(increments=[TextIncrement(text="r2")], usage=_usage(1000, 1000))],
        sink,
    )
    await second.resume(sid)
    await second.drive(sid, [TextBlock(text="two")])  # +0.003 → 0.007 > 0.005

    assert "budget-exceeded" in _reasons(sink.events)
