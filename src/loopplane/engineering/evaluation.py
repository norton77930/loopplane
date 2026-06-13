"""The optional Evaluator contract and its non-gating result
(contracts/validator-evaluator.md; FR-040–FR-043).

An Evaluator produces measurement only — score, label, reason, metadata. It
never decides control flow by itself; only the stop condition or a Validator
may consume its output (FR-041).
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from loopplane.engineering.state import LoopState
    from loopplane.host import RunOutcome


@dataclass(frozen=True)
class EvaluationResult:
    """The Evaluator's non-gating output (FR-040)."""

    score: float | None = None
    label: str | None = None
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Evaluator(Protocol):
    """Given an iteration's Agent Run outcome and the current Loop State,
    returns an :class:`EvaluationResult` (sync or async)."""

    def __call__(
        self, outcome: RunOutcome, state: LoopState
    ) -> EvaluationResult | Awaitable[EvaluationResult]: ...
