"""Unit tests for the plan-mode policy (spec 038): while plan mode is active the
decider denies non-read-only tools (except the allowlist) and allows read-only tools;
a no-op when inactive/absent; composed deny-wins + fail-closed through the existing
governance combinators. Host-free, deterministic.
"""

from __future__ import annotations

import pathlib

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.context import PlanModeState, RunContext
from loopplane.governance import (
    all_of,
    allow,
    as_decider,
    plan_mode_policy,
    safe_failure,
)
from tests.governance_helpers import call, decide_with_context, descriptor

pytestmark = pytest.mark.anyio

_READ_ONLY_TOOLS = ("read_file", "grep", "glob_files", "search_files")
_ALLOWLISTED_TOOLS = ("ask_user", "exit_plan_mode")
_MUTATING_TOOLS = ("write_file", "edit_file", "run_command")


def _ctx(state: PlanModeState | None) -> RunContext:
    return RunContext(session_id="s", working_scope=pathlib.Path("."), plan_mode=state)


async def test_active_denies_non_read_only_tools() -> None:
    policy = plan_mode_policy()
    ctx = _ctx(PlanModeState(active=True))
    for name in _MUTATING_TOOLS:
        verdict = await decide_with_context(
            policy, call(name), descriptor(name=name, read_only=False), ctx
        )
        assert isinstance(verdict, PolicyDeny), name
        assert verdict.reason


async def test_active_allows_read_only_tools() -> None:
    policy = plan_mode_policy()
    ctx = _ctx(PlanModeState(active=True))
    for name in _READ_ONLY_TOOLS:
        verdict = await decide_with_context(
            policy, call(name), descriptor(name=name, read_only=True), ctx
        )
        assert isinstance(verdict, PolicyAllow), name


async def test_active_allows_the_allowlist_even_though_not_read_only() -> None:
    policy = plan_mode_policy()
    ctx = _ctx(PlanModeState(active=True))
    for name in _ALLOWLISTED_TOOLS:
        verdict = await decide_with_context(
            policy, call(name), descriptor(name=name, read_only=False), ctx
        )
        assert isinstance(verdict, PolicyAllow), name


async def test_inactive_holder_is_a_no_op() -> None:
    policy = plan_mode_policy()
    ctx = _ctx(PlanModeState(active=False))
    verdict = await decide_with_context(
        policy, call("write_file"), descriptor(name="write_file", read_only=False), ctx
    )
    assert isinstance(verdict, PolicyAllow)


async def test_absent_holder_is_a_no_op() -> None:
    policy = plan_mode_policy()
    ctx = _ctx(None)
    verdict = await decide_with_context(
        policy, call("write_file"), descriptor(name="write_file", read_only=False), ctx
    )
    assert isinstance(verdict, PolicyAllow)


async def test_explicit_state_argument_overrides_the_context_holder() -> None:
    # An explicit active state denies even though the context holder is absent.
    policy = plan_mode_policy(PlanModeState(active=True))
    ctx = _ctx(None)
    verdict = await decide_with_context(
        policy, call("write_file"), descriptor(name="write_file", read_only=False), ctx
    )
    assert isinstance(verdict, PolicyDeny)

    # An explicit inactive state allows even though the context holder is active.
    off = plan_mode_policy(PlanModeState(active=False))
    ctx_active = _ctx(PlanModeState(active=True))
    write = descriptor(name="write_file", read_only=False)
    verdict_off = await decide_with_context(off, call("write_file"), write, ctx_active)
    assert isinstance(verdict_off, PolicyAllow)


async def test_fail_closed_when_a_composed_policy_raises() -> None:
    async def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("policy exploded")

    composed = safe_failure(all_of(plan_mode_policy(PlanModeState(active=True)), boom))
    verdict = await decide_with_context(
        composed,
        call("read_file"),
        descriptor(name="read_file", read_only=True),
        _ctx(None),
    )
    assert isinstance(verdict, PolicyDeny)


async def test_deny_wins_in_the_composed_chain() -> None:
    # plan_mode denies write_file (active); an allow-all after it cannot rescue.
    composed = all_of(
        plan_mode_policy(PlanModeState(active=True)),
        as_decider(lambda _c, _d: allow()),
    )
    verdict = await decide_with_context(
        composed,
        call("write_file"),
        descriptor(name="write_file", read_only=False),
        _ctx(None),
    )
    assert isinstance(verdict, PolicyDeny)


async def test_off_policy_decides_identically_to_no_policy() -> None:
    # An off/absent plan-mode policy composed with another decider equals that decider
    # alone for a non-read-only tool (proving off == no policy; US4).
    other = as_decider(lambda _c, _d: allow())
    with_off = all_of(plan_mode_policy(PlanModeState(active=False)), other)
    write = descriptor(name="write_file", read_only=False)

    only_other = await decide_with_context(other, call("write_file"), write, _ctx(None))
    composed = await decide_with_context(
        with_off, call("write_file"), write, _ctx(None)
    )
    assert isinstance(only_other, PolicyAllow)
    assert isinstance(composed, PolicyAllow)
