"""Review Memory (contracts/review.md; FR-030–FR-033).

Remembers a Review Decision under a review key so a later matching review
auto-resolves without re-invoking the reviewer. In process and host-owned;
durable persistence is reserved. Distinct from the Phase-1 in-run tool approval
memory.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from loopplane.review.decision import ReviewDecision
    from loopplane.review.request import ReviewRequest

RememberMode = Literal["approvals", "rejections", "both"]
ReviewKey = Callable[["ReviewRequest"], str]


def default_review_key(request: ReviewRequest) -> str:
    """The default review key — the loop id; never crosses unrelated loops
    (FR-032)."""

    return request.loop_id


class ReviewMemory:
    """An in-process remember-the-decision store keyed by a review key
    (FR-030)."""

    def __init__(
        self, *, remember: RememberMode = "both", key: ReviewKey = default_review_key
    ) -> None:
        self._remember = remember
        self._key = key
        self._store: dict[str, ReviewDecision] = {}

    def recall(self, request: ReviewRequest) -> ReviewDecision | None:
        """Return a remembered decision for this request's key, else ``None``."""

        return self._store.get(self._key(request))

    def remember_decision(
        self, request: ReviewRequest, decision: ReviewDecision
    ) -> None:
        """Store the decision under the request's key, only if its outcome
        matches the configured remember mode (FR-031)."""

        is_approval = decision.outcome == "approve"
        if self._remember == "approvals" and not is_approval:
            return
        if self._remember == "rejections" and is_approval:
            return
        self._store[self._key(request)] = decision
