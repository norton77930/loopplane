"""Foundational unit tests for governance (009): the verdict helpers and the
decider adapter. Host-free.
"""

from __future__ import annotations

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.governance import allow, as_decider, deny, path_policy
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio


async def test_allow_and_deny_helpers() -> None:
    assert isinstance(allow(), PolicyAllow)
    verdict = deny("nope")
    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason == "nope"


async def test_as_decider_returns_the_simple_verdict() -> None:
    policy = as_decider(
        lambda the_call, the_descriptor: (
            deny("blocked") if the_call.tool_name == "x" else allow()
        )
    )
    assert isinstance(await decide(policy, call("x"), descriptor()), PolicyDeny)
    assert isinstance(await decide(policy, call("y"), descriptor()), PolicyAllow)


async def test_as_decider_ignores_context_and_emitter() -> None:
    # decide() passes None for run context / emitter; the adapter must not touch them.
    policy = as_decider(lambda the_call, the_descriptor: allow())
    assert isinstance(await decide(policy, call("any"), descriptor()), PolicyAllow)


async def test_path_policy_root_slash_contains_children_and_blocks_escape() -> None:
    root = path_policy("/")
    assert isinstance(
        await decide(root, call("read", path="/"), descriptor()), PolicyAllow
    )
    assert isinstance(
        await decide(root, call("read", path="/etc/passwd"), descriptor()),
        PolicyAllow,
    )
    # Two leading slashes are a different POSIX path and are not under "/".
    assert isinstance(
        await decide(root, call("read", path="//etc/passwd"), descriptor()),
        PolicyDeny,
    )
    sandbox = path_policy("sandbox")
    assert isinstance(
        await decide(sandbox, call("read", path="../etc/passwd"), descriptor()),
        PolicyDeny,
    )
