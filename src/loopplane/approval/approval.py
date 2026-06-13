"""Human Approval: the policy decision boundary (contracts/approval.md;
FR-110–FR-114).

Decision sources in deterministic order: session approval memory, persistent
permission rules, reviewer escalation. The skill execution-profile gates
(sources 1 and 3 of the contract) join in the skills phase through this same
component. A tool with no applicable source resolves as "ask".
"""

from __future__ import annotations

from collections.abc import Sequence

from loopplane.approval.decisions import PolicyAllow, PolicyDeny, PolicyVerdict
from loopplane.approval.rules import PermissionRule, resolve_rules
from loopplane.context import RunContext
from loopplane.events.emitter import EventEmitter
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor

_DEFAULT_DENIAL_REASON = "denied by reviewer"
_SUMMARY_LIMIT = 200


def _summarize_input(call: ToolCallRequest) -> str:
    summary = ", ".join(f"{key}={value!r}" for key, value in call.input.items())
    return summary[:_SUMMARY_LIMIT]


class HumanApproval:
    def __init__(self, *, rules: Sequence[PermissionRule] = ()) -> None:
        self._rules = list(rules)

    async def __call__(
        self,
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        remembered = context.session_approval_memory.get(call.tool_name)
        if remembered == "allow":
            return PolicyAllow()
        if remembered == "deny":
            return PolicyDeny(
                reason=f"{call.tool_name} was denied earlier in this session"
            )

        effect = resolve_rules(self._rules, call.tool_name)
        if effect == "allow":
            return PolicyAllow()
        if effect == "deny":
            return PolicyDeny(reason=f"{call.tool_name} is denied by a permission rule")

        broker = context.interactions
        if broker is None or not broker.reviewer_attached:
            return PolicyDeny(reason="no reviewer available")
        resolution = await broker.request_approval(
            call_id=call.call_id,
            tool_name=call.tool_name,
            input_summary=_summarize_input(call),
        )
        if resolution.scope == "session":
            context.session_approval_memory[call.tool_name] = resolution.decision
        if resolution.decision == "allow":
            return PolicyAllow()
        return PolicyDeny(reason=resolution.reason or _DEFAULT_DENIAL_REASON)
