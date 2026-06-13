"""US3: bound cost and per-tool quota (spec US3; SC-007)."""

from __future__ import annotations

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.governance import CostModel, budget_policy, quota_policy
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio


async def test_cost_model() -> None:
    model = CostModel({"expensive": 5})
    assert model.cost("expensive") == 5
    assert model.cost("other") == 1
    assert CostModel({}, default=3).cost("x") == 3


async def test_budget_allows_until_exhausted_then_denies() -> None:
    policy = budget_policy(3)
    for _ in range(3):
        assert isinstance(await decide(policy, call("t"), descriptor()), PolicyAllow)
    assert isinstance(await decide(policy, call("t"), descriptor()), PolicyDeny)
    assert policy.spent == 3


async def test_budget_respects_cost_weights() -> None:
    policy = budget_policy(10, cost_model=CostModel({"big": 4}))
    assert isinstance(await decide(policy, call("big"), descriptor()), PolicyAllow)
    assert isinstance(await decide(policy, call("big"), descriptor()), PolicyAllow)
    assert isinstance(await decide(policy, call("big"), descriptor()), PolicyDeny)
    assert policy.spent == 8


async def test_quota_enforces_per_tool_limit() -> None:
    policy = quota_policy({"fetch": 2})
    assert isinstance(await decide(policy, call("fetch"), descriptor()), PolicyAllow)
    assert isinstance(await decide(policy, call("fetch"), descriptor()), PolicyAllow)
    assert isinstance(await decide(policy, call("fetch"), descriptor()), PolicyDeny)
    for _ in range(5):
        assert isinstance(await decide(policy, call("free"), descriptor()), PolicyAllow)


async def test_budget_is_deterministic() -> None:
    sequence = ["a", "b", "c"]
    first: list[type] = []
    second: list[type] = []
    policy_a = budget_policy(2)
    policy_b = budget_policy(2)
    for name in sequence:
        first.append(type(await decide(policy_a, call(name), descriptor())))
    for name in sequence:
        second.append(type(await decide(policy_b, call(name), descriptor())))
    assert first == second
