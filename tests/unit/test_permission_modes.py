"""Unit tests for named permission modes (spec 066; gap G10): the four presets
(acceptEdits / bypassPermissions / dontAsk / plan) build from the EXISTING 039 DSL,
are selected by ``RuntimeConfig.permission_mode``, feed the SAME ``rule_dsl_policy``
decider, and are default-off byte-identical. Host-free, deterministic.
"""

from __future__ import annotations

import pathlib

import pytest

from loopplane.approval import PolicyAllow, PolicyDeny
from loopplane.context import RunContext
from loopplane.governance import (
    PERMISSION_MODES,
    PermissionRuleSet,
    PermissionRuleSpec,
    all_of,
    per_run_permission_mode_policy,
    permission_mode_ruleset,
    rule_dsl_policy,
)
from loopplane.host import ConfigError, RuntimeConfig
from loopplane.host import config as host_config
from loopplane.host.assembly import _resolve_permission_mode
from loopplane.model import ScriptedModel
from tests.governance_helpers import call, decide_with_context, descriptor

pytestmark = pytest.mark.anyio


def _model() -> ScriptedModel:
    return ScriptedModel(script=[], context_capacity=1_000)


def _ctx() -> RunContext:
    return RunContext(session_id="s", working_scope=pathlib.Path("."))


# --- the builder: each mode's preset ------------------------------------------------


def test_accept_edits_allows_edit_tools_and_defaults_to_ask() -> None:
    rs = permission_mode_ruleset("acceptEdits", None)
    assert rs is not None and rs.default == "ask"
    allowed = {r.tool for r in rs.rules if r.decision == "allow"}
    assert allowed == {"write_file", "edit_file", "notebook_edit", "undo_file"}


def test_bypass_permissions_allows_everything() -> None:
    rs = permission_mode_ruleset("bypassPermissions", None)
    assert rs == PermissionRuleSet(rules=(), default="allow")


def test_dont_ask_standalone_is_allow_all() -> None:
    rs = permission_mode_ruleset("dontAsk", None)
    assert rs is not None and rs.rules == () and rs.default == "allow"


def test_dont_ask_rewrites_ask_to_allow_keeps_deny() -> None:
    explicit = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(tool="run_command", decision="ask"),
            PermissionRuleSpec(tool="write_file", decision="deny"),
        ),
        default="ask",
    )
    rs = permission_mode_ruleset("dontAsk", explicit)
    assert rs is not None and rs.default == "allow"
    by_tool = {r.tool: r.decision for r in rs.rules}
    assert by_tool == {"run_command": "allow", "write_file": "deny"}


def test_plan_mode_returns_no_ruleset() -> None:
    assert permission_mode_ruleset("plan", None) is None


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):
        permission_mode_ruleset("bogus", None)


# --- the decider posture (through the existing rule_dsl_policy) ----------------------


async def test_accept_edits_allows_a_write_through_the_decider() -> None:
    policy = rule_dsl_policy(permission_mode_ruleset("acceptEdits", None))  # type: ignore[arg-type]
    verdict = await decide_with_context(
        policy, call("write_file", path="x"), descriptor(name="write_file"), _ctx()
    )
    assert isinstance(verdict, PolicyAllow)


async def test_bypass_allows_an_arbitrary_tool_through_the_decider() -> None:
    policy = rule_dsl_policy(permission_mode_ruleset("bypassPermissions", None))  # type: ignore[arg-type]
    verdict = await decide_with_context(
        policy,
        call("run_command", command="ls"),
        descriptor(name="run_command"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyAllow)


async def test_dont_ask_keeps_deny_through_the_decider() -> None:
    explicit = PermissionRuleSet(
        rules=(PermissionRuleSpec(tool="write_file", decision="deny"),), default="ask"
    )
    policy = rule_dsl_policy(permission_mode_ruleset("dontAsk", explicit))  # type: ignore[arg-type]
    denied = await decide_with_context(
        policy, call("write_file", path="x"), descriptor(name="write_file"), _ctx()
    )
    assert isinstance(denied, PolicyDeny)
    allowed = await decide_with_context(
        policy,
        call("run_command", command="ls"),
        descriptor(name="run_command"),
        _ctx(),
    )
    assert isinstance(allowed, PolicyAllow)


# --- _resolve_permission_mode (assembly) + default-off byte-identity ----------------


def test_resolve_none_is_byte_identical() -> None:
    explicit = PermissionRuleSet(
        rules=(PermissionRuleSpec(tool="x", decision="deny"),), default="allow"
    )
    config = RuntimeConfig(model=_model(), permission_rules=explicit, plan_mode=True)
    rules, plan = _resolve_permission_mode(config)
    assert rules is explicit and plan is True


def test_resolve_plan_forces_plan_mode() -> None:
    config = RuntimeConfig(model=_model(), permission_mode="plan")
    rules, plan = _resolve_permission_mode(config)
    assert rules is None and plan is True


def test_resolve_accept_edits_builds_the_preset() -> None:
    config = RuntimeConfig(model=_model(), permission_mode="acceptEdits")
    rules, plan = _resolve_permission_mode(config)
    assert rules is not None and rules.default == "ask" and plan is False


# --- validate_config: known modes + precedence --------------------------------------


def test_unknown_mode_is_a_config_error() -> None:
    config = RuntimeConfig(model=_model(), permission_mode="bogus")
    with pytest.raises(ConfigError):
        host_config.validate_config(config)


def test_accept_edits_with_explicit_rules_is_ambiguous() -> None:
    config = RuntimeConfig(
        model=_model(),
        permission_mode="acceptEdits",
        permission_rules=PermissionRuleSet(default="allow"),
    )
    with pytest.raises(ConfigError):
        host_config.validate_config(config)


def test_dont_ask_with_explicit_rules_is_allowed() -> None:
    config = RuntimeConfig(
        model=_model(),
        permission_mode="dontAsk",
        permission_rules=PermissionRuleSet(
            rules=(PermissionRuleSpec(tool="x", decision="ask"),), default="ask"
        ),
    )
    host_config.validate_config(config)  # no raise


def test_known_modes_are_the_documented_four() -> None:
    assert set(PERMISSION_MODES) == {
        "acceptEdits",
        "bypassPermissions",
        "dontAsk",
        "plan",
    }


async def test_per_run_mode_policy_applies_only_the_host_approved_context_mode() -> (
    None
):
    policy = per_run_permission_mode_policy(("acceptEdits", "plan"))
    selected = RunContext(
        session_id="s",
        working_scope=pathlib.Path("."),
        permission_mode="acceptEdits",
    )
    default = _ctx()

    allowed = await decide_with_context(
        policy, call("write_file", path="x"), descriptor(name="write_file"), selected
    )
    unchanged = await decide_with_context(
        policy,
        call("write_file", path="x"),
        descriptor(name="write_file"),
        default,
    )

    assert isinstance(allowed, PolicyAllow)
    assert isinstance(unchanged, PolicyAllow)


async def test_per_run_mode_cannot_override_an_explicit_deny() -> None:
    selected = RunContext(
        session_id="s",
        working_scope=pathlib.Path("."),
        permission_mode="acceptEdits",
    )
    explicit_deny = rule_dsl_policy(
        PermissionRuleSet(
            rules=(PermissionRuleSpec(tool="write_file", decision="deny"),),
            default="allow",
        )
    )
    composed = all_of(explicit_deny, per_run_permission_mode_policy(("acceptEdits",)))

    verdict = await decide_with_context(
        composed,
        call("write_file", path="x"),
        descriptor(name="write_file"),
        selected,
    )

    assert isinstance(verdict, PolicyDeny)


async def test_per_run_mode_policy_denies_a_forged_or_bypassing_context_mode() -> None:
    policy = per_run_permission_mode_policy(("acceptEdits",))
    forged = RunContext(
        session_id="s",
        working_scope=pathlib.Path("."),
        permission_mode="bypassPermissions",
    )

    verdict = await decide_with_context(
        policy,
        call("run_command", command="whoami"),
        descriptor(name="run_command"),
        forged,
    )

    assert isinstance(verdict, PolicyDeny)
