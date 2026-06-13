"""Loop and run diagnostics — metadata summaries over recorded event streams
(contracts/observability.md; FR-010-FR-021).

``loop_diagnostics`` reuses the Phase-3 ``reconstruct_state`` for the latest-state
fields (no re-implementation). Every summary is metadata-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loopplane.engineering import reconstruct_state
from loopplane.inspect.base import count_by_type

if TYPE_CHECKING:
    from loopplane.engineering import LoopEvent
    from loopplane.events import RuntimeEvent

_TERMINAL = ("loop_completed", "loop_failed")


@dataclass(frozen=True)
class LoopDiagnostics:
    iterations: int
    runs: int
    retries: int
    repairs: int
    human_reviews: int
    latest_validation_status: str | None
    latest_evaluation_label: str | None
    terminal_status: str | None


def loop_diagnostics(events: Sequence[LoopEvent]) -> LoopDiagnostics:
    """Summarize a recorded Loop Event stream: counts by type plus the latest
    outcomes and terminal status (reusing ``reconstruct_state``). An empty stream
    yields an empty report; an unknown loop type is skipped (FR-010, FR-011)."""

    if not events:
        return LoopDiagnostics(0, 0, 0, 0, 0, None, None, None)

    state = reconstruct_state(events)
    terminal_status: str | None = None
    for event in events:
        if event.type in _TERMINAL:
            terminal_status = event.type

    validation = state.latest_validation
    evaluation = state.latest_evaluation
    return LoopDiagnostics(
        iterations=count_by_type(events, "loop_iteration_completed"),
        runs=len(state.run_refs),
        retries=count_by_type(events, "retry_scheduled"),
        repairs=count_by_type(events, "repair_requested"),
        human_reviews=count_by_type(events, "human_review_requested"),
        latest_validation_status=validation.status if validation is not None else None,
        latest_evaluation_label=evaluation.label if evaluation is not None else None,
        terminal_status=terminal_status,
    )


@dataclass(frozen=True)
class RunDiagnostics:
    tool_calls: int
    turns: int
    errors: int
    termination_reason: str | None


def run_diagnostics(events: Sequence[RuntimeEvent]) -> RunDiagnostics:
    """Summarize a recorded Runtime Event stream: tool-call / turn / error counts
    by type and the termination reason — metadata only. An empty stream yields a
    zero/``None`` report; an unknown type is skipped (FR-020, FR-021)."""

    termination_reason: str | None = None
    for event in events:
        if event.type == "run-terminated":
            termination_reason = event.payload.reason
    return RunDiagnostics(
        tool_calls=count_by_type(events, "tool-call-started"),
        turns=count_by_type(events, "turn-completed"),
        errors=count_by_type(events, "diagnostic"),
        termination_reason=termination_reason,
    )
