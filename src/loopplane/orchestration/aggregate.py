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


@dataclass(frozen=True)
class AggregatedArtifact:
    """One subagent artifact reference, projected to metadata only."""

    subagent: str
    session_id: str
    reference: str


def aggregate_artifacts(
    results: Sequence[SubagentResult],
) -> tuple[AggregatedArtifact, ...]:
    """Each subagent's artifact references as ``(subagent, session_id,
    reference)``, grouped by subagent in **result (registration) order**. A
    subagent with no artifacts contributes nothing — only the public-safe
    reference metadata is surfaced, never the artifact content (FR-030, FR-031)."""

    aggregated: list[AggregatedArtifact] = []
    for result in results:
        if result.outcome is None:
            continue
        for ref in result.outcome.state.artifacts:
            aggregated.append(
                AggregatedArtifact(
                    subagent=result.subagent,
                    session_id=ref.session_id,
                    reference=ref.reference,
                )
            )
    return tuple(aggregated)
