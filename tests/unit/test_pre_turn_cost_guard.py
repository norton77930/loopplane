"""Pre-turn USD cost guard tests (spec 068; ADR 0014).

The guard is default-off and fail-open. These tests stay offline: a scripted model
records whether the loop actually called the model, and pricing is host-supplied.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import pytest

import loopplane.loop.assembly as assembly
import loopplane.loop.loop as loop_module
from loopplane.budget import BudgetChecker, UsdBudgetCaps
from loopplane.context import RunContext
from loopplane.events import SCHEMA_VERSION, EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.host import ConfigError, LoopPlaneHost, RuntimeConfig
from loopplane.host.assembly import assemble
from loopplane.loop import AgentLoop, SessionHistory
from loopplane.model import (
    Message,
    ModelIncrement,
    ModelRequest,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolDescriptor,
    TurnEnd,
)
from loopplane.model.content import ToolCallBlock
from loopplane.pricing import PricingRate, PricingTable

pytestmark = pytest.mark.anyio

_MODEL = "test-model"


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


class _CountingModel:
    def __init__(self, turn: ScriptedTurn, *, context_capacity: int = 100_000) -> None:
        self._turn = turn
        self._capacity = context_capacity
        self.calls: list[ModelRequest] = []

    def context_capacity(self) -> int:
        return self._capacity

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.calls.append(request)
        for increment in self._turn.increments:
            yield increment
        yield TurnEnd(stop_reason=self._turn.stop_reason, usage=self._turn.usage)


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
    pre_turn_max_output_tokens: int | None = None,
) -> BudgetChecker:
    return BudgetChecker(
        caps=UsdBudgetCaps(per_message_usd=per_message, per_session_usd=per_session),
        pricing=table or _table(),
        model_id=model_id,
        pre_turn_max_output_tokens=pre_turn_max_output_tokens,
    )


def _usage(inp: int, out: int) -> TokenUsage:
    return TokenUsage(input_tokens=inp, output_tokens=out)


async def _run(
    model: _CountingModel,
    tmp_path: Path,
    *,
    budget_checker: BudgetChecker | None = None,
) -> tuple[list[RuntimeEvent], SessionHistory]:
    sink = _Collector()
    history = SessionHistory()
    loop = AgentLoop(
        model=model,
        gateway=ToolGateway(),
        emitter=_emitter(sink),
        history=history,
        budget_checker=budget_checker,
    )
    await loop.run([TextBlock(text="go")], _context(tmp_path))
    return sink.events, history


async def _run_host(
    config: RuntimeConfig, tmp_path: Path
) -> tuple[list[RuntimeEvent], str]:
    sink = _Collector()
    host = LoopPlaneHost(config, working_scope=tmp_path)

    outcome = await host.run("go", sink)

    return sink.events, outcome.termination_reason


def _reasons(events: list[RuntimeEvent]) -> list[str]:
    return [e.payload.reason for e in events if e.type == "run-terminated"]


def _assistant_texts(history: SessionHistory) -> list[str]:
    return [
        block.text
        for entry in history.snapshot()
        if entry.role == "assistant"
        for block in entry.blocks
        if isinstance(block, TextBlock)
    ]


def _descriptor(name: str = "tool") -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=f"test tool {name}",
        input_schema={"type": "object"},
    )


def _request_with_context() -> ModelRequest:
    return ModelRequest(
        context=[
            Message(role="user", blocks=[TextBlock(text="abcd")]),
            Message(
                role="assistant",
                blocks=[
                    TextBlock(text="efgh"),
                    ToolCallBlock(call_id="c1", tool_name="tool", input={}),
                ],
            ),
        ],
        tools=[_descriptor()],
        output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
    )


async def test_estimate_request_tokens_reuses_assembly_text_heuristic() -> None:
    assert hasattr(assembly, "estimate_request_tokens")
    estimate = assembly.estimate_request_tokens(_request_with_context())

    # Existing assembly sizing counts text length and a fixed cost for non-text
    # blocks. The helper must match that heuristic exactly so default compaction
    # behavior does not drift.
    assert estimate == (len("abcd") + len("efgh") + 50) // 4
    assert estimate > 0


def test_pre_turn_max_output_tokens_mapping_defaults_none() -> None:
    model = _CountingModel(ScriptedTurn())

    config = RuntimeConfig.from_mapping(
        {"model": model, "pre_turn_max_output_tokens": 128}
    )

    assert config.pre_turn_max_output_tokens == 128
    assert (
        RuntimeConfig.from_mapping({"model": model}).pre_turn_max_output_tokens is None
    )


@pytest.mark.parametrize("bad_value", [-1, 1.25, "many"])
def test_pre_turn_max_output_tokens_must_be_non_negative_integer(
    bad_value: object,
) -> None:
    with pytest.raises(ConfigError, match="pre_turn_max_output_tokens"):
        LoopPlaneHost(
            RuntimeConfig(
                model=_CountingModel(ScriptedTurn()),
                pre_turn_max_output_tokens=bad_value,  # type: ignore[arg-type]
            )
        )


def test_pre_turn_max_output_tokens_reaches_per_session_budget_checker(
    tmp_path: Path,
) -> None:
    runtime = assemble(
        RuntimeConfig(
            model=_CountingModel(ScriptedTurn()),
            pricing_table=_table(),
            model_id=_MODEL,
            per_message_usd=Decimal("1"),
            pre_turn_max_output_tokens=128,
        )
    )

    session_id = runtime.controller.create_session(working_scope=tmp_path)
    session = runtime.controller._sessions[session_id]  # type: ignore[attr-defined]
    checker = session.loop._budget_checker  # type: ignore[attr-defined]

    assert checker is not None
    assert checker.pre_turn_max_output_tokens == 128


def test_pre_turn_max_output_tokens_alone_does_not_create_budget_checker(
    tmp_path: Path,
) -> None:
    runtime = assemble(
        RuntimeConfig(
            model=_CountingModel(ScriptedTurn()),
            pre_turn_max_output_tokens=128,
        )
    )

    session_id = runtime.controller.create_session(working_scope=tmp_path)
    session = runtime.controller._sessions[session_id]  # type: ignore[attr-defined]

    assert session.loop.current_session_cost() is None


async def test_pre_turn_per_message_overage_terminates_before_model_call(
    tmp_path: Path,
) -> None:
    model = _CountingModel(
        ScriptedTurn(increments=[TextIncrement(text="should not stream")])
    )
    checker = _checker(
        per_message=Decimal("1"),
        table=_table(input_rate="0", output_rate="1"),
        pre_turn_max_output_tokens=2,
    )

    events, _ = await _run(model, tmp_path, budget_checker=checker)

    assert model.calls == []
    assert _reasons(events) == ["budget-exceeded"]


async def test_pre_turn_per_session_overage_terminates_before_model_call(
    tmp_path: Path,
) -> None:
    model = _CountingModel(
        ScriptedTurn(increments=[TextIncrement(text="should not stream")])
    )
    checker = _checker(
        per_session=Decimal("1"),
        table=_table(input_rate="0", output_rate="1"),
        pre_turn_max_output_tokens=2,
    )

    events, _ = await _run(model, tmp_path, budget_checker=checker)

    assert model.calls == []
    assert _reasons(events) == ["budget-exceeded"]


async def test_missing_pre_turn_max_output_tokens_allows_model_call(
    tmp_path: Path,
) -> None:
    model = _CountingModel(ScriptedTurn(increments=[TextIncrement(text="called")]))
    checker = _checker(
        per_message=Decimal("0"),
        table=_table(input_rate="0", output_rate="1"),
    )

    events, _ = await _run(model, tmp_path, budget_checker=checker)

    assert len(model.calls) == 1
    assert _reasons(events) == ["natural-completion"]


async def test_missing_pricing_table_allows_model_call(tmp_path: Path) -> None:
    model = _CountingModel(ScriptedTurn(increments=[TextIncrement(text="called")]))

    _, reason = await _run_host(
        RuntimeConfig(
            model=model,
            model_id=_MODEL,
            per_message_usd=Decimal("0"),
            pre_turn_max_output_tokens=2,
        ),
        tmp_path,
    )

    assert len(model.calls) == 1
    assert reason == "natural-completion"


async def test_missing_model_id_allows_model_call(tmp_path: Path) -> None:
    model = _CountingModel(ScriptedTurn(increments=[TextIncrement(text="called")]))

    _, reason = await _run_host(
        RuntimeConfig(
            model=model,
            pricing_table=_table(input_rate="0", output_rate="1"),
            per_message_usd=Decimal("0"),
            pre_turn_max_output_tokens=2,
        ),
        tmp_path,
    )

    assert len(model.calls) == 1
    assert reason == "natural-completion"


async def test_no_active_cap_allows_model_call(tmp_path: Path) -> None:
    model = _CountingModel(ScriptedTurn(increments=[TextIncrement(text="called")]))
    checker = _checker(
        table=_table(input_rate="0", output_rate="1"),
        pre_turn_max_output_tokens=2,
    )

    events, _ = await _run(model, tmp_path, budget_checker=checker)

    assert len(model.calls) == 1
    assert _reasons(events) == ["natural-completion"]


async def test_unpriced_model_allows_model_call(tmp_path: Path) -> None:
    model = _CountingModel(ScriptedTurn(increments=[TextIncrement(text="called")]))
    checker = _checker(
        per_message=Decimal("0"),
        table=_table(input_rate="0", output_rate="1", model="priced-model"),
        model_id="unpriced-model",
        pre_turn_max_output_tokens=2,
    )

    events, _ = await _run(model, tmp_path, budget_checker=checker)

    assert len(model.calls) == 1
    assert _reasons(events) == ["natural-completion"]


async def test_pre_turn_refusal_reuses_budget_contract_without_cancelled(
    tmp_path: Path,
) -> None:
    assert SCHEMA_VERSION == 1
    model = _CountingModel(
        ScriptedTurn(increments=[TextIncrement(text="should not stream")])
    )
    checker = _checker(
        per_message=Decimal("1"),
        table=_table(input_rate="0", output_rate="1"),
        pre_turn_max_output_tokens=2,
    )

    events, history = await _run(model, tmp_path, budget_checker=checker)

    assert model.calls == []
    assert _reasons(events) == ["budget-exceeded"]
    assert "cancelled" not in _reasons(events)
    assert [entry.role for entry in history.snapshot()] == ["user"]


async def test_allowed_underestimate_still_uses_post_turn_budget_accounting(
    tmp_path: Path,
) -> None:
    model = _CountingModel(
        ScriptedTurn(
            increments=[TextIncrement(text="actual spend")],
            usage=_usage(0, 2),
        )
    )
    checker = _checker(
        per_message=Decimal("1"),
        table=_table(input_rate="0", output_rate="1"),
        pre_turn_max_output_tokens=0,
    )

    events, history = await _run(model, tmp_path, budget_checker=checker)

    assert len(model.calls) == 1
    assert _reasons(events) == ["budget-exceeded"]
    assert "actual spend" in _assistant_texts(history)


async def test_unset_pre_turn_max_output_tokens_skips_pre_turn_estimator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_if_called(request: ModelRequest) -> int:
        raise AssertionError("pre-turn estimator should be disabled")

    monkeypatch.setattr(loop_module, "estimate_request_tokens", fail_if_called)
    model = _CountingModel(ScriptedTurn(increments=[TextIncrement(text="called")]))
    checker = _checker(
        per_message=Decimal("0"),
        table=_table(input_rate="0", output_rate="1"),
    )

    events, _ = await _run(model, tmp_path, budget_checker=checker)

    assert len(model.calls) == 1
    assert _reasons(events) == ["natural-completion"]
