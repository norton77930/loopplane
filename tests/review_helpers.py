"""Deterministic, public-safe test helpers for the human-review layer (006).

Builds a Phase-3 loop that needs review (reusing the Phase-3 scripted-host
helpers) plus scripted reviewers, askers, and a review-event recorder.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    ManualTrigger,
    StaticInput,
    ValidationPolicy,
    stop_on_pass,
)
from loopplane.review import (
    ReviewContext,
    ReviewDecision,
    ReviewEvent,
    ReviewOutcome,
    ReviewQuestion,
    ReviewRequest,
)
from tests.loop_helpers import ScriptedValidator, scripted_host_factory


def needs_review_definition(
    *,
    loop_id: str = "reviewed",
    validator: object | None = None,
    working_scope: Path | None = None,
) -> LoopDefinition:
    """A Phase-3 loop whose validator returns ``needs_human_review`` (so the loop
    routes to human review), with a fresh scripted host per run for determinism
    and resume re-drive."""

    return LoopDefinition(
        loop_id=loop_id,
        trigger=ManualTrigger(),
        input_source=StaticInput("do the task"),
        host_profile=HostRuntimeProfile(
            selector=scripted_host_factory("draft output", working_scope=working_scope)
        ),
        validation_policy=ValidationPolicy(
            validator=validator
            or ScriptedValidator("needs_human_review", reason="please review")
        ),
        stop_condition=stop_on_pass(max_iterations=3),
    )


def const_reviewer(
    outcome: ReviewOutcome, *, reason: str | None = None, reviewer: str = "bot"
) -> object:
    def review(request: ReviewRequest, context: ReviewContext) -> ReviewDecision:
        return ReviewDecision(outcome=outcome, reason=reason, reviewer=reviewer)

    return review


class RecordingReviewer:
    """A reviewer that records the Review Request it saw and its call count."""

    def __init__(
        self, outcome: ReviewOutcome = "approve", *, reason: str | None = None
    ) -> None:
        self.seen: ReviewRequest | None = None
        self.calls = 0
        self._outcome = outcome
        self._reason = reason

    def __call__(
        self, request: ReviewRequest, context: ReviewContext
    ) -> ReviewDecision:
        self.seen = request
        self.calls += 1
        return ReviewDecision(
            outcome=self._outcome, reason=self._reason, reviewer="recorder"
        )


def raising_reviewer() -> object:
    def review(request: ReviewRequest, context: ReviewContext) -> ReviewDecision:
        raise RuntimeError("reviewer boom")

    return review


def unknown_outcome_reviewer() -> object:
    def review(request: ReviewRequest, context: ReviewContext) -> ReviewDecision:
        return ReviewDecision(outcome="weird")  # type: ignore[arg-type]

    return review


class AskingReviewer:
    """An async reviewer that asks one question and approves iff the answer
    matches ``approve_if``."""

    def __init__(self, question: str, *, approve_if: str) -> None:
        self.question = question
        self.approve_if = approve_if
        self.answer: str | None = None

    async def __call__(
        self, request: ReviewRequest, context: ReviewContext
    ) -> ReviewDecision:
        answers = await context.ask([ReviewQuestion(text=self.question)])
        self.answer = answers[0] if answers else None
        outcome: ReviewOutcome = (
            "approve" if self.answer == self.approve_if else "reject"
        )
        return ReviewDecision(outcome=outcome, reason=f"answer={self.answer}")


def scripted_asker(*answers: str) -> object:
    def asker(questions: Sequence[ReviewQuestion]) -> list[str]:
        return list(answers)

    return asker


def raising_asker() -> object:
    def asker(questions: Sequence[ReviewQuestion]) -> list[str]:
        raise RuntimeError("asker boom")

    return asker


class ReviewEventRecorder:
    """A review-event sink that records every emitted event in order."""

    def __init__(self) -> None:
        self.events: list[ReviewEvent] = []

    async def __call__(self, event: ReviewEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]
