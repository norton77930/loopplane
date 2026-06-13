"""US3: score and label iterations (spec US3; SC-004, SC-008).

Scoring, label, and length evaluators return EvaluationResults and never gate.
"""

from __future__ import annotations

from loopplane.engineering import EvaluationResult
from loopplane.packs import (
    OutcomeView,
    label_evaluator,
    length_evaluator,
    scoring_evaluator,
)
from tests.packs_helpers import scripted_outcome


def test_scoring_evaluator_returns_the_score() -> None:
    evaluator = scoring_evaluator(lambda view: 0.75)
    result = evaluator(*scripted_outcome(text="x"))
    assert isinstance(result, EvaluationResult)
    assert result.score == 0.75


def test_scoring_function_raising_is_a_non_fatal_diagnostic() -> None:
    def boom(view: OutcomeView) -> float:
        raise RuntimeError("scoring boom")

    result = scoring_evaluator(boom)(*scripted_outcome(text="x"))
    assert result.score is None
    assert result.reason is not None
    assert "raised" in result.reason


def test_label_evaluator_assigns_a_label() -> None:
    evaluator = label_evaluator(
        [(lambda view: "good" in view.final_text, "high")], default="low"
    )
    assert evaluator(*scripted_outcome(text="good output")).label == "high"
    assert evaluator(*scripted_outcome(text="bad output")).label == "low"


def test_length_evaluator_scores_within_unit_interval() -> None:
    evaluator = length_evaluator(target_chars=10)
    assert evaluator(*scripted_outcome(text="12345")).score == 0.5
    assert evaluator(*scripted_outcome(text="x" * 100)).score == 1.0
    assert evaluator(*scripted_outcome(text="")).score == 0.0


def test_evaluators_are_non_gating() -> None:
    # An evaluator returns an EvaluationResult, never a ValidationResult.
    result = scoring_evaluator(lambda view: 0.1)(*scripted_outcome(text="x"))
    assert isinstance(result, EvaluationResult)
    assert not hasattr(result, "status")
