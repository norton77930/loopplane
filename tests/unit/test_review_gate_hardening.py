"""Fail-safe and observation hardening for the review gate (006; FR-002,
FR-052, NFR-005, SC-007). Host-free: the resolver is driven directly with a
hand-built Loop State so the gate's own edges are exercised in isolation.
"""

from __future__ import annotations

import pytest

from loopplane.engineering import LoopState, RunReference, ValidationResult
from loopplane.review import (
    ReviewContext,
    ReviewDecision,
    ReviewEvent,
    ReviewMemory,
    ReviewRequest,
    build_review_resolver,
)
from tests.review_helpers import (
    RecordingReviewer,
    ReviewEventRecorder,
    const_reviewer,
)

pytestmark = pytest.mark.anyio


def _review_state(
    run_refs: tuple[RunReference, ...] = (RunReference("s1", "natural-completion"),),
) -> LoopState:
    return LoopState(
        loop_id="L",
        loop_definition_id="defL",
        iteration_index=1,
        run_refs=run_refs,
        latest_validation=ValidationResult(
            status="needs_human_review", reason="please review"
        ),
        artifacts=(),
    )


async def _raising_sink(event: ReviewEvent) -> None:
    raise RuntimeError("sink boom")


def _raising_key(request: ReviewRequest) -> str:
    raise RuntimeError("key boom")


async def test_raising_event_sink_does_not_crash_or_change_decision() -> None:
    state = _review_state()
    clean = await build_review_resolver(const_reviewer("approve", reason="ok"))(state)
    hardened = await build_review_resolver(
        const_reviewer("approve", reason="ok"), on_event=_raising_sink
    )(state)

    # A raising observation sink never changes the decision or crashes the review
    # (FR-052, NFR-005).
    assert hardened == clean
    assert hardened.approve is True
    assert hardened.reason == "ok"


async def test_review_decided_event_carries_metadata() -> None:
    recorder = ReviewEventRecorder()

    def reviewer(request: ReviewRequest, context: ReviewContext) -> ReviewDecision:
        return ReviewDecision(
            outcome="approve", reason="r", reviewer="rv", metadata={"score": 9}
        )

    await build_review_resolver(reviewer, on_event=recorder)(_review_state())

    decided = [event for event in recorder.events if event.type == "review_decided"]
    assert len(decided) == 1
    payload = decided[0].payload
    # The decision's reason and optional metadata are carried into the event
    # (FR-002, SC-007).
    assert payload["metadata"] == {"score": 9}
    assert payload["reason"] == "r"
    assert payload["reviewer"] == "rv"
    assert payload["outcome"] == "approve"
    assert payload["source"] == "reviewer"


async def test_review_event_payload_and_sequence_are_well_formed() -> None:
    recorder = ReviewEventRecorder()
    await build_review_resolver(
        const_reviewer("approve", reason="ok"), on_event=recorder
    )(_review_state())

    assert recorder.types == ["review_requested", "review_decided"]
    assert [event.sequence for event in recorder.events] == [0, 1]
    requested = recorder.events[0]
    assert requested.loop_id == "L"
    assert requested.session_id == "s1"
    assert requested.payload["cause"] == "validator_status"
    assert requested.payload["validation_status"] == "needs_human_review"


async def test_memory_raising_key_does_not_crash_review() -> None:
    reviewer = RecordingReviewer("approve")
    decision = await build_review_resolver(
        reviewer, memory=ReviewMemory(key=_raising_key)
    )(_review_state())

    # A raising review-key maps to a cache miss; the reviewer still decides and
    # the failed persist is swallowed (NFR-005).
    assert reviewer.calls == 1
    assert decision.approve is True
