"""US1: define and manually run a single-iteration loop (spec US1; SC-001, SC-002).

A loop over a scripted host with an always-pass validator starts exactly one
Agent Run through the Host Application Interface, records reference-only Loop
State, and emits the ordered Loop Event sequence — touching no Phase-1 internal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    run_loop,
    stop_on_pass,
)
from tests.loop_helpers import (
    LoopEventRecorder,
    ScriptedValidator,
    scripted_host,
    scripted_host_factory,
)

pytestmark = pytest.mark.anyio

US1_EVENTS = [
    "loop_started",
    "loop_iteration_started",
    "loop_iteration_completed",
    "validation_completed",
    "loop_completed",
]


def _definition(
    *, selector: object, observe: bool = False, validator: object | None = None
) -> LoopDefinition:
    return LoopDefinition(
        loop_id="echo-once",
        trigger=ManualTrigger(),
        input_source=StaticInput("please echo hello"),
        host_profile=HostRuntimeProfile(selector=selector),  # type: ignore[arg-type]
        validation_policy=ValidationPolicy(
            validator=validator or ScriptedValidator("pass")
        ),
        stop_condition=stop_on_pass(),
        observation_policy=ObservationPolicy(emit_loop_events=observe),
    )


async def test_manual_trigger_starts_exactly_one_agent_run(tmp_path: Path) -> None:
    host = scripted_host("hi there", working_scope=tmp_path)
    definition = _definition(selector=lambda: host)

    outcome = await run_loop(definition)

    assert outcome.terminal_event == "loop_completed"
    assert not outcome.paused
    assert len(outcome.state.run_refs) == 1
    assert outcome.state.run_refs[0].termination_reason == "natural-completion"


async def test_loop_state_references_the_run_and_its_artifacts(tmp_path: Path) -> None:
    host = scripted_host("done", working_scope=tmp_path)
    definition = _definition(selector=lambda: host)

    outcome = await run_loop(definition)
    state = outcome.state

    assert state.loop_id == "echo-once"
    assert state.iteration_index == 1
    session_id = state.run_refs[0].session_id
    assert session_id
    assert state.latest_validation is not None
    assert state.latest_validation.status == "pass"
    # No tool calls in a plain text run => no artifact references (the "any
    # artifacts" of US1.2 is the empty case), and Loop State holds only refs.
    assert state.artifacts == ()


async def test_loop_events_are_emitted_in_order(tmp_path: Path) -> None:
    host = scripted_host("ok", working_scope=tmp_path)
    recorder = LoopEventRecorder()
    definition = _definition(selector=lambda: host, observe=True)

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert recorder.types == US1_EVENTS
    assert outcome.events == tuple(recorder.events)
    sequences = [event.sequence for event in recorder.events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


async def test_boundary_audit_run_goes_through_the_host(tmp_path: Path) -> None:
    host = scripted_host("hi", working_scope=tmp_path)
    definition = _definition(selector=lambda: host)

    outcome = await run_loop(definition)

    # The run reference resolves to a real host session: the Agent Run was
    # started and is known *through* the Host Interface (SC-002), never by a
    # direct Phase-1 path.
    session_id = outcome.state.run_refs[0].session_id
    history = host.history_snapshot(session_id)
    assert [entry.role for entry in history] == ["user", "assistant"]


async def test_two_runs_produce_identical_ordered_streams(tmp_path: Path) -> None:
    factory = scripted_host_factory("hi", working_scope=tmp_path)
    definition = _definition(selector=factory, observe=True)

    first = await run_loop(definition)
    second = await run_loop(definition)

    assert [e.type for e in first.events] == [e.type for e in second.events]
    assert first.terminal_event == second.terminal_event == "loop_completed"
    assert first.stop_reason == second.stop_reason
    assert (
        first.state.latest_validation == second.state.latest_validation  # type: ignore[union-attr]
    )
