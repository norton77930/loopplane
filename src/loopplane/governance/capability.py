"""The capability policy — gating by a tool's declared capability
(contracts/policies.md; FR-030).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.governance.base import allow, as_decider, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.model import ToolCallRequest, ToolDescriptor


def capability_policy(
    *, require_read_only: bool = False, require_concurrency_safe: bool = False
) -> PolicyDecider:
    """Deny a tool whose declared ``read_only`` / ``concurrency_safe`` does not meet
    the required flags; else allow (FR-030). Decided from the descriptor, no
    invocation."""

    def decide(call: ToolCallRequest, descriptor: ToolDescriptor) -> PolicyVerdict:
        if require_read_only and not descriptor.read_only:
            return deny(f"capability policy: tool {call.tool_name!r} is not read-only")
        if require_concurrency_safe and not descriptor.concurrency_safe:
            return deny(
                f"capability policy: tool {call.tool_name!r} is not concurrency-safe"
            )
        return allow()

    return as_decider(decide)
