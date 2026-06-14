"""Aggregated, metadata-only views over coordinated subagents (013).

Each subagent's captured ``LoopOutcome`` carries its recorded, sequence-ordered
loop events and its artifact references. Aggregation flattens these into
registration-ordered, metadata-only records — never a ``LoopEvent.payload``,
conversation content, tool I/O, or a secret (FR-020/FR-021, NFR-006).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from loopplane.orchestration.coordinator import SubagentResult


@dataclass(frozen=True)
class AggregatedEvent:
    """One subagent loop event, projected to metadata only."""

    subagent: str
    type: str
    sequence: int


def aggregate_events(results: Sequence[SubagentResult]) -> tuple[AggregatedEvent, ...]:
    """Each subagent's loop events as ``(subagent, type, sequence)``, grouped by
    subagent in **result (registration) order** and ordered by sequence within a
    subagent. A result with no outcome contributes nothing (FR-020, FR-021)."""

    aggregated: list[AggregatedEvent] = []
    for result in results:
        if result.outcome is None:
            continue
        for event in result.outcome.events:
            aggregated.append(
                AggregatedEvent(
                    subagent=result.subagent,
                    type=event.type,
                    sequence=event.sequence,
                )
            )
    return tuple(aggregated)
