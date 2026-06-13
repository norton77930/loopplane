"""The review gate, pause/inspect/resume (contracts/gate-boundary.md;
FR-010–FR-022).

``build_review_resolver`` composes a Reviewer (+ optional Review Memory and a
review-question channel) into a Phase-3 ``ReviewResolver`` — the human gate loop.
``inspect_paused`` extracts a Review Request from a paused outcome, and
``resume_review`` drives a Loop Run with a supplied decision (in process). The
layer starts runs only through the Phase-3 ``run_loop`` and reads only the public
Loop State (FR-012, FR-040).
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

from loopplane.engineering import ReviewDecision as EngineeringReviewDecision
from loopplane.engineering import run_loop
from loopplane.review.decision import ReviewDecision, Reviewer, to_phase3_decision
from loopplane.review.events import ReviewEvent, ReviewEventSink, ReviewEventType
from loopplane.review.questions import QuestionAsker, ReviewContext
from loopplane.review.request import (
    DEFAULT_OPTIONS,
    ReviewRequest,
    build_review_request,
)

if TYPE_CHECKING:
    from loopplane.engineering import (
        LoopDefinition,
        LoopOutcome,
        LoopState,
        ReviewResolver,
    )
    from loopplane.review.decision import ReviewOutcome
    from loopplane.review.memory import ReviewMemory

_VALID_OUTCOMES = frozenset({"approve", "reject", "request_changes"})


def build_review_resolver(
    reviewer: Reviewer,
    *,
    memory: ReviewMemory | None = None,
    asker: QuestionAsker | None = None,
    on_event: ReviewEventSink | None = None,
    options: tuple[ReviewOutcome, ...] = DEFAULT_OPTIONS,
) -> ReviewResolver:
    """Compose a Reviewer into a Phase-3 ``ReviewResolver`` (the human gate loop;
    FR-010, FR-011)."""

    sequence = _Counter()

    async def emit(
        event_type: ReviewEventType, *, request: ReviewRequest, payload: dict[str, Any]
    ) -> None:
        if on_event is None:
            return
        event = ReviewEvent(
            type=event_type,
            sequence=sequence.next(),
            loop_id=request.loop_id,
            iteration_index=request.iteration_index,
            session_id=request.session_id,
            payload=payload,
        )
        await on_event(event)

    async def resolver(state: LoopState) -> EngineeringReviewDecision:
        request = build_review_request(state, options=options)
        await emit(
            "review_requested",
            request=request,
            payload={
                "cause": request.cause,
                "validation_status": request.validation_status,
            },
        )

        if memory is not None:
            remembered = memory.recall(request)
            if remembered is not None:
                await emit(
                    "review_resolved_from_memory",
                    request=request,
                    payload={"outcome": remembered.outcome},
                )
                await _emit_decided(emit, request, remembered, source="memory")
                return to_phase3_decision(remembered)

        def bound_emit(
            event_type: ReviewEventType, payload: dict[str, Any]
        ) -> Awaitable[None]:
            return emit(event_type, request=request, payload=payload)

        context = ReviewContext(asker=asker, emit=bound_emit)
        decision = await _run_reviewer(reviewer, request, context)
        if memory is not None:
            memory.remember_decision(request, decision)
        await _emit_decided(emit, request, decision, source="reviewer")
        return to_phase3_decision(decision)

    return resolver


async def _emit_decided(
    emit: Any, request: ReviewRequest, decision: ReviewDecision, *, source: str
) -> None:
    await emit(
        "review_decided",
        request=request,
        payload={
            "outcome": decision.outcome,
            "reason": decision.reason,
            "reviewer": decision.reviewer,
            "source": source,
        },
    )


async def _run_reviewer(
    reviewer: Reviewer, request: ReviewRequest, context: ReviewContext
) -> ReviewDecision:
    """Invoke the reviewer and fail safe — a raised or unrecognized outcome maps
    to a non-approval decision, never a silent approve (FR-013)."""

    try:
        raw = reviewer(request, context)
        decision = raw if isinstance(raw, ReviewDecision) else await raw
    except Exception as exc:  # noqa: BLE001 - fail safe, never a silent approve
        return ReviewDecision(
            outcome="reject", reason=f"fail-safe: reviewer raised: {exc!r}"
        )
    if decision.outcome not in _VALID_OUTCOMES:
        return ReviewDecision(
            outcome="reject",
            reason=f"fail-safe: unrecognized review outcome {decision.outcome!r}",
        )
    return decision


def inspect_paused(outcome: LoopOutcome) -> ReviewRequest | None:
    """Return the Review Request describing a paused outcome, else ``None`` for a
    terminal outcome (FR-020)."""

    if not outcome.paused:
        return None
    return build_review_request(outcome.state)


async def resume_review(
    definition: LoopDefinition,
    decision: ReviewDecision,
    *,
    on_event: ReviewEventSink | None = None,
) -> LoopOutcome:
    """Resume a review by driving the Loop Run through the Phase-3 ``run_loop``
    with the supplied decision (in process; durable resume reserved — FR-021,
    FR-022)."""

    def _constant_reviewer(
        request: ReviewRequest, context: ReviewContext
    ) -> ReviewDecision:
        return decision

    resolver = build_review_resolver(_constant_reviewer, on_event=on_event)
    return await run_loop(definition, review_resolver=resolver)


class _Counter:
    def __init__(self) -> None:
        self._value = 0

    def next(self) -> int:
        value = self._value
        self._value += 1
        return value
