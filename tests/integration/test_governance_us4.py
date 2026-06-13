"""US4: compose policies and gate by capability (spec US4; SC-008)."""

from __future__ import annotations

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.governance import all_of, allow, as_decider, capability_policy, deny
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio

_ALLOW = as_decider(lambda the_call, the_descriptor: allow())


async def test_capability_requires_read_only() -> None:
    policy = capability_policy(require_read_only=True)
    assert isinstance(
        await decide(policy, call("w"), descriptor(read_only=False)), PolicyDeny
    )
    assert isinstance(
        await decide(policy, call("r"), descriptor(read_only=True)), PolicyAllow
    )


async def test_capability_requires_concurrency_safe() -> None:
    policy = capability_policy(require_concurrency_safe=True)
    assert isinstance(
        await decide(policy, call("t"), descriptor(concurrency_safe=False)), PolicyDeny
    )
    assert isinstance(
        await decide(policy, call("t"), descriptor(concurrency_safe=True)), PolicyAllow
    )


async def test_all_of_deny_wins() -> None:
    deny_p = as_decider(lambda the_call, the_descriptor: deny("blocked"))
    verdict = await decide(all_of(_ALLOW, deny_p), call("t"), descriptor())
    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason == "blocked"


async def test_all_of_all_allow() -> None:
    assert isinstance(
        await decide(all_of(_ALLOW, _ALLOW), call("t"), descriptor()), PolicyAllow
    )


async def test_all_of_empty_denies() -> None:
    assert isinstance(await decide(all_of(), call("t"), descriptor()), PolicyDeny)


async def test_all_of_short_circuits_on_first_deny() -> None:
    def boom(the_call: object, the_descriptor: object) -> object:
        raise RuntimeError("a later policy must not be reached after a deny")

    deny_p = as_decider(lambda the_call, the_descriptor: deny("first"))
    verdict = await decide(all_of(deny_p, as_decider(boom)), call("t"), descriptor())
    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason == "first"
