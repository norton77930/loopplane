"""Persistent permission rules with deterministic precedence (FR-114).

A more local scope overrides a broader scope (session-local > project >
user); within one scope, deny overrides allow; no matching rule falls
through to the next decision source.
"""

from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatchcase
from typing import Literal

from pydantic import BaseModel, ConfigDict

RuleEffect = Literal["allow", "deny"]
RuleScope = Literal["user", "project", "session-local"]

_SCOPE_PRECEDENCE: dict[RuleScope, int] = {"session-local": 0, "project": 1, "user": 2}


class PermissionRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    matcher: str
    effect: RuleEffect
    scope: RuleScope


def resolve_rules(rules: Sequence[PermissionRule], tool_name: str) -> RuleEffect | None:
    matched = [rule for rule in rules if fnmatchcase(tool_name, rule.matcher)]
    if not matched:
        return None
    most_local = min(_SCOPE_PRECEDENCE[rule.scope] for rule in matched)
    in_scope = [rule for rule in matched if _SCOPE_PRECEDENCE[rule.scope] == most_local]
    if any(rule.effect == "deny" for rule in in_scope):
        return "deny"
    return "allow"
