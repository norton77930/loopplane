"""The coordinator + result value types for multi-agent orchestration (013).

The coordinator runs a selected set of subagents through the public Phase-3
``run_loop`` and returns one ``SubagentResult`` per selection, in registration
order. It executes no tool and reads each captured ``LoopOutcome`` (it passes no
live event sink) (Constitution V & VI).
"""

from __future__ import annotations

from dataclasses import dataclass

from loopplane.engineering import LoopOutcome, RunReference
from loopplane.orchestration.registry import AgentRegistry


@dataclass(frozen=True)
class ChildRunReference:
    """A public-safe reference to a subagent's loop run — metadata only."""

    subagent: str
    loop_id: str
    run_refs: tuple[RunReference, ...]


@dataclass(frozen=True)
class SubagentResult:
    """A subagent's coordinated result: a child reference + outcome on success,
    or a captured failure / not-found."""

    subagent: str
    reference: ChildRunReference | None
    outcome: LoopOutcome | None
    failure: str | None


class Coordinator:
    """Runs selected subagents from a registry and returns their results."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
