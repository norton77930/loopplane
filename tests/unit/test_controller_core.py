"""Direct unit tests for the controller package's harness-free public surface
(contracts/run-lifecycle.md): session-state wire values and the frozen
consumer-request models.

Dispatcher and BatchingSink behavior is covered by
tests/contract/test_run_lifecycle.py; this file only pins the contract shapes
that need no runtime harness.
"""

from __future__ import annotations

import typing

import pytest
from pydantic import ValidationError

import loopplane.controller as controller
from loopplane.controller import (
    ApprovalDecision,
    Cancel,
    QuestionAnswer,
    SessionState,
    SubmitInput,
)
from loopplane.model.content import TextBlock


def test_session_state_wire_values_are_stable() -> None:
    assert set(typing.get_args(SessionState)) == {
        "created",
        "active",
        "suspended",
        "terminated",
    }


def test_public_surface_exports_resolve() -> None:
    for name in controller.__all__:
        assert getattr(controller, name) is not None


def test_submit_input_is_frozen() -> None:
    request = SubmitInput(blocks=(TextBlock(text="hi"),))
    with pytest.raises(ValidationError):
        request.blocks = ()  # type: ignore[misc]


def test_approval_decision_validates_decision_and_scope() -> None:
    decision = ApprovalDecision(request_id="r1", decision="allow")
    assert decision.scope == "once"
    assert decision.reason is None
    with pytest.raises(ValidationError):
        ApprovalDecision(request_id="r1", decision="maybe")
    with pytest.raises(ValidationError):
        ApprovalDecision(request_id="r1", decision="deny", scope="forever")


def test_question_answer_requires_answers() -> None:
    answer = QuestionAnswer(request_id="q1", answers=("yes",))
    assert answer.answers == ("yes",)
    with pytest.raises(ValidationError):
        QuestionAnswer(request_id="q1")  # type: ignore[call-arg]


def test_cancel_is_a_frozen_marker() -> None:
    assert Cancel() == Cancel()
