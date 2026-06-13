"""US5: fail safe and apply a named sandbox profile (spec US5; SC-003)."""

from __future__ import annotations

import pytest

from loopplane.approval import PermissionRule, PolicyAllow, PolicyDeny
from loopplane.governance import (
    allow,
    as_decider,
    capability_policy,
    default_deny,
    permission_policy,
    safe_failure,
    sandbox_profile,
)
from tests.governance_helpers import call, decide, descriptor

pytestmark = pytest.mark.anyio


def _boom(the_call: object, the_descriptor: object) -> object:
    raise RuntimeError("policy boom")


async def test_safe_failure_maps_raise_to_deny() -> None:
    wrapped = safe_failure(as_decider(_boom))
    assert isinstance(await decide(wrapped, call("t"), descriptor()), PolicyDeny)


async def test_safe_failure_passes_through_a_normal_verdict() -> None:
    wrapped = safe_failure(as_decider(lambda the_call, the_descriptor: allow()))
    assert isinstance(await decide(wrapped, call("t"), descriptor()), PolicyAllow)


async def test_default_deny_always_denies() -> None:
    assert isinstance(await decide(default_deny(), call("t"), descriptor()), PolicyDeny)


async def test_sandbox_profile_composes_deny_wins() -> None:
    perm = permission_policy(
        [PermissionRule(matcher="read", effect="allow", scope="project")]
    )
    cap = capability_policy(require_read_only=True)
    profile = sandbox_profile(permission=perm, capability=cap)
    # allowed by permission + read-only ⇒ allow
    assert isinstance(
        await decide(profile, call("read"), descriptor(read_only=True)), PolicyAllow
    )
    # allowed by permission but not read-only ⇒ capability denies (deny-wins)
    assert isinstance(
        await decide(profile, call("read"), descriptor(read_only=False)), PolicyDeny
    )
    # not permitted ⇒ permission denies
    assert isinstance(
        await decide(profile, call("write"), descriptor(read_only=True)), PolicyDeny
    )


async def test_sandbox_profile_is_fail_safe() -> None:
    profile = sandbox_profile(permission=as_decider(_boom))
    assert isinstance(await decide(profile, call("t"), descriptor()), PolicyDeny)


async def test_empty_sandbox_profile_denies() -> None:
    assert isinstance(
        await decide(sandbox_profile(), call("t"), descriptor()), PolicyDeny
    )
