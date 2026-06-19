"""The declarative permission rule DSL — host-suppliable allow/deny/ask rules enforced
at the Tool Gateway decide stage (spec 039; FR-001–FR-009).

A host supplies an ordered :class:`PermissionRuleSet`: each :class:`PermissionRuleSpec`
names a ``tool`` (an exact name or an ``fnmatch`` pattern in the **existing** matcher
syntax, e.g. ``mcp:*``), an optional ``match`` (a map of input-field name → pattern: a
**path-glob** for path-shaped fields, a **regex** otherwise), and a ``decision`` of
``allow`` | ``deny`` | ``ask``; a top-level ``default`` decision applies on no match.

:func:`rule_dsl_policy` returns a decide-stage decider that selects the rules whose
``tool`` matcher **and** every ``match`` pattern match the call, combines them with a
SAFE precedence (**deny > ask > allow** — reusing the deny-wins semantics of
``resolve_rules``), falls back to ``default``, and returns the **existing**
``PolicyVerdict``: ``allow`` → :class:`PolicyAllow`; ``deny`` → :class:`PolicyDeny`;
``ask`` → it **reuses the existing approval round-trip** (the same
``InteractionBroker.request_approval`` the Human Approval boundary uses) and maps the
human's resolution to allow / deny — no new verdict type, no new approval mechanism.

Regexes and path-globs are **compiled eagerly at construction**, so a malformed pattern
is a clear config error there (fail-closed), never a silently-allowed call at decide
time. Compose it through the **existing** combinators (``all_of`` deny-wins +
``safe_failure`` fail-closed); this adds no new Tool Gateway stage (Constitution V).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from fnmatch import fnmatchcase, translate
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from loopplane.governance.base import allow, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.context import RunContext
    from loopplane.events.emitter import EventEmitter
    from loopplane.model import ToolCallRequest, ToolDescriptor

RuleDecision = Literal["allow", "deny", "ask"]

# Field names treated as paths (their `match` value is a path-glob, not a regex). `path`
# is the input field every baseline file tool uses (write_file / read_file / edit_file).
_PATH_FIELDS: frozenset[str] = frozenset({"path", "file"})

_SUMMARY_LIMIT = 200


def _is_path_field(field: str) -> bool:
    return field in _PATH_FIELDS or field.endswith("_path")


class PermissionRuleSpec(BaseModel):
    """One declarative permission rule (public-safe: a tool name + patterns + a
    decision; never a secret)."""

    model_config = ConfigDict(frozen=True)

    tool: str
    match: Mapping[str, str] | None = None
    decision: RuleDecision


class PermissionRuleSet(BaseModel):
    """A host-suppliable rule set: an ordered ``rules`` collection + the ``default``
    decision applied when no rule matches. Default ``allow``, so an empty set is a
    no-op."""

    model_config = ConfigDict(frozen=True)

    rules: tuple[PermissionRuleSpec, ...] = ()
    default: RuleDecision = "allow"


class _CompiledRule:
    """A rule with its ``match`` patterns compiled (eagerly, at policy construction)."""

    __slots__ = ("tool", "match", "decision")

    def __init__(self, rule: PermissionRuleSpec) -> None:
        self.tool = rule.tool
        self.decision: RuleDecision = rule.decision
        # field -> (compiled pattern, is_path_glob)
        self.match: dict[str, tuple[re.Pattern[str], bool]] = {}
        for field, pattern in (rule.match or {}).items():
            is_path = _is_path_field(field)
            try:
                compiled = (
                    re.compile(translate(pattern)) if is_path else re.compile(pattern)
                )
            except (
                re.error
            ) as exc:  # eager, fail-closed (FR-005) — never a silent allow
                raise ValueError(
                    f"invalid {'path-glob' if is_path else 'regex'} for rule "
                    f"tool {rule.tool!r} field {field!r}: {exc}"
                ) from exc
            self.match[field] = (compiled, is_path)

    def matches(self, call: ToolCallRequest) -> bool:
        if not fnmatchcase(call.tool_name, self.tool):
            return False
        for field, (pattern, is_path) in self.match.items():
            if field not in call.input:
                return False
            value = str(call.input[field])
            if is_path:
                value = value.replace("\\", "/")
            if pattern.search(value) is None:
                return False
        return True


def _combine(matched: Sequence[_CompiledRule], default: RuleDecision) -> RuleDecision:
    """Combine the matching rules' decisions: deny > ask > allow; no match → ``default``
    (the most-restrictive matching decision wins; reduces to ``resolve_rules`` deny-wins
    when matching rules are name-only allow/deny)."""

    if not matched:
        return default
    decisions = {rule.decision for rule in matched}
    if "deny" in decisions:
        return "deny"
    if "ask" in decisions:
        return "ask"
    return "allow"


def _summarize_input(call: ToolCallRequest) -> str:
    summary = ", ".join(f"{key}={value!r}" for key, value in call.input.items())
    return summary[:_SUMMARY_LIMIT]


def rule_dsl_policy(rules: PermissionRuleSet) -> PolicyDecider:
    """Decide a call by the declarative ``rules``: select the rules whose ``tool``
    matcher and every ``match`` pattern match, combine deny > ask > allow, fall back to
    ``rules.default``; ``allow`` → allow, ``deny`` → deny, ``ask`` → reuse the existing
    approval round-trip (FR-002, FR-003). ``match`` patterns are compiled here, so an
    invalid pattern raises a clear config error at construction (FR-005)."""

    compiled = [_CompiledRule(rule) for rule in rules.rules]
    default = rules.default

    async def decider(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        matched = [rule for rule in compiled if rule.matches(call)]
        decision = _combine(matched, default)
        if decision == "allow":
            return allow()
        if decision == "deny":
            return deny(f"tool {call.tool_name!r} denied by permission rule")
        return await _escalate(call, context)

    return decider


async def _escalate(call: ToolCallRequest, context: RunContext) -> PolicyVerdict:
    """Reuse the existing approval round-trip for an ``ask`` decision (the same path
    the Human Approval boundary uses): request a human decision and map it to allow /
    deny; no reviewer attached → deny (never a hang, never a silent allow)."""

    broker = context.interactions
    if broker is None or not broker.reviewer_attached:
        return deny(f"no reviewer available to approve {call.tool_name!r}")
    resolution = await broker.request_approval(
        call_id=call.call_id,
        tool_name=call.tool_name,
        input_summary=_summarize_input(call),
    )
    if resolution.decision == "allow":
        return allow()
    return deny(resolution.reason or f"{call.tool_name!r} denied by reviewer")
