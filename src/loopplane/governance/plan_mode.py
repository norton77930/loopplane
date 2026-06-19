"""The plan-mode policy — gating non-read-only tools during read-only investigation
(spec 038; FR-001, FR-002, FR-003).

A decide-stage policy that, while plan mode is active, denies any tool whose
descriptor declares ``read_only=False`` — EXCEPT a small allowlist that must remain
usable to make and submit a plan (``ask_user`` and ``exit_plan_mode``). Every
read-only tool is allowed; when plan mode is inactive (or absent) the policy is a no-op
allow. Plan-mode activity is read from a per-run :class:`PlanModeState` holder: an
explicit ``state`` argument (unit tests) or, when omitted, ``context.plan_mode`` (the
host wiring) — the same per-run holder the ``exit_plan_mode`` tool flips on approval.

Decided from the descriptor + the holder alone — no invocation. Compose it with the
other deciders through the existing combinators (``all_of`` deny-wins +
``safe_failure`` fail-closed); this adds no new Tool Gateway stage (Constitution V).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.context import PlanModeState
from loopplane.governance.base import allow, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.context import RunContext
    from loopplane.events.emitter import EventEmitter
    from loopplane.model import ToolCallRequest, ToolDescriptor

# The minimal set of non-read-only tools that must stay callable while planning so the
# agent can make and submit a plan: ask the user questions and submit the plan itself.
PLAN_MODE_ALLOWLIST: frozenset[str] = frozenset({"ask_user", "exit_plan_mode"})


def plan_mode_policy(
    state: PlanModeState | None = None,
    *,
    allowlist: frozenset[str] = PLAN_MODE_ALLOWLIST,
) -> PolicyDecider:
    """Deny a non-read-only, non-allowlisted tool while plan mode is active; allow
    read-only tools and the allowlist; a no-op when plan mode is inactive/absent
    (FR-001, FR-002). Plan-mode activity comes from ``state`` when given, else from
    the per-run ``context.plan_mode``."""

    async def decider(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        current = state if state is not None else context.plan_mode
        if current is None or not current.active:
            return allow()
        if descriptor.read_only or descriptor.name in allowlist:
            return allow()
        return deny(f"plan mode is active: {descriptor.name!r} is not a read-only tool")

    return decider
