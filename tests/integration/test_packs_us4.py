"""US4: compose validators and gate on a score (spec US4; SC-005, SC-006, SC-008).

all-of / any-of combinators with documented precedence, and a threshold gate —
the single evaluation-to-gating conversion.
"""

from __future__ import annotations

import pytest

from loopplane.engineering import EvaluationResult, LoopState, ValidationResult
from loopplane.host import RunOutcome
from loopplane.packs import (
    all_of,
    any_of,
    rule_validator,
    scoring_evaluator,
    threshold_gate,
)
from tests.packs_helpers import scripted_outcome

pytestmark = pytest.mark.anyio


def _const(status: str) -> object:
    def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        return ValidationResult(status=status)  # type: ignore[arg-type]

    return validate


async def test_all_of_passes_only_when_all_pass() -> None:
    validator = all_of(rule_validator(lambda v: True), _const("pass"))  # type: ignore[arg-type]
    assert (await validator(*scripted_outcome(text="x"))).status == "pass"

    failing = all_of(rule_validator(lambda v: True), _const("fail"))  # type: ignore[arg-type]
    assert (await failing(*scripted_outcome(text="x"))).status == "fail"


async def test_all_of_surfaces_the_most_cautious_status() -> None:
    validator = all_of(_const("pass"), _const("needs_human_review"), _const("fail"))  # type: ignore[arg-type]
    assert (await validator(*scripted_outcome(text="x"))).status == "needs_human_review"


async def test_any_of_passes_when_one_passes() -> None:
    validator = any_of(_const("fail"), _const("pass"))  # type: ignore[arg-type]
    assert (await validator(*scripted_outcome(text="x"))).status == "pass"


async def test_any_of_all_fail_yields_most_cautious() -> None:
    validator = any_of(_const("fail"), _const("needs_repair"))  # type: ignore[arg-type]
    assert (await validator(*scripted_outcome(text="x"))).status == "needs_repair"


async def test_empty_combinator_defaults() -> None:
    assert (await all_of()(*scripted_outcome(text="x"))).status == "pass"
    assert (await any_of()(*scripted_outcome(text="x"))).status == "fail"


async def test_threshold_gate_gates_on_the_score() -> None:
    high = threshold_gate(scoring_evaluator(lambda v: 0.9), threshold=0.5)
    assert (await high(*scripted_outcome(text="x"))).status == "pass"

    low = threshold_gate(
        scoring_evaluator(lambda v: 0.2), threshold=0.5, below="needs_repair"
    )
    result = await low(*scripted_outcome(text="x"))
    assert result.status == "needs_repair"


async def test_threshold_gate_fails_safe_on_a_missing_score() -> None:
    def no_score(outcome: RunOutcome, state: LoopState) -> EvaluationResult:
        return EvaluationResult(score=None)

    gate = threshold_gate(no_score, threshold=0.5)
    result = await gate(*scripted_outcome(text="x"))
    assert result.status == "fail"
    assert result.reason is not None
    assert "score" in result.reason
