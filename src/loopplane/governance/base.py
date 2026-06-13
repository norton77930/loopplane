"""The verdict helpers and the decider adapter (contracts/policies.md; FR-001,
FR-002).

Every policy targets the Tool Gateway's decide-stage ``PolicyDecider`` shape;
``as_decider`` adapts a simple ``(call, descriptor) -> verdict`` into that async
four-parameter form, ignoring the trailing run context / event emitter and never
invoking a tool.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from loopplane.approval import PolicyAllow, PolicyDeny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.context import RunContext
    from loopplane.events.emitter import EventEmitter
    from loopplane.model import ToolCallRequest, ToolDescriptor

SimpleDecision = Callable[["ToolCallRequest", "ToolDescriptor"], "PolicyVerdict"]


def allow() -> PolicyAllow:
    return PolicyAllow()


def deny(reason: str) -> PolicyDeny:
    return PolicyDeny(reason=reason)


def as_decider(decision: SimpleDecision) -> PolicyDecider:
    """Wrap a simple ``(call, descriptor) -> verdict`` into the gateway's async
    ``PolicyDecider``; the run context and event emitter are accepted and ignored,
    and no tool is ever invoked (FR-001, FR-002, NFR-006)."""

    async def decider(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        return decision(call, descriptor)

    return decider
