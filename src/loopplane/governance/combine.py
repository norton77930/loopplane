"""Policy combinators and safe-failure governance (contracts/policies.md; FR-060,
FR-071).

``all_of`` composes deciders deny-wins; safe-failure maps any raised policy to a
deny (never a silent allow).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.approval import PolicyDeny
from loopplane.governance.base import allow, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.context import RunContext
    from loopplane.events.emitter import EventEmitter
    from loopplane.model import ToolCallRequest, ToolDescriptor


def all_of(*policies: PolicyDecider) -> PolicyDecider:
    """Deny-wins: evaluate the policies in order and short-circuit on the first
    deny (returning its reason); all must allow to allow. An empty ``all_of()``
    denies (safe by default) (FR-060)."""

    async def decider(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        if not policies:
            return deny("all_of: no policies (deny by default)")
        for policy in policies:
            verdict = await policy(call, descriptor, context, emitter)
            if isinstance(verdict, PolicyDeny):
                return verdict
        return allow()

    return decider
