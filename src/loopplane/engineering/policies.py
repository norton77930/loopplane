"""Loop Definition policies (contracts/loop-definition.md; FR-004–FR-009,
FR-051–FR-052).

Small, declarative, public-safe policy holders that the Loop Definition carries.
Retry and repair are expressible independently — retry as count+backoff, repair
as enablement+instruction — preserving the retry-vs-repair distinction
(FR-006, FR-050).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from loopplane.engineering.state import ArtifactRef, RunReference
from loopplane.engineering.validation import ValidationStatus

if TYPE_CHECKING:
    from loopplane.engineering.evaluation import Evaluator
    from loopplane.engineering.validation import Validator


class BackoffContract(Protocol):
    """The delay schedule between retry attempts (FR-051).

    Returns a delay value only — the layer performs no in-process sleeping; a
    host may enact the delay.
    """

    def delay_seconds(self, attempt: int) -> float: ...


@dataclass(frozen=True)
class ConstantBackoff:
    """A fixed delay between attempts (default zero)."""

    seconds: float = 0.0

    def delay_seconds(self, attempt: int) -> float:
        return self.seconds


NO_BACKOFF: BackoffContract = ConstantBackoff(0.0)


@dataclass(frozen=True)
class RepairContext:
    """The previous-run context handed to a repair instruction source (FR-052)."""

    prior_run: RunReference
    validation_reason: str | None = None
    validation_metadata: Mapping[str, Any] = field(default_factory=dict)
    reused_artifacts: tuple[ArtifactRef, ...] = ()


class RepairInstructionSource(Protocol):
    """Produces the corrective instruction injected into a repair iteration
    (FR-052)."""

    def instruction(self, context: RepairContext) -> str: ...


@dataclass(frozen=True)
class ValidationPolicy:
    """Identifies the Validator the controller applies each iteration (FR-004)."""

    validator: Validator


@dataclass(frozen=True)
class EvaluationPolicy:
    """Identifies the optional Evaluator (FR-005, FR-040)."""

    evaluator: Evaluator


@dataclass(frozen=True)
class RetryPolicy:
    """Maximum retry count plus a backoff contract (FR-006, FR-051)."""

    max_retries: int = 0
    backoff: BackoffContract = NO_BACKOFF


@dataclass(frozen=True)
class RepairPolicy:
    """Repair enablement plus an instruction source (FR-006, FR-052)."""

    enabled: bool = False
    instruction_source: RepairInstructionSource | None = None


@dataclass(frozen=True)
class ArtifactPolicy:
    """Whether prior-iteration artifacts may be reused, by reference (FR-008)."""

    reuse: bool = False


@dataclass(frozen=True)
class ApprovalPolicy:
    """When loop-level human review is required (FR-009, FR-034, FR-082)."""

    require_human_review_on: frozenset[ValidationStatus] = frozenset(
        {"needs_human_review"}
    )
    human_review_available: bool = True


@dataclass(frozen=True)
class ObservationPolicy:
    """Whether loop-level observation is emitted; defaults off (FR-009, NFR-005)."""

    emit_loop_events: bool = False
