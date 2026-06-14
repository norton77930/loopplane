"""The coordinator + result value types for multi-agent orchestration (013).

The coordinator runs a selected set of subagents through the public Phase-3
``run_loop`` and returns one ``SubagentResult`` per selection, in registration
order. It executes no tool and reads each captured ``LoopOutcome`` (it passes no
live event sink) (Constitution V & VI).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from loopplane.engineering import LoopDefinition, LoopOutcome, RunReference, run_loop
from loopplane.orchestration.registry import AgentRegistry

# A delegation policy selects which registered subagents the coordinator runs.
DelegationPolicy = Callable[[AgentRegistry], Sequence[str]]


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

    async def run(self, selection: Sequence[str]) -> tuple[SubagentResult, ...]:
        """Run exactly the selected subagents (deduped, each once) in
        **registration order**, then any unknown names as not-found results.
        Each subagent is driven through the public ``run_loop`` (FR-010, FR-011,
        FR-003)."""

        selected = list(dict.fromkeys(selection))
        results: list[SubagentResult] = []
        for name in self._registry.names():
            if name not in selected:
                continue
            subagent = self._registry.get(name)
            if subagent is None:  # defensive — registered names always resolve
                continue
            results.append(await self._run_subagent(name, subagent.definition))
        for name in selected:
            if name not in self._registry:
                results.append(
                    SubagentResult(
                        subagent=name, reference=None, outcome=None, failure="not found"
                    )
                )
        return tuple(results)

    async def delegate(self, policy: DelegationPolicy) -> tuple[SubagentResult, ...]:
        """Resolve a delegation policy to a selection, then run it. A raising
        policy is contained — it yields an empty selection (FR-040, FR-041)."""

        try:
            selection = policy(self._registry)
        except Exception:
            selection = ()
        return await self.run(selection)

    async def _run_subagent(
        self, name: str, definition: LoopDefinition
    ) -> SubagentResult:
        # A subagent whose loop run raises is captured per subagent (a fixed,
        # public-safe marker — never the raw exception detail) so the coordinator
        # still completes with the other subagents' results (FR-041, NFR-005/006).
        try:
            outcome = await run_loop(definition)
        except Exception:
            return SubagentResult(
                subagent=name, reference=None, outcome=None, failure="failed"
            )
        reference = ChildRunReference(
            subagent=name, loop_id=outcome.loop_id, run_refs=outcome.state.run_refs
        )
        return SubagentResult(
            subagent=name, reference=reference, outcome=outcome, failure=None
        )
