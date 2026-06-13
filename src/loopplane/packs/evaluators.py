"""Evaluator packs (contracts/packs.md; FR-020–FR-023).

Reusable implementations of the Phase-3 Evaluator Protocol. Each is a pure
callable that returns an ``EvaluationResult``. Evaluators are **non-gating** —
they never return a ``ValidationResult`` and never decide control flow; only the
threshold gate converts a score into a gating decision.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from loopplane.engineering import EvaluationResult
from loopplane.packs.reader import OutcomeView, read_outcome
from loopplane.packs.validators import PackConfigError

if TYPE_CHECKING:
    from loopplane.engineering import Evaluator, LoopState
    from loopplane.host import RunOutcome


def scoring_evaluator(
    score_fn: Callable[[OutcomeView], float], *, label: str | None = None
) -> Evaluator:
    """Apply a host scoring function over the outcome view (FR-020). A raising
    function becomes a non-fatal diagnostic with ``score=None`` (FR-023)."""

    def evaluate(outcome: RunOutcome, state: LoopState) -> EvaluationResult:
        view = read_outcome(outcome, state)
        try:
            score = score_fn(view)
        except Exception as exc:  # noqa: BLE001 - non-fatal diagnostic (FR-023)
            return EvaluationResult(
                score=None, reason=f"scoring function raised: {exc!r}"
            )
        return EvaluationResult(score=score, label=label)

    return evaluate


def label_evaluator(
    rules: Sequence[tuple[Callable[[OutcomeView], bool], str]], *, default: str
) -> Evaluator:
    """Assign the first matching rule's label, else ``default`` (FR-021)."""

    def evaluate(outcome: RunOutcome, state: LoopState) -> EvaluationResult:
        view = read_outcome(outcome, state)
        for predicate, label in rules:
            try:
                matched = predicate(view)
            except Exception:  # noqa: BLE001 - a raising rule is skipped
                continue
            if matched:
                return EvaluationResult(label=label, reason=f"matched rule -> {label}")
        return EvaluationResult(label=default, reason="no rule matched; default label")

    return evaluate


def length_evaluator(*, target_chars: int) -> Evaluator:
    """A deterministic measurement: normalized output length in ``[0, 1]``
    (FR-022)."""

    if target_chars <= 0:
        raise PackConfigError("target_chars must be positive")

    def evaluate(outcome: RunOutcome, state: LoopState) -> EvaluationResult:
        length = len(read_outcome(outcome, state).final_text)
        score = min(1.0, max(0.0, length / target_chars))
        return EvaluationResult(score=score)

    return evaluate
