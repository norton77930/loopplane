"""The permission policy — gating tool calls by the Phase-1 rule engine
(contracts/policies.md; FR-010-FR-011).

Reuses ``loopplane.approval.resolve_rules`` for rule precedence (no
re-implementation); a no-match falls back to a configurable default that defaults
to deny (safe by default).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from loopplane.approval import resolve_rules
from loopplane.governance.base import allow, as_decider, deny

if TYPE_CHECKING:
    from loopplane.approval import PermissionRule, PolicyDecider, PolicyVerdict
    from loopplane.model import ToolCallRequest, ToolDescriptor


def permission_policy(
    rules: Sequence[PermissionRule], *, default: Literal["allow", "deny"] = "deny"
) -> PolicyDecider:
    """Decide a call by ``resolve_rules`` over ``rules``: deny ⇒ deny, allow ⇒
    allow, no-match ⇒ ``default`` (defaults to deny) (FR-010, FR-011, FR-082)."""

    def decide(call: ToolCallRequest, descriptor: ToolDescriptor) -> PolicyVerdict:
        effect = resolve_rules(rules, call.tool_name) or default
        if effect == "allow":
            return allow()
        return deny(f"tool {call.tool_name!r} denied by permission policy")

    return as_decider(decide)
