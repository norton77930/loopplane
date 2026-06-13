"""US5: bound triggers and route human review through extension points
(spec US5; SC-007, SC-008).

The manual trigger starts Loop Runs; a host-supplied driver enacts the interval
and condition trigger *contracts* through the same manual entry point; a
``needs_human_review`` outcome pauses and an external decision resumes or
terminates the loop — with no scheduler and no stranded runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import (
    ConditionTrigger,
    EvaluationPolicy,
    HostRuntimeProfile,
    IntervalTrigger,
    LoopDefinition,
    LoopOutcome,
    LoopState,
    ManualTrigger,
    ObservationPolicy,
    ReviewDecision,
    StaticInput,
    Trigger,
    ValidationPolicy,
    run_loop,
    stop_on_pass,
    stop_when_score_at_least,
)
from tests.loop_helpers import (
    LoopEventRecorder,
    ScriptedEvaluator,
    ScriptedValidator,
    scripted_host,
)

pytestmark = pytest.mark.anyio


def _def(
    *, host: object, trigger: Trigger, validator: object, **overrides: object
) -> LoopDefinition:
    base = dict(
        loop_id="bounded",
        trigger=trigger,
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(selector=lambda: host),
        validation_policy=ValidationPolicy(validator=validator),
        stop_condition=stop_on_pass(max_iterations=3),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )
    base.update(overrides)
    return LoopDefinition(**base)  # type: ignore[arg-type]


async def test_manual_trigger_starts_exactly_one_loop_run(tmp_path: Path) -> None:
    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        trigger=ManualTrigger(),
        validator=ScriptedValidator("pass"),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_completed"
    assert recorder.types.count("loop_started") == 1


async def test_interval_and_condition_drivers_use_the_manual_entry_point(
    tmp_path: Path,
) -> None:
    # A host's own driver enacts a tick / satisfied predicate by calling the
    # same manual entry point (run_loop). No in-runtime scheduler exists.
    async def host_driver(definition: LoopDefinition) -> LoopOutcome:
        return await run_loop(definition)

    interval = _def(
        host=scripted_host("x", working_scope=tmp_path),
        trigger=IntervalTrigger(interval_seconds=60.0),
        validator=ScriptedValidator("pass"),
    )
    condition = _def(
        host=scripted_host("y", working_scope=tmp_path),
        trigger=ConditionTrigger(predicate_ref="files-changed"),
        validator=ScriptedValidator("pass"),
    )

    assert (await host_driver(interval)).terminal_event == "loop_completed"
    assert (await host_driver(condition)).terminal_event == "loop_completed"


async def test_human_review_resolver_approval_resumes_to_completion(
    tmp_path: Path,
) -> None:
    async def approve(state: LoopState) -> ReviewDecision:
        return ReviewDecision(approve=True, reason="looks fine")

    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        trigger=ManualTrigger(),
        validator=ScriptedValidator("needs_human_review"),
    )

    outcome = await run_loop(definition, review_resolver=approve)

    assert outcome.terminal_event == "loop_completed"
    assert outcome.state.approval_status == "approved"
    assert not outcome.paused


async def test_human_review_resolver_rejection_terminates(tmp_path: Path) -> None:
    def resolver(state: LoopState) -> ReviewDecision:
        return ReviewDecision(approve=False, reason="not acceptable")

    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        trigger=ManualTrigger(),
        validator=ScriptedValidator("needs_human_review"),
    )

    outcome = await run_loop(definition, review_resolver=resolver)

    assert outcome.terminal_event == "loop_failed"
    assert outcome.state.approval_status == "rejected"
    assert outcome.stop_reason == "not acceptable"


async def test_paused_loop_without_a_decision_never_strands_a_run(
    tmp_path: Path,
) -> None:
    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        trigger=ManualTrigger(),
        validator=ScriptedValidator("needs_human_review"),
    )

    outcome = await run_loop(definition)

    assert outcome.paused
    assert outcome.terminal_event is None
    assert outcome.state.approval_status == "pending"
    assert len(outcome.state.run_refs) == 1  # no further Agent Run started


async def test_never_satisfiable_stop_terminates_at_the_bound(tmp_path: Path) -> None:
    # A passing validator whose score never reaches the threshold keeps the loop
    # continuing; the hard max_iterations bound still terminates it (SC-007).
    definition = _def(
        host=scripted_host("a", "b", "c", working_scope=tmp_path),
        trigger=ManualTrigger(),
        validator=ScriptedValidator("pass"),
        evaluation_policy=EvaluationPolicy(evaluator=ScriptedEvaluator(0.1)),
        stop_condition=stop_when_score_at_least(0.9, max_iterations=3),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_failed"
    assert len(outcome.state.run_refs) == 3
    assert "retry_scheduled" not in recorder.types
    assert outcome.stop_reason is not None
    assert "bound" in outcome.stop_reason
