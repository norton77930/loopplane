"""US2: restrict tool arguments to an allowed path root (spec US2; SC-004)."""

from __future__ import annotations

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.governance import path_policy
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio


async def test_contained_path_is_allowed() -> None:
    policy = path_policy("sandbox", key="path")
    assert isinstance(
        await decide(policy, call("read", path="sandbox/file.txt"), descriptor()),
        PolicyAllow,
    )
    assert isinstance(
        await decide(policy, call("read", path="file.txt"), descriptor()), PolicyAllow
    )


async def test_traversal_escape_is_denied() -> None:
    policy = path_policy("sandbox")
    assert isinstance(
        await decide(policy, call("read", path="../escape"), descriptor()), PolicyDeny
    )
    assert isinstance(
        await decide(policy, call("read", path="deep/../../escape"), descriptor()),
        PolicyDeny,
    )


async def test_absolute_escape_is_denied() -> None:
    policy = path_policy("sandbox")
    assert isinstance(
        await decide(policy, call("read", path="/outside/file"), descriptor()),
        PolicyDeny,
    )


async def test_missing_or_malformed_path_is_denied() -> None:
    policy = path_policy("sandbox")
    assert isinstance(await decide(policy, call("read"), descriptor()), PolicyDeny)
    assert isinstance(
        await decide(policy, call("read", path=123), descriptor()), PolicyDeny
    )
    assert isinstance(
        await decide(policy, call("read", path=""), descriptor()), PolicyDeny
    )


async def test_path_policy_is_deterministic() -> None:
    policy = path_policy("sandbox")
    contained = call("read", path="sandbox/x")
    first = await decide(policy, contained, descriptor())
    second = await decide(policy, contained, descriptor())
    assert type(first) is type(second)
