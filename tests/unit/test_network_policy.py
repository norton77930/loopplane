"""Unit tests for the network-egress policy (spec 034): network_policy denies a
network-flagged tool unless the host opts in, composed deny-wins + fail-closed
through the existing governance combinators. Host-free, deterministic.
"""

from __future__ import annotations

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.governance import all_of, allow, as_decider, network_policy, safe_failure
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio


def _net(name: str = "web_fetch") -> object:
    return descriptor(name=name)


async def test_network_tool_denied_when_egress_disabled() -> None:
    policy = network_policy(allow_network=False)
    verdict = await decide(
        policy, call("web_fetch"), descriptor(name="web_fetch", network=True)
    )
    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason


async def test_network_tool_allowed_when_egress_enabled() -> None:
    policy = network_policy(allow_network=True)
    verdict = await decide(
        policy, call("web_fetch"), descriptor(name="web_fetch", network=True)
    )
    assert isinstance(verdict, PolicyAllow)


async def test_non_network_tool_is_never_denied_by_the_policy() -> None:
    # Even with egress disabled, a non-network tool passes this policy untouched.
    disabled = network_policy(allow_network=False)
    enabled = network_policy(allow_network=True)
    plain = descriptor(name="read_file", network=False)
    assert isinstance(await decide(disabled, call("read_file"), plain), PolicyAllow)
    assert isinstance(await decide(enabled, call("read_file"), plain), PolicyAllow)


async def test_fail_closed_when_a_composed_policy_raises() -> None:
    async def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("policy exploded")

    composed = safe_failure(all_of(network_policy(allow_network=True), boom))
    verdict = await decide(
        composed, call("web_fetch"), descriptor(name="web_fetch", network=True)
    )
    assert isinstance(verdict, PolicyDeny)


async def test_deny_wins_in_the_composed_chain() -> None:
    # network_policy denies (egress off); an allow-all after it cannot rescue.
    composed = all_of(
        network_policy(allow_network=False),
        as_decider(lambda _c, _d: allow()),
    )
    verdict = await decide(
        composed, call("web_fetch"), descriptor(name="web_fetch", network=True)
    )
    assert isinstance(verdict, PolicyDeny)
