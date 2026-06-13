"""Runnable example: plug validator/evaluator packs into a loop.

Public-safe and credential-free. Composes packs into a Loop Definition's
validation and evaluation policies and runs one Loop Run through the Phase-3
`run_loop` — showing how the loop gates on the packs' decisions.

Run::

    python examples/packs_quickstart.py
"""

from __future__ import annotations

from pathlib import Path

import anyio

from loopplane.engineering import (
    EvaluationPolicy,
    HostRuntimeProfile,
    LoopDefinition,
    LoopOutcome,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    run_loop,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from loopplane.packs import (
    all_of,
    artifact_presence_validator,
    length_evaluator,
    text_validator,
)


def _scripted_host(text: str, working_scope: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(RuntimeConfig(model=model), working_scope=working_scope)


async def run_demo(working_scope: Path | None = None) -> LoopOutcome:
    scope = working_scope or Path.cwd()

    # Gate on: the output contains "done" AND no artifact was produced.
    validator = all_of(
        text_validator(mode="contains", pattern="done"),
        artifact_presence_validator(require=False),
    )
    definition = LoopDefinition(
        loop_id="packs-demo",
        trigger=ManualTrigger(),
        input_source=StaticInput("do the task"),
        host_profile=HostRuntimeProfile(
            selector=lambda: _scripted_host("report: task done", scope)
        ),
        validation_policy=ValidationPolicy(validator=validator),
        evaluation_policy=EvaluationPolicy(evaluator=length_evaluator(target_chars=20)),
        stop_condition=stop_on_pass(),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )

    outcome = await run_loop(definition)

    print(f"loop terminal: {outcome.terminal_event} -> {outcome.stop_reason}")
    if outcome.state.latest_evaluation is not None:
        print(f"length evaluator score: {outcome.state.latest_evaluation.score}")
    return outcome


if __name__ == "__main__":
    anyio.run(run_demo)
