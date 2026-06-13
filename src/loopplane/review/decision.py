"""The Review Decision, the Reviewer contract, and the Phase-3 mapping
(contracts/review.md; FR-002–FR-004).
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from loopplane.engineering import ReviewDecision as EngineeringReviewDecision

if TYPE_CHECKING:
    from loopplane.review.questions import ReviewContext
    from loopplane.review.request import ReviewRequest

ReviewOutcome = Literal["approve", "reject", "request_changes"]


@dataclass(frozen=True)
class ReviewDecision:
    """A reviewer's output: an outcome plus a reason, reviewer identity, and
    metadata (FR-002)."""

    outcome: ReviewOutcome
    reason: str | None = None
    reviewer: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Reviewer(Protocol):
    """A host-supplied callable that, given a Review Request and a Review
    Context, returns a Review Decision (sync or async) (FR-003)."""

    def __call__(
        self, request: ReviewRequest, context: ReviewContext
    ) -> ReviewDecision | Awaitable[ReviewDecision]: ...


def to_phase3_decision(decision: ReviewDecision) -> EngineeringReviewDecision:
    """Map a Review Decision to the Phase-3 ``ReviewDecision`` (FR-004).

    ``approve`` → approve; ``reject`` / ``request_changes`` → non-approval. A
    non-approval outcome is never mapped to approval.
    """

    if decision.outcome == "approve":
        return EngineeringReviewDecision(approve=True, reason=decision.reason)
    reason = decision.reason
    if reason is None and decision.outcome == "request_changes":
        reason = "changes requested"
    return EngineeringReviewDecision(approve=False, reason=reason)
