"""The network-egress policy — gating tools that require network access (spec 034;
FR-009, FR-011).

A decide-stage policy that denies any tool whose descriptor declares
``network=True`` unless the host has explicitly enabled network egress
(default-deny / opt-in). A non-network tool is never denied here. Decided from the
descriptor alone — no invocation. Compose it with the other deciders through the
existing combinators (``all_of`` deny-wins + ``safe_failure`` fail-closed); this
adds no new Tool Gateway stage (Constitution V).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.governance.base import allow, as_decider, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.model import ToolCallRequest, ToolDescriptor


def network_policy(*, allow_network: bool) -> PolicyDecider:
    """Deny a tool flagged ``network=True`` when network egress is disabled; allow
    it when enabled; never deny a non-network tool (FR-009, FR-011). Decided from
    the descriptor, no invocation."""

    def decide(call: ToolCallRequest, descriptor: ToolDescriptor) -> PolicyVerdict:
        if descriptor.network and not allow_network:
            return deny(
                f"network egress is disabled: tool {call.tool_name!r} requires "
                f"network access"
            )
        return allow()

    return as_decider(decide)
