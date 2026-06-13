"""US4: score or label iterations with an optional evaluator (spec US4;
FR-040–FR-043).

Evaluation is optional and non-gating: it informs a score-threshold stop but
never decides retry or repair, an evaluator error is non-fatal, and an absent
policy leaves the loop running on validation alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import (
    EvaluationPolicy,
    HostRuntimeProfile,
    LoopDefinition,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    run_loop,
    stop_on_pass,
    stop_when_score_at_least,
)
from tests.loop_helpers import (
    LoopEventRecorder,
    RaisingEvaluator,
    ScriptedEvaluator,
    ScriptedValidator,
    scripted_host,
)

pytestmark = pytest.mark.anyio


def _def(*, host: object, validator: object, **overrides: object) -> LoopDefinition:
    base = dict(
        loop_id="scored",
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(selector=lambda: host),
        validation_policy=ValidationPolicy(validator=validator),
        stop_condition=stop_on_pass(max_iterations=3),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )
    base.update(overrides)
    return LoopDefinition(**base)  # type: ignore[arg-type]


async def test_score_threshold_stop_halts_at_the_right_iteration(
    tmp_path: Path,
) -> None:
    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        validator=ScriptedValidator("pass"),
        evaluation_policy=EvaluationPolicy(evaluator=ScriptedEvaluator(0.95)),
        stop_condition=stop_when_score_at_least(0.9, max_iterations=3),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_completed"
    assert outcome.state.latest_evaluation is not None
    assert outcome.state.latest_evaluation.score == 0.95
    assert recorder.types[-2:] == ["evaluation_completed", "loop_completed"]


async def test_evaluation_is_non_gating(tmp_path: Path) -> None:
    # A low score with a passing validator and stop_on_pass must still stop on
    # the pass — evaluation alone never forces retry/repair (FR-041).
    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        validator=ScriptedValidator("pass"),
        evaluation_policy=EvaluationPolicy(evaluator=ScriptedEvaluator(0.1)),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_completed"
    assert outcome.state.latest_evaluation is not None
    assert outcome.state.latest_evaluation.score == 0.1
    assert "evaluation_completed" in recorder.types
    assert "retry_scheduled" not in recorder.types
    assert "repair_requested" not in recorder.types


async def test_no_evaluation_policy_runs_no_evaluation_step(tmp_path: Path) -> None:
    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        validator=ScriptedValidator("pass"),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_completed"
    assert "evaluation_completed" not in recorder.types
    assert outcome.state.latest_evaluation is None


async def test_evaluator_error_is_non_fatal(tmp_path: Path) -> None:
    definition = _def(
        host=scripted_host("x", working_scope=tmp_path),
        validator=ScriptedValidator("pass"),
        evaluation_policy=EvaluationPolicy(evaluator=RaisingEvaluator()),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    # The iteration proceeds on the validation result; the evaluator error is a
    # non-fatal diagnostic and emits no evaluation_completed (FR-043).
    assert outcome.terminal_event == "loop_completed"
    assert "evaluation_completed" not in recorder.types
    assert outcome.state.latest_evaluation is None
    assert any("evaluator raised" in d for d in outcome.diagnostics)
