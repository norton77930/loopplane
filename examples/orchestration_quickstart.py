"""Runnable example: register subagents, coordinate them, aggregate results.

Public-safe and credential-free. Three scripted subagents are registered in an
``AgentRegistry``; a ``Coordinator`` runs a selected set in **registration order**
through the public Phase-3 ``run_loop``, and the aggregated event / artifact views
are printed — metadata only (subagent / type / sequence / reference), never
conversation content, tool I/O, or a secret. The orchestration layer executes no
tool itself and re-emits no live bus (Constitution V & VI).

Run::

    python examples/orchestration_quickstart.py
"""

from __future__ import annotations

import anyio

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopState,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    ValidationResult,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RunOutcome, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from loopplane.orchestration import (
    AgentRegistry,
    Coordinator,
    aggregate_artifacts,
    aggregate_events,
)


def _always_pass(outcome: RunOutcome, state: LoopState) -> ValidationResult:
    return ValidationResult(status="pass", reason="scripted demo always passes")


def _subagent_definition(name: str) -> LoopDefinition:
    """A public-safe single-iteration subagent over a scripted model."""

    def build_host() -> LoopPlaneHost:
        model = ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text=f"{name} done")])],
            context_capacity=100_000,
        )
        return LoopPlaneHost(RuntimeConfig(model=model))

    return LoopDefinition(
        loop_id=name,
        trigger=ManualTrigger(),
        input_source=StaticInput("run"),
        host_profile=HostRuntimeProfile(selector=build_host),
        validation_policy=ValidationPolicy(validator=_always_pass),
        stop_condition=stop_on_pass(),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )


async def run_demo() -> None:
    registry = AgentRegistry()
    for name in ("researcher", "writer", "reviewer"):
        registry.register(name, _subagent_definition(name))

    coordinator = Coordinator(registry)

    # Coordinate a selected set: deduped, run once each, in registration order
    # (independent of the selection order); an unknown name is captured as a
    # not-found result rather than crashing.
    results = await coordinator.run(["reviewer", "researcher", "ghost"])

    print("Coordinated results (registration order):")
    for result in results:
        if result.failure is not None:
            print(f"  {result.subagent:<11} failure: {result.failure}")
            continue
        reference = result.reference
        outcome = result.outcome
        assert reference is not None and outcome is not None
        print(
            f"  {result.subagent:<11} loop_id={reference.loop_id} "
            f"runs={len(reference.run_refs)} terminal={outcome.stop_reason}"
        )

    # Aggregated, metadata-only event view: (subagent, type, sequence).
    print("\nAggregated events (subagent / type / sequence):")
    for event in aggregate_events(results):
        print(f"  {event.subagent:<11} {event.type:<22} #{event.sequence}")

    # Aggregated artifact view — scripted text runs produce no artifacts, so this
    # is empty; a real run's references would appear here, metadata only.
    artifacts = aggregate_artifacts(results)
    print(f"\nAggregated artifacts: {len(artifacts)} (scripted runs produce none)")

    # Delegation: a policy chooses which registered subagents run; a raising
    # policy or an empty selection is contained as an empty result.
    delegated = await coordinator.delegate(lambda registry: ["writer"])
    print("Delegated selection ->", [result.subagent for result in delegated])


if __name__ == "__main__":
    anyio.run(run_demo)
