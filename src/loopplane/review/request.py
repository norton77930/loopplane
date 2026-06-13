"""The Review Request (contracts/review.md; FR-001).

A structured, public-safe description of what a reviewer reviews, built from the
public Loop State. It reads only the public surface and never mutates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from loopplane.engineering import LoopState
    from loopplane.review.decision import ReviewOutcome

ReviewCause = Literal["validator_status", "fail_safe"]

DEFAULT_OPTIONS: tuple[ReviewOutcome, ...] = ("approve", "reject", "request_changes")


@dataclass(frozen=True)
class ReviewRequest:
    """What a reviewer sees, built from the public Loop State (FR-001)."""

    loop_id: str
    loop_definition_id: str
    iteration_index: int
    session_id: str | None
    cause: ReviewCause
    validation_status: str | None
    validation_reason: str | None
    artifact_references: tuple[str, ...]
    options: tuple[ReviewOutcome, ...]


def build_review_request(
    state: LoopState, *, options: tuple[ReviewOutcome, ...] = DEFAULT_OPTIONS
) -> ReviewRequest:
    """Build a Review Request from the public Loop State (FR-001).

    The cause is ``validator_status`` when a validation result exists, else
    ``fail_safe`` (a validator fault routed to review). The session reference is
    the most recent Agent Run's id.
    """

    validation = state.latest_validation
    session_id = state.run_refs[-1].session_id if state.run_refs else None
    return ReviewRequest(
        loop_id=state.loop_id,
        loop_definition_id=state.loop_definition_id,
        iteration_index=state.iteration_index,
        session_id=session_id,
        cause="validator_status" if validation is not None else "fail_safe",
        validation_status=validation.status if validation is not None else None,
        validation_reason=validation.reason if validation is not None else None,
        artifact_references=tuple(ref.reference for ref in state.artifacts),
        options=options,
    )
