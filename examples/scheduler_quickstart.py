"""Runnable example: drive an interval loop on a virtual clock.

Public-safe and credential-free. A `Scheduler` over a `VirtualClock` fires a
scripted Phase-3 loop once per elapsed period — deterministically, with no real
sleeping — and starts every run through the Phase-3 `run_loop` entry point.

Run::

    python examples/scheduler_quickstart.py
"""

from __future__ import annotations

from pathlib import Path

import anyio

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopState,
    ManualTrigger,
    StaticInput,
    ValidationPolicy,
    ValidationResult,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RunOutcome, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from loopplane.scheduling import Scheduler, VirtualClock


def _always_pass(outcome: RunOutcome, state: LoopState) -> ValidationResult:
    return ValidationResult(status="pass")


def _loop_definition(working_scope: Path) -> LoopDefinition:
    def build_host() -> LoopPlaneHost:
        model = ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="tick")])],
            context_capacity=100_000,
        )
        return LoopPlaneHost(RuntimeConfig(model=model), working_scope=working_scope)

    return LoopDefinition(
        loop_id="nightly",
        trigger=ManualTrigger(),
        input_source=StaticInput("do the nightly job"),
        host_profile=HostRuntimeProfile(selector=build_host),
        validation_policy=ValidationPolicy(validator=_always_pass),
        stop_condition=stop_on_pass(),
    )


async def run_demo(working_scope: Path | None = None) -> int:
    scope = working_scope or Path.cwd()
    clock = VirtualClock()
    scheduler = Scheduler(clock)
    scheduler.register_interval(
        "nightly", _loop_definition(scope), interval_seconds=60.0
    )

    total = 0
    for _ in range(3):
        clock.advance(60.0)  # one period — a virtual clock, never the wall clock
        outcomes = await scheduler.poll()
        total += len(outcomes)
        state = scheduler.trigger_state("nightly")
        print(
            f"clock={clock.now():>5.0f}  fired={len(outcomes)}  "
            f"fire_count={state.fire_count}  next_due={state.next_due:.0f}"
        )

    print(f"total Scheduled Loop Runs: {total}")
    return total


if __name__ == "__main__":
    anyio.run(run_demo)
