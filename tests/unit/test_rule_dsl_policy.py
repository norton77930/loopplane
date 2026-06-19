"""Unit tests for the declarative permission rule DSL (spec 039): rule_dsl_policy
matches a call by its tool matcher AND every `match` pattern (arg-regex / path-glob),
combines deny-wins (deny > ask > allow), falls back to a top-level default, and returns
the existing PolicyVerdict — reusing the existing approval round-trip for `ask`.
Composed deny-wins + fail-closed through the existing governance combinators. Host-free,
deterministic (a scripted InteractionBroker for the `ask` path; no real reviewer/model).
"""

from __future__ import annotations

import pathlib

import anyio
import anyio.lowlevel
import pytest

from loopplane.approval import InteractionBroker, PolicyAllow, PolicyDeny
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.governance import (
    PermissionRuleSet,
    PermissionRuleSpec,
    all_of,
    allow,
    as_decider,
    rule_dsl_policy,
    safe_failure,
)
from tests.governance_helpers import call, decide, decide_with_context, descriptor

pytestmark = pytest.mark.anyio


def _ctx(broker: InteractionBroker | None = None) -> RunContext:
    return RunContext(
        session_id="s", working_scope=pathlib.Path("."), interactions=broker
    )


# --- US1: an arg-regex deny denies a matching call, allows a non-matching one --------


async def test_arg_regex_deny_denies_matching_command() -> None:
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="run_command", match={"command": "^rm -rf"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy,
        call("run_command", command="rm -rf /"),
        descriptor(name="run_command"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason


async def test_arg_regex_deny_allows_non_matching_command_via_default() -> None:
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="run_command", match={"command": "^rm -rf"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy,
        call("run_command", command="ls -la"),
        descriptor(name="run_command"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyAllow)


async def test_tool_matcher_gates_first() -> None:
    # The same deny rule on run_command does not touch a different tool.
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="run_command", match={"command": "^rm -rf"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy,
        call("read_file", command="rm -rf /"),
        descriptor(name="read_file"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyAllow)


async def test_fnmatch_tool_pattern_matches() -> None:
    # The tool matcher reuses the existing fnmatch syntax (e.g. mcp:*).
    rules = PermissionRuleSet(
        rules=(PermissionRuleSpec(tool="mcp:*", decision="deny"),), default="allow"
    )
    policy = rule_dsl_policy(rules)
    matched = await decide_with_context(
        policy, call("mcp:server:tool"), descriptor(name="mcp:server:tool"), _ctx()
    )
    unmatched = await decide_with_context(
        policy, call("read_file"), descriptor(name="read_file"), _ctx()
    )
    assert isinstance(matched, PolicyDeny)
    assert isinstance(unmatched, PolicyAllow)


# --- US2: a path-glob deny denies a matching path; an allow rule allows --------------


async def test_path_glob_deny_denies_matching_path() -> None:
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="write_file", match={"path": "**/secrets/**"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy,
        call("write_file", path="app/secrets/key.pem"),
        descriptor(name="write_file"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyDeny)


async def test_path_glob_deny_allows_non_matching_path_via_default() -> None:
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="write_file", match={"path": "**/secrets/**"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy,
        call("write_file", path="app/notes.md"),
        descriptor(name="write_file"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyAllow)


async def test_path_glob_normalizes_windows_separators() -> None:
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="write_file", match={"path": "**/secrets/**"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy,
        call("write_file", path="app\\secrets\\key.pem"),
        descriptor(name="write_file"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyDeny)


async def test_allow_rule_allows_its_tool() -> None:
    rules = PermissionRuleSet(
        rules=(PermissionRuleSpec(tool="read_file", decision="allow"),),
        default="deny",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy, call("read_file", path="x"), descriptor(name="read_file"), _ctx()
    )
    assert isinstance(verdict, PolicyAllow)


# --- matching edge cases ------------------------------------------------------------


async def test_match_on_absent_field_does_not_match() -> None:
    # A deny rule keyed on `command` does not match a call lacking `command`; it falls
    # through to the default (a deny gates a specific present invocation, not the tool).
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(
                tool="run_command", match={"command": "^rm"}, decision="deny"
            ),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy, call("run_command"), descriptor(name="run_command"), _ctx()
    )
    assert isinstance(verdict, PolicyAllow)


async def test_non_string_field_is_coerced_for_the_regex() -> None:
    rules = PermissionRuleSet(
        rules=(PermissionRuleSpec(tool="t", match={"n": "^42$"}, decision="deny"),),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    matched = await decide_with_context(
        policy, call("t", n=42), descriptor(name="t"), _ctx()
    )
    unmatched = await decide_with_context(
        policy, call("t", n=7), descriptor(name="t"), _ctx()
    )
    assert isinstance(matched, PolicyDeny)
    assert isinstance(unmatched, PolicyAllow)


# --- US5: empty / absent rules are a no-op ------------------------------------------


async def test_empty_policy_decides_identically_to_no_policy() -> None:
    # An empty rule set with default=allow composed with another decider equals that
    # decider alone for any call (proving empty == no policy; US5).
    other = as_decider(lambda _c, _d: allow())
    empty = rule_dsl_policy(PermissionRuleSet(default="allow"))
    composed = all_of(empty, other)
    only_other = await decide(other, call("write_file"), descriptor(name="write_file"))
    both = await decide(composed, call("write_file"), descriptor(name="write_file"))
    assert isinstance(only_other, PolicyAllow)
    assert isinstance(both, PolicyAllow)


# --- US3: the ask round-trip reuses the existing approval path -----------------------


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    def of_type(self, event_type: str) -> list[RuntimeEvent]:
        return [event for event in self.events if event.type == event_type]


def _broker(sink: _Collector) -> InteractionBroker:
    emitter = EventEmitter(session_id="s", sequencer=EventSequencer(), sink=sink)
    broker = InteractionBroker(emitter=emitter)
    broker.attach_reviewer()
    return broker


async def _decide_with_resolution(
    policy: object,
    the_call: object,
    the_descriptor: object,
    context: RunContext,
    sink: _Collector,
    *,
    decision: str,
) -> object:
    """Drive the decider while concurrently resolving its one approval request (the
    established broker round-trip pattern from tests/contract/test_approval.py)."""

    broker = context.interactions
    assert broker is not None
    result: list[object] = []

    async def run() -> None:
        result.append(await policy(the_call, the_descriptor, context, None))  # type: ignore[operator]

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(run)
        with anyio.fail_after(5):
            while not sink.of_type("approval-requested"):
                await anyio.lowlevel.checkpoint()
        request_id = sink.of_type("approval-requested")[0].payload.request_id
        assert broker.resolve_approval(request_id, decision=decision, scope="once")  # type: ignore[arg-type]

    return result[0]


async def test_ask_rule_approve_yields_allow() -> None:
    sink = _Collector()
    context = _ctx(_broker(sink))
    policy = rule_dsl_policy(
        PermissionRuleSet(rules=(PermissionRuleSpec(tool="echo", decision="ask"),))
    )
    verdict = await _decide_with_resolution(
        policy, call("echo"), descriptor(name="echo"), context, sink, decision="allow"
    )
    assert isinstance(verdict, PolicyAllow)


async def test_ask_rule_reject_yields_deny() -> None:
    sink = _Collector()
    context = _ctx(_broker(sink))
    policy = rule_dsl_policy(
        PermissionRuleSet(rules=(PermissionRuleSpec(tool="echo", decision="ask"),))
    )
    verdict = await _decide_with_resolution(
        policy, call("echo"), descriptor(name="echo"), context, sink, decision="deny"
    )
    assert isinstance(verdict, PolicyDeny)


async def test_ask_rule_without_a_reviewer_denies() -> None:
    # No broker attached → ask resolves as deny (no reviewer); never a silent allow.
    policy = rule_dsl_policy(
        PermissionRuleSet(rules=(PermissionRuleSpec(tool="echo", decision="ask"),))
    )
    verdict = await decide_with_context(
        policy, call("echo"), descriptor(name="echo"), _ctx(broker=None)
    )
    assert isinstance(verdict, PolicyDeny)


async def test_default_ask_escalates_on_no_match() -> None:
    sink = _Collector()
    context = _ctx(_broker(sink))
    # No rule matches `echo`; the default is ask → it escalates.
    policy = rule_dsl_policy(
        PermissionRuleSet(
            rules=(PermissionRuleSpec(tool="other", decision="deny"),), default="ask"
        )
    )
    verdict = await _decide_with_resolution(
        policy, call("echo"), descriptor(name="echo"), context, sink, decision="allow"
    )
    assert isinstance(verdict, PolicyAllow)


# --- US3: precedence + default ------------------------------------------------------


async def test_deny_wins_when_rules_conflict() -> None:
    rules = PermissionRuleSet(
        rules=(
            PermissionRuleSpec(tool="echo", decision="allow"),
            PermissionRuleSpec(tool="echo", decision="deny"),
        ),
        default="allow",
    )
    policy = rule_dsl_policy(rules)
    verdict = await decide_with_context(
        policy, call("echo"), descriptor(name="echo"), _ctx()
    )
    assert isinstance(verdict, PolicyDeny)


async def test_default_applies_on_no_match() -> None:
    deny_default = rule_dsl_policy(
        PermissionRuleSet(
            rules=(PermissionRuleSpec(tool="other", decision="allow"),), default="deny"
        )
    )
    allow_default = rule_dsl_policy(
        PermissionRuleSet(
            rules=(PermissionRuleSpec(tool="other", decision="allow"),), default="allow"
        )
    )
    denied = await decide_with_context(
        deny_default, call("echo"), descriptor(name="echo"), _ctx()
    )
    allowed = await decide_with_context(
        allow_default, call("echo"), descriptor(name="echo"), _ctx()
    )
    assert isinstance(denied, PolicyDeny)
    assert isinstance(allowed, PolicyAllow)


# --- US4: invalid regex is a config error; the composed chain fails closed -----------


def test_invalid_regex_is_a_config_error_at_construction() -> None:
    with pytest.raises(Exception):  # noqa: B017,PT011 - a clear config error, not a silent allow
        rule_dsl_policy(
            PermissionRuleSet(
                rules=(
                    PermissionRuleSpec(
                        tool="run_command", match={"command": "["}, decision="deny"
                    ),
                )
            )
        )


async def test_fail_closed_when_a_composed_policy_raises() -> None:
    async def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("policy exploded")

    composed = safe_failure(
        all_of(
            rule_dsl_policy(
                PermissionRuleSet(
                    rules=(PermissionRuleSpec(tool="echo", decision="allow"),)
                )
            ),
            boom,
        )
    )
    verdict = await decide_with_context(
        composed, call("echo"), descriptor(name="echo"), _ctx()
    )
    assert isinstance(verdict, PolicyDeny)


async def test_deny_wins_in_the_composed_chain() -> None:
    # The DSL denies a matching call; an allow-all after it cannot rescue.
    composed = all_of(
        rule_dsl_policy(
            PermissionRuleSet(
                rules=(
                    PermissionRuleSpec(
                        tool="run_command",
                        match={"command": "^rm -rf"},
                        decision="deny",
                    ),
                )
            )
        ),
        as_decider(lambda _c, _d: allow()),
    )
    verdict = await decide_with_context(
        composed,
        call("run_command", command="rm -rf /"),
        descriptor(name="run_command"),
        _ctx(),
    )
    assert isinstance(verdict, PolicyDeny)
