"""LoopPlane Sandbox, Policy & Governance layer (feature
009-loopplane-sandbox-policy-governance).

Reusable, deterministic, public-safe **policy deciders** for the Tool Gateway's
decide-stage seam: permission, path, capability, budget, quota, combinators, and a
named sandbox profile. Every policy returns a Phase-1 ``PolicyVerdict`` (allow /
deny-with-reason) and **never executes, resolves, or OS-sandboxes a tool** — the
Tool Gateway stays the single chokepoint (Constitution V;
contracts/governance-boundary.md). It composes only the public Phase-1
policy/approval contracts and is distinct from the Phase-1 Human Approval boundary.
"""

from loopplane.governance.base import SimpleDecision, allow, as_decider, deny
from loopplane.governance.permission import permission_policy

__all__ = [
    "SimpleDecision",
    "allow",
    "as_decider",
    "deny",
    "permission_policy",
]
