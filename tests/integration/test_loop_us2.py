"""US2: gate a loop on validation outcomes (spec US2; SC-003).

Each of the four validation statuses maps to a defined, observable loop decision
and Loop Event, including the fail-safe path for a raised or unrecognized status
(never a silent pass).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import (
    ApprovalPolicy,
    HostRuntimeProfile,
    LoopDefinition,
    ManualTrigger,
    ObservationPolicy,
    RepairPolicy,
    StaticInput,
    ValidationPolicy,
    run_loop,
    stop_on_pass,
)
from tests.loop_helpers import (
    AppendRepairInstruction,
    LoopEventRecorder,
    RaisingValidator,
    ScriptedValidator,
    UnknownStatusValidator,
    scripted_host,
)

pytestmark = pytest.mark.anyio


def _definition(
    *, host: object, validator: object, **overrides: object
) -> LoopDefinition:
    base = dict(
        loop_id="gated",
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(selector=lambda: host),
        validation_policy=ValidationPolicy(validator=validator),
        stop_condition=stop_on_pass(max_iterations=3),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )
    base.update(overrides)
    return LoopDefinition(**base)  # type: ignore[arg-type]


async def test_pass_stops_with_loop_completed(tmp_path: Path) -> None:
    definition = _definition(
        host=scripted_host("ok", working_scope=tmp_path),
        validator=ScriptedValidator("pass"),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_completed"
    assert recorder.types[-2:] == ["validation_completed", "loop_completed"]


async def test_needs_repair_emits_repair_requested_and_repairs(tmp_path: Path) -> None:
    definition = _definition(
        host=scripted_host("first", "second", working_scope=tmp_path),
        validator=ScriptedValidator("needs_repair", "pass"),
        repair_policy=RepairPolicy(
            enabled=True, instruction_source=AppendRepairInstruction()
        ),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert "repair_requested" in recorder.types
    assert outcome.terminal_event == "loop_completed"
    repair_starts = [
        event
        for event in recorder.events
        if event.type == "loop_iteration_started"
        and event.payload.get("kind") == "repair"
    ]
    assert len(repair_starts) == 1


async def test_needs_human_review_pauses_without_another_run(tmp_path: Path) -> None:
    definition = _definition(
        host=scripted_host("only-one", working_scope=tmp_path),
        validator=ScriptedValidator("needs_human_review"),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.paused
    assert outcome.terminal_event is None
    assert outcome.state.approval_status == "pending"
    assert len(outcome.state.run_refs) == 1
    assert "human_review_requested" in recorder.types
    assert "loop_completed" not in recorder.types
    assert "loop_failed" not in recorder.types


async def test_raised_validator_fails_safe_to_review_never_silent_pass(
    tmp_path: Path,
) -> None:
    definition = _definition(
        host=scripted_host("x", working_scope=tmp_path),
        validator=RaisingValidator(),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.paused
    assert "human_review_requested" in recorder.types
    assert any("validator raised" in d for d in outcome.diagnostics)
    review = next(e for e in recorder.events if e.type == "human_review_requested")
    assert review.payload.get("cause") == "fail_safe"
    assert "loop_completed" not in recorder.types


async def test_unrecognized_status_fails_safe(tmp_path: Path) -> None:
    definition = _definition(
        host=scripted_host("x", working_scope=tmp_path),
        validator=UnknownStatusValidator(),
    )

    outcome = await run_loop(definition)

    assert outcome.paused
    assert any("unrecognized status" in d for d in outcome.diagnostics)


async def test_fail_safe_terminates_when_review_unavailable(tmp_path: Path) -> None:
    definition = _definition(
        host=scripted_host("x", working_scope=tmp_path),
        validator=RaisingValidator(),
        approval_policy=ApprovalPolicy(human_review_available=False),
    )

    outcome = await run_loop(definition)

    assert outcome.terminal_event == "loop_failed"
    assert any("validator raised" in d for d in outcome.diagnostics)
    assert outcome.state.latest_validation is None
