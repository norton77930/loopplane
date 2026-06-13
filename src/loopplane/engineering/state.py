"""Loop State and its event-stream reconstruction
(contracts/loop-events.md; FR-060–FR-064).

Loop State is the outer per-run record, **held in process**, that references
Phase-1/2 state only by identifier or reference — never copying or owning Run
State, conversation history, or artifact bytes (FR-061, FR-063). It is
reconstructable from the ordered Loop Event stream (FR-062, SC-006). Durable
persistence and loop resume are reserved extension points, not built here
(FR-064).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from loopplane.engineering.evaluation import EvaluationResult
from loopplane.engineering.events import LoopEvent
from loopplane.engineering.validation import ValidationResult, ValidationStatus

if TYPE_CHECKING:
    from loopplane.host import RunOutcome

ApprovalStatus = Literal["none", "pending", "approved", "rejected"]


@dataclass(frozen=True)
class RunReference:
    """An Agent Run, referenced by its session id and terminal reason — the
    only run data Loop State keeps (FR-061)."""

    session_id: str
    termination_reason: str


@dataclass(frozen=True)
class ArtifactRef:
    """An artifact, referenced by its owning session and stable reference;
    resolvable only via ``host.retrieve_artifact`` (FR-053, FR-083)."""

    session_id: str
    reference: str


@dataclass
class LoopState:
    """The outer per-run record (FR-060). Mutable and controller-owned; holds
    references only."""

    loop_id: str
    loop_definition_id: str
    iteration_index: int = 0
    run_refs: tuple[RunReference, ...] = ()
    latest_validation: ValidationResult | None = None
    latest_evaluation: EvaluationResult | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    approval_status: ApprovalStatus = "none"
    stop_reason: str | None = None


def reconstruct_state(
    events: Sequence[LoopEvent],
    outcomes: Mapping[str, RunOutcome] | None = None,
) -> LoopState:
    """Rebuild Loop State from the ordered Loop Event stream alone (FR-062,
    FR-073, SC-006).

    The event stream is sufficient: ``loop_iteration_completed`` events carry
    each run's ``session_id`` and terminal reason, ``validation_completed`` /
    ``evaluation_completed`` carry the latest results, and the terminal event
    carries the stop reason. ``outcomes`` is accepted for cross-checking but is
    not required.
    """

    if not events:
        raise ValueError("cannot reconstruct Loop State from an empty event stream")

    first = events[0]
    state = LoopState(
        loop_id=first.loop_id, loop_definition_id=first.loop_definition_id
    )

    run_refs: list[RunReference] = []
    for event in events:
        if event.iteration_index is not None:
            state.iteration_index = max(state.iteration_index, event.iteration_index)

        if event.type == "loop_iteration_completed" and event.session_id is not None:
            reason = str(event.payload.get("termination_reason", "unknown"))
            run_refs.append(
                RunReference(session_id=event.session_id, termination_reason=reason)
            )
        elif event.type == "validation_completed":
            status = event.payload.get("status")
            if status in {"pass", "fail", "needs_repair", "needs_human_review"}:
                state.latest_validation = ValidationResult(
                    status=_as_status(str(status)),
                    reason=_as_str_or_none(event.payload.get("reason")),
                )
        elif event.type == "evaluation_completed":
            state.latest_evaluation = EvaluationResult(
                score=_as_float_or_none(event.payload.get("score")),
                label=_as_str_or_none(event.payload.get("label")),
                reason=_as_str_or_none(event.payload.get("reason")),
            )
        elif event.type == "human_review_requested":
            state.approval_status = "pending"
        elif event.type in {"loop_completed", "loop_failed"}:
            state.stop_reason = _as_str_or_none(event.payload.get("stop_reason"))
            if state.approval_status == "pending":
                state.approval_status = (
                    "approved" if event.type == "loop_completed" else "rejected"
                )

    state.run_refs = tuple(run_refs)
    return state


def _as_status(value: str) -> ValidationStatus:
    # value is pre-checked against the closed status set by the caller.
    return value  # type: ignore[return-value]


def _as_str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_float_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
