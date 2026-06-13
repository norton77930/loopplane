"""Stop conditions: bounded predicates over Loop State
(contracts/validator-evaluator.md; FR-007, FR-013).

A stop condition pairs a testable predicate with a mandatory hard
``max_iterations`` bound the controller enforces *before* the predicate, so
every Loop Run is guaranteed to terminate (FR-013, SC-007).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loopplane.engineering.state import LoopState

StopPredicate = Callable[["LoopState"], bool]


@dataclass(frozen=True)
class StopCondition:
    """A predicate over Loop State plus the hard iteration bound (FR-007)."""

    predicate: StopPredicate
    max_iterations: int
    description: str = ""

    def satisfied(self, state: LoopState) -> bool:
        return self.predicate(state)


def stop_on_pass(*, max_iterations: int = 1) -> StopCondition:
    """Stop on the first passing validation (FR-007)."""

    def _passed(state: LoopState) -> bool:
        return (
            state.latest_validation is not None
            and state.latest_validation.status == "pass"
        )

    return StopCondition(
        predicate=_passed,
        max_iterations=max_iterations,
        description="stop on first passing validation",
    )


def max_iterations(n: int) -> StopCondition:
    """Run exactly ``n`` iterations, then stop — a bound-only condition."""

    if n < 1:
        raise ValueError("max_iterations must be at least 1")

    return StopCondition(
        predicate=lambda state: state.iteration_index >= n,
        max_iterations=n,
        description=f"stop after {n} iterations",
    )


def stop_when_score_at_least(threshold: float, *, max_iterations: int) -> StopCondition:
    """Stop when the latest evaluation score reaches ``threshold`` (US4; FR-007).

    Evaluation can drive *stopping* but never retry/repair (FR-041).
    """

    def _scored(state: LoopState) -> bool:
        evaluation = state.latest_evaluation
        return (
            evaluation is not None
            and evaluation.score is not None
            and evaluation.score >= threshold
        )

    return StopCondition(
        predicate=_scored,
        max_iterations=max_iterations,
        description=f"stop when score >= {threshold}",
    )
