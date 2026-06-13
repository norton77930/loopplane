"""The Validator contract and the gating decision (contracts/validator-evaluator.md;
FR-030–FR-034).

The Validator is a host-supplied policy callable that returns exactly one
gating ``ValidationResult``. The layer defines the contract and handles its
outcomes but hardcodes no domain-specific validation logic (FR-033).
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from loopplane.engineering.state import LoopState
    from loopplane.host import RunOutcome

ValidationStatus = Literal["pass", "fail", "needs_repair", "needs_human_review"]

VALIDATION_STATUSES: frozenset[str] = frozenset(
    {"pass", "fail", "needs_repair", "needs_human_review"}
)

# The control decision the Loop Controller selects after validation. ``continue``
# means "a passing iteration that the stop condition has not yet satisfied —
# run another iteration"; it is not one of the spec's terminal/retry/repair
# actions but the bounded next-iteration case of FR-032.
NextAction = Literal[
    "continue",
    "stop_success",
    "stop_failure",
    "retry",
    "repair",
    "human_review",
]


@dataclass(frozen=True)
class ValidationResult:
    """The Validator's single gating output (FR-030, FR-031)."""

    status: ValidationStatus
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Validator(Protocol):
    """Given an iteration's Agent Run outcome and the current Loop State,
    returns exactly one :class:`ValidationResult` (sync or async)."""

    def __call__(
        self, outcome: RunOutcome, state: LoopState
    ) -> ValidationResult | Awaitable[ValidationResult]: ...


def decide(
    status: str,
    *,
    retries_used: int,
    max_retries: int,
    stop_satisfied: bool,
) -> NextAction:
    """Map a validation status to the controller's next action (FR-032).

    Only the four recognized statuses are handled here; an unrecognized or
    raised status is routed to the fail-safe path by the controller *before*
    this function is consulted (FR-034).
    """

    if status == "pass":
        return "stop_success" if stop_satisfied else "continue"
    if status == "needs_repair":
        return "repair"
    if status == "needs_human_review":
        return "human_review"
    if status == "fail":
        return "retry" if retries_used < max_retries else "stop_failure"
    # Defensive: callers guard unknown statuses first; never a silent pass.
    return "human_review"
