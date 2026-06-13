"""Runnable example: define and manually run a single-iteration LoopPlane loop.

Public-safe and credential-free. A scripted model plus an always-pass validator
drive exactly one Agent Run **through the Host Application Interface** and print
the ordered Loop Event stream and the outcome — with the loop touching no
Phase-1 internal.

Run::

    python examples/loop_quickstart.py
"""

from __future__ import annotations

from pathlib import Path

import anyio

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopEvent,
    LoopOutcome,
    LoopState,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    ValidationResult,
    run_loop,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RunOutcome, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement


def _scripted_model(text: str) -> ScriptedModel:
    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
        context_capacity=100_000,
    )


def _always_pass(outcome: RunOutcome, state: LoopState) -> ValidationResult:
    """A one-line validator: every iteration passes (FR-033 — validation is a
    host-supplied policy, not loop-internal logic)."""

    return ValidationResult(status="pass", reason="scripted demo always passes")


async def run_demo(working_scope: Path | None = None) -> LoopOutcome:
    config = RuntimeConfig(model=_scripted_model("hello from a scripted run"))

    def build_host() -> LoopPlaneHost:
        return LoopPlaneHost(config, working_scope=working_scope or Path.cwd())

    definition = LoopDefinition(
        loop_id="quickstart-echo",
        trigger=ManualTrigger(),
        input_source=StaticInput("please echo hello"),
        host_profile=HostRuntimeProfile(selector=build_host),
        validation_policy=ValidationPolicy(validator=_always_pass),
        stop_condition=stop_on_pass(),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )

    events: list[LoopEvent] = []

    async def on_loop_event(event: LoopEvent) -> None:
        events.append(event)

    outcome = await run_loop(definition, on_loop_event=on_loop_event)

    print("Loop Event stream:")
    for event in events:
        suffix = f"  [{event.payload}]" if event.payload else ""
        print(f"  {event.sequence:>2}  {event.type}{suffix}")
    run_ref = outcome.state.run_refs[0]
    print(f"\nAgent Run (by reference): {run_ref.session_id}")
    print(f"  terminal reason: {run_ref.termination_reason}")
    print(f"loop terminal: {outcome.terminal_event} -> {outcome.stop_reason}")
    return outcome


if __name__ == "__main__":
    anyio.run(run_demo)
