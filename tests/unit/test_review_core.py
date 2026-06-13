"""Foundational unit tests for the human-review layer (006, RA): request
building, the Phase-3 decision mapping, and the default review key. Host-free.
"""

from __future__ import annotations

from loopplane.engineering import ArtifactRef, LoopState, RunReference, ValidationResult
from loopplane.review import (
    ReviewDecision,
    build_review_request,
    default_review_key,
    to_phase3_decision,
)


def _state(*, validation: ValidationResult | None) -> LoopState:
    return LoopState(
        loop_id="L",
        loop_definition_id="defL",
        iteration_index=2,
        run_refs=(RunReference("s1", "natural-completion"),),
        latest_validation=validation,
        artifacts=(ArtifactRef("s1", "a/1"),),
    )


def test_build_review_request_from_validator_status() -> None:
    state = _state(
        validation=ValidationResult(status="needs_human_review", reason="please review")
    )
    request = build_review_request(state)

    assert request.loop_id == "L"
    assert request.loop_definition_id == "defL"
    assert request.iteration_index == 2
    assert request.session_id == "s1"
    assert request.cause == "validator_status"
    assert request.validation_status == "needs_human_review"
    assert request.validation_reason == "please review"
    assert request.artifact_references == ("a/1",)
    assert "approve" in request.options


def test_build_review_request_fail_safe_cause() -> None:
    # A validator fault routes to review with no validation result.
    request = build_review_request(_state(validation=None))
    assert request.cause == "fail_safe"
    assert request.validation_status is None


def test_to_phase3_decision_mapping() -> None:
    assert to_phase3_decision(ReviewDecision(outcome="approve")).approve is True
    rejected = to_phase3_decision(ReviewDecision(outcome="reject", reason="no"))
    assert rejected.approve is False
    assert rejected.reason == "no"
    changes = to_phase3_decision(ReviewDecision(outcome="request_changes"))
    assert changes.approve is False
    assert changes.reason == "changes requested"


def test_default_review_key_is_the_loop_id() -> None:
    request = build_review_request(
        _state(validation=ValidationResult(status="needs_human_review"))
    )
    assert default_review_key(request) == "L"
