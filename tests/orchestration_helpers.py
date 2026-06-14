"""Shared in-process harness for the Multi-Agent Orchestration suites (013).

A public-safe, deterministic builder for a runnable subagent — a single-iteration
``LoopDefinition`` over a scripted model (reusing the unit-003 loop helpers). No
real model, no network.
"""

from __future__ import annotations

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from tests.loop_helpers import ScriptedValidator


def _scripted_host(text: str) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(RuntimeConfig(model=model))


def scripted_subagent_definition(
    name: str, *, text: str = "done", fail: bool = False
) -> LoopDefinition:
    """A public-safe single-iteration loop definition over a scripted model — a
    runnable subagent that passes validation and emits loop events.

    ``fail=True`` makes building the host raise, to exercise the coordinator's
    fail-safe capture.
    """

    def selector() -> LoopPlaneHost:
        if fail:
            raise RuntimeError("subagent host build failed")
        return _scripted_host(text)

    return LoopDefinition(
        loop_id=name,
        trigger=ManualTrigger(),
        input_source=StaticInput("run"),
        host_profile=HostRuntimeProfile(selector=selector),  # type: ignore[arg-type]
        validation_policy=ValidationPolicy(validator=ScriptedValidator("pass")),
        stop_condition=stop_on_pass(),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )
