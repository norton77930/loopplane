"""Validator combinators and the threshold gate
(contracts/combinators-boundary.md; FR-030–FR-034).

``all_of`` / ``any_of`` compose validators with a documented, cautious status
precedence. ``threshold_gate`` is the single pack that converts an evaluator
score into a gating decision, preserving the Phase-3 non-gating rule.
"""

from __future__ import annotations

from collections.abc import Awaitable, Sequence
from typing import TYPE_CHECKING

from loopplane.engineering import EvaluationResult, ValidationResult

if TYPE_CHECKING:
    from loopplane.engineering import (
        Evaluator,
        LoopState,
        ValidationStatus,
        Validator,
    )
    from loopplane.host import RunOutcome

# Most cautious wins: needs_human_review > needs_repair > fail > pass (FR-031).
_PRECEDENCE: dict[str, int] = {
    "pass": 0,
    "fail": 1,
    "needs_repair": 2,
    "needs_human_review": 3,
}


def _most_cautious(statuses: Sequence[str]) -> ValidationStatus:
    chosen = max(statuses, key=lambda status: _PRECEDENCE[status])
    return chosen  # type: ignore[return-value]


async def _resolve(
    value: ValidationResult | Awaitable[ValidationResult],
) -> ValidationResult:
    if isinstance(value, ValidationResult):
        return value
    return await value


def all_of(*validators: Validator) -> Validator:
    """`pass` iff every sub-validator passes; otherwise the most cautious
    non-pass status. Empty ⇒ `pass` (FR-030, FR-034)."""

    async def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        results = [await _resolve(v(outcome, state)) for v in validators]
        if all(r.status == "pass" for r in results):
            return ValidationResult(status="pass")
        non_pass = [r.status for r in results if r.status != "pass"]
        return ValidationResult(
            status=_most_cautious(non_pass),
            reason="all_of: " + "; ".join(r.status for r in results),
        )

    return validate


def any_of(*validators: Validator) -> Validator:
    """`pass` iff at least one sub-validator passes; otherwise the most cautious
    status. Empty ⇒ `fail` (FR-030, FR-034)."""

    async def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        results = [await _resolve(v(outcome, state)) for v in validators]
        if not results:
            return ValidationResult(status="fail", reason="any_of: no validators")
        if any(r.status == "pass" for r in results):
            return ValidationResult(status="pass")
        return ValidationResult(
            status=_most_cautious([r.status for r in results]),
            reason="any_of: none passed",
        )

    return validate


def threshold_gate(
    evaluator: Evaluator,
    *,
    threshold: float,
    below: ValidationStatus = "fail",
) -> Validator:
    """Turn an evaluator score into a gating decision — the only pack that does
    so (FR-032). A missing score fails safe (FR-033)."""

    async def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        raw = evaluator(outcome, state)
        evaluation = raw if isinstance(raw, EvaluationResult) else await raw
        if evaluation.score is None:
            return ValidationResult(
                status="fail", reason="threshold gate: evaluation carries no score"
            )
        if evaluation.score >= threshold:
            return ValidationResult(status="pass")
        return ValidationResult(
            status=below,
            reason=f"score {evaluation.score} below threshold {threshold}",
        )

    return validate
