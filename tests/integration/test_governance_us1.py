"""US1: gate tool calls by permission rules (spec US1; SC-001/003/009)."""

from __future__ import annotations

import pytest

from loopplane.approval import PermissionRule, PolicyAllow, PolicyDeny, resolve_rules
from loopplane.governance import permission_policy
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio


def _rule(matcher: str, effect: str, scope: str = "project") -> PermissionRule:
    return PermissionRule(matcher=matcher, effect=effect, scope=scope)


async def test_allowed_tool_is_allowed() -> None:
    policy = permission_policy([_rule("read", "allow")])
    assert isinstance(await decide(policy, call("read"), descriptor()), PolicyAllow)


async def test_denied_tool_is_denied() -> None:
    policy = permission_policy([_rule("write", "deny")])
    verdict = await decide(policy, call("write"), descriptor())
    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason


async def test_unmatched_defaults_to_deny() -> None:
    policy = permission_policy([_rule("read", "allow")])
    assert isinstance(await decide(policy, call("other"), descriptor()), PolicyDeny)


async def test_default_allow_for_unmatched() -> None:
    policy = permission_policy([], default="allow")
    assert isinstance(await decide(policy, call("anything"), descriptor()), PolicyAllow)


async def test_verdict_matches_resolve_rules() -> None:
    rules = [_rule("read*", "allow"), _rule("read_secret", "deny", "session-local")]
    policy = permission_policy(rules)
    for name in ("read_file", "read_secret", "write"):
        effect = resolve_rules(rules, name)
        verdict = await decide(policy, call(name), descriptor())
        if effect == "allow":
            assert isinstance(verdict, PolicyAllow)
        else:  # "deny" or no-match -> default deny
            assert isinstance(verdict, PolicyDeny)
