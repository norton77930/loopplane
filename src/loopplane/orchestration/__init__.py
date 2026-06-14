"""LoopPlane Multi-Agent Orchestration (feature 013).

Run several agent loops as subagents and combine their results: an agent registry
(named subagents = loop definitions), a coordinator that runs a selected set
through the public Phase-3 entry point (``run_loop``), child run references, and
deterministic, metadata-only aggregated event / artifact views. It executes no
tool itself and consumes each subagent's recorded loop events as a consumer
(Constitution V & VI). It composes only the public Phase-3 loop surface
(:mod:`loopplane.engineering`).
"""

from __future__ import annotations

from loopplane.orchestration.aggregate import (
    AggregatedArtifact,
    AggregatedEvent,
    aggregate_artifacts,
    aggregate_events,
)
from loopplane.orchestration.coordinator import (
    ChildRunReference,
    Coordinator,
    DelegationPolicy,
    SubagentResult,
)
from loopplane.orchestration.registry import (
    AgentRegistry,
    DuplicateSubagentError,
    Subagent,
)

__all__ = [
    "AgentRegistry",
    "AggregatedArtifact",
    "AggregatedEvent",
    "ChildRunReference",
    "Coordinator",
    "DelegationPolicy",
    "DuplicateSubagentError",
    "Subagent",
    "SubagentResult",
    "aggregate_artifacts",
    "aggregate_events",
]
