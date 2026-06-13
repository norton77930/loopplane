"""Deterministic, public-safe test helpers for the scheduler layer (feature 004).

Reuses the Phase-3 scripted host/validator helpers; the scheduler fires real
Loop Runs through `run_loop`. No real sleeping — a `VirtualClock` drives time.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
from loopplane.host import RunOutcome
from loopplane.scheduling import SchedulerEvent
from tests.loop_helpers import ScriptedValidator, scripted_host_factory


def always_pass(outcome: RunOutcome, state: LoopState) -> ValidationResult:
    return ValidationResult(status="pass")


def pass_loop_definition(
    loop_id: str = "loop", *, working_scope: Path | None = None
) -> LoopDefinition:
    """A Phase-3 loop that always passes in one iteration; a fresh scripted host
    is built per Loop Run so repeated fires never exhaust the model."""

    return LoopDefinition(
        loop_id=loop_id,
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(
            selector=scripted_host_factory("ok", working_scope=working_scope)
        ),
        validation_policy=ValidationPolicy(validator=always_pass),
        stop_condition=stop_on_pass(),
    )


def pausing_loop_definition(
    loop_id: str = "paused-loop", *, working_scope: Path | None = None
) -> LoopDefinition:
    """A loop whose validator returns ``needs_human_review`` so, with no
    resolver, ``run_loop`` pauses (the scheduler supplies no resolver)."""

    return LoopDefinition(
        loop_id=loop_id,
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(
            selector=scripted_host_factory("ok", working_scope=working_scope)
        ),
        validation_policy=ValidationPolicy(
            validator=ScriptedValidator("needs_human_review")
        ),
        stop_condition=stop_on_pass(),
    )


def scripted_predicate(*values: bool) -> Callable[[], bool]:
    """A condition predicate that returns the given booleans, one per poll;
    repeats the last once exhausted."""

    state = {"i": 0}

    def predicate() -> bool:
        index = min(state["i"], len(values) - 1)
        state["i"] += 1
        return values[index]

    return predicate


def raising_predicate() -> bool:
    raise RuntimeError("predicate boom")


class SchedulerEventRecorder:
    """A Scheduler Event sink that records every emitted event in order."""

    def __init__(self) -> None:
        self.events: list[SchedulerEvent] = []

    async def __call__(self, event: SchedulerEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]
