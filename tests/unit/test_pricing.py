"""Server-side pricing tests (spec 053). Offline + deterministic; exact decimals."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from loopplane.model.boundary import TokenUsage
from loopplane.pricing import PricingRate, PricingTable


def _table() -> PricingTable:
    return PricingTable(
        rates={"m1": PricingRate(Decimal("0.000003"), Decimal("0.000015"))}
    )


def test_cost_is_exact_for_a_priced_model() -> None:
    cost = _table().cost(TokenUsage(input_tokens=1000, output_tokens=500), "m1")
    assert cost == Decimal("0.000003") * 1000 + Decimal("0.000015") * 500
    assert cost == Decimal("0.0105")


def test_cost_is_exact_decimal_no_float_drift() -> None:
    # Large counts + fractional per-token rates: exact decimal, no float error.
    usage = TokenUsage(input_tokens=1_234_567, output_tokens=7_654_321)
    table = PricingTable(
        rates={"m": PricingRate(Decimal("0.0000011"), Decimal("0.0000022"))}
    )
    cost = table.cost(usage, "m")
    assert cost == (Decimal("0.0000011") * 1_234_567 + Decimal("0.0000022") * 7_654_321)
    assert isinstance(cost, Decimal)


def test_unknown_model_returns_none() -> None:
    assert _table().cost(TokenUsage(input_tokens=10, output_tokens=10), "nope") is None


def test_zero_usage_is_zero() -> None:
    assert _table().cost(TokenUsage(), "m1") == Decimal("0")


def test_zero_rates_is_zero() -> None:
    table = PricingTable(rates={"m": PricingRate(Decimal("0"), Decimal("0"))})
    cost = table.cost(TokenUsage(input_tokens=100, output_tokens=100), "m")
    assert cost == Decimal("0")


def test_value_objects_are_immutable() -> None:
    rate = PricingRate(Decimal("1"), Decimal("2"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        rate.input_rate = Decimal("9")
    with pytest.raises(dataclasses.FrozenInstanceError):
        _table().rates = {}


def test_only_input_and_output_are_priced() -> None:
    # cached / reasoning tokens are NOT priced in v1 (input + output only).
    usage = TokenUsage(
        input_tokens=3, output_tokens=4, cached_tokens=99, reasoning_tokens=99
    )
    table = PricingTable(rates={"m": PricingRate(Decimal("2"), Decimal("5"))})
    assert table.cost(usage, "m") == Decimal("3") * 2 + Decimal("4") * 5  # 26
