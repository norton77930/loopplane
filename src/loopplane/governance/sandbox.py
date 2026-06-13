"""The sandbox profile — a named bundle of policies (contracts/policies.md;
FR-070).

Composes the supplied policies with ``all_of`` (deny-wins) and wraps the result in
``safe_failure``, returning one ``PolicyDecider`` for the gateway's seam. This is a
policy-level sandbox, not OS-level isolation (FR-090 reserved).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.governance.combine import all_of, safe_failure

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider


def sandbox_profile(
    *,
    permission: PolicyDecider | None = None,
    path: PolicyDecider | None = None,
    capability: PolicyDecider | None = None,
    budget: PolicyDecider | None = None,
) -> PolicyDecider:
    """Compose the supplied policies (deny-wins) and wrap in safe-failure; a profile
    with no policies denies by default (FR-070)."""

    policies = [
        policy
        for policy in (permission, path, capability, budget)
        if policy is not None
    ]
    return safe_failure(all_of(*policies))
