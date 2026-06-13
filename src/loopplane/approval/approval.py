"""Human Approval: the policy decision boundary (contracts/approval.md;
FR-110–FR-114, FR-055).

Decision sources in deterministic order: the autonomous-invocation gate (a
capability gate nothing overrides), session approval memory, the skill
approval requirement (forces at least an "ask"; a persistent allow rule
never satisfies it), persistent permission rules, reviewer escalation. A
tool with no applicable source resolves as "ask".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from loopplane.approval.decisions import PolicyAllow, PolicyDeny, PolicyVerdict
from loopplane.approval.rules import PermissionRule, resolve_rules
from loopplane.context import RunContext
from loopplane.events.emitter import EventEmitter
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor

_DEFAULT_DENIAL_REASON = "denied by reviewer"
_SUMMARY_LIMIT = 200


class SkillConstraint(Protocol):
    """The execution-profile fields this boundary honors (FR-055; research A1)."""

    @property
    def autonomous_invocation(self) -> str: ...

    @property
    def approval_required(self) -> bool: ...


def _summarize_input(call: ToolCallRequest) -> str:
    summary = ", ".join(f"{key}={value!r}" for key, value in call.input.items())
    return summary[:_SUMMARY_LIMIT]


class HumanApproval:
    def __init__(
        self,
        *,
        rules: Sequence[PermissionRule] = (),
        skill_profiles: Mapping[str, SkillConstraint] | None = None,
    ) -> None:
        self._rules = list(rules)
        self._skill_profiles = dict(skill_profiles) if skill_profiles else {}

    async def __call__(
        self,
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        # 1. Autonomous-invocation gate: capability gating, not a permission;
        # no rule, session memory, or reviewer decision overrides it.
        profile = self._skill_profiles.get(call.tool_name)
        if profile is not None and profile.autonomous_invocation == "forbidden":
            return PolicyDeny(
                reason=f"{call.tool_name} is not available for autonomous use"
            )

        # 2. Session approval memory (FR-113).
        remembered = context.session_approval_memory.get(call.tool_name)
        if remembered == "allow":
            return PolicyAllow()
        if remembered == "deny":
            return PolicyDeny(
                reason=f"{call.tool_name} was denied earlier in this session"
            )

        # 3. Skill approval requirement: forces at least an "ask"; only an
        # explicit human decision satisfies it.
        if profile is not None and profile.approval_required:
            return await self._escalate(call, context)

        # 4. Persistent permission rules (FR-114).
        effect = resolve_rules(self._rules, call.tool_name)
        if effect == "allow":
            return PolicyAllow()
        if effect == "deny":
            return PolicyDeny(reason=f"{call.tool_name} is denied by a permission rule")

        # 5. Reviewer escalation.
        return await self._escalate(call, context)

    async def _escalate(
        self, call: ToolCallRequest, context: RunContext
    ) -> PolicyVerdict:
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
