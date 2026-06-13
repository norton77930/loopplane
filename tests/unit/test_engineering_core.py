"""Foundational unit tests for the loop-engineering layer (feature 003, EA).

Covers Loop Definition validation, the status->action mapping, the bounded stop
conditions, and Loop State reconstruction from the event stream — all host-free.
"""

from __future__ import annotations

import dataclasses

import pytest

from loopplane.engineering import (
    EvaluationResult,
    HostRuntimeProfile,
    LoopDefinition,
    LoopDefinitionError,
    LoopEvent,
    LoopState,
    ManualTrigger,
    RepairPolicy,
    RunReference,
    StaticInput,
    StopCondition,
    ValidationPolicy,
    ValidationResult,
    decide,
    max_iterations,
    reconstruct_state,
    stop_on_pass,
    stop_when_score_at_least,
    validate_definition,
)
from loopplane.host import RuntimeConfig
from loopplane.model import ScriptedModel
from tests.loop_helpers import AppendRepairInstruction, ScriptedValidator


def _valid_definition(**overrides: object) -> LoopDefinition:
    config = RuntimeConfig(model=ScriptedModel(script=[], context_capacity=100))
    base = LoopDefinition(
        loop_id="L",
        trigger=ManualTrigger(),
        input_source=StaticInput("hi"),
        host_profile=HostRuntimeProfile(config=config),
        validation_policy=ValidationPolicy(validator=ScriptedValidator("pass")),
        stop_condition=stop_on_pass(),
    )
    return dataclasses.replace(base, **overrides)


# --- Definition validation (FR-001, FR-013) ---


def test_valid_definition_passes_validation() -> None:
    validate_definition(_valid_definition())


def test_empty_loop_id_is_rejected() -> None:
    with pytest.raises(LoopDefinitionError, match="loop_id"):
        validate_definition(_valid_definition(loop_id=""))


def test_host_profile_with_neither_config_nor_selector_is_rejected() -> None:
    with pytest.raises(LoopDefinitionError, match="config.*selector"):
        validate_definition(_valid_definition(host_profile=HostRuntimeProfile()))


def test_host_profile_with_both_config_and_selector_is_rejected() -> None:
    config = RuntimeConfig(model=ScriptedModel(script=[], context_capacity=100))
    profile = HostRuntimeProfile(config=config, selector=lambda: None)  # type: ignore[arg-type,return-value]
    with pytest.raises(LoopDefinitionError, match="exactly one"):
        validate_definition(_valid_definition(host_profile=profile))


def test_stop_condition_without_a_finite_bound_is_rejected() -> None:
    unbounded = StopCondition(predicate=lambda state: False, max_iterations=0)
    with pytest.raises(LoopDefinitionError, match="max_iterations"):
        validate_definition(_valid_definition(stop_condition=unbounded))


def test_repair_enabled_without_instruction_source_is_rejected() -> None:
    with pytest.raises(LoopDefinitionError, match="instruction_source"):
        validate_definition(_valid_definition(repair_policy=RepairPolicy(enabled=True)))


def test_repair_enabled_with_instruction_source_passes() -> None:
    policy = RepairPolicy(enabled=True, instruction_source=AppendRepairInstruction())
    validate_definition(_valid_definition(repair_policy=policy))


# --- decide(): status -> next action (FR-032) ---


def test_decide_pass_stops_when_stop_condition_satisfied() -> None:
    assert (
        decide("pass", retries_used=0, max_retries=0, stop_satisfied=True)
        == "stop_success"
    )


def test_decide_pass_continues_when_stop_not_satisfied() -> None:
    assert (
        decide("pass", retries_used=0, max_retries=0, stop_satisfied=False)
        == "continue"
    )


def test_decide_fail_retries_until_exhausted() -> None:
    assert (
        decide("fail", retries_used=0, max_retries=2, stop_satisfied=False) == "retry"
    )
    assert (
        decide("fail", retries_used=1, max_retries=2, stop_satisfied=False) == "retry"
    )
    assert (
        decide("fail", retries_used=2, max_retries=2, stop_satisfied=False)
        == "stop_failure"
    )


def test_decide_repair_and_human_review() -> None:
    assert (
        decide("needs_repair", retries_used=0, max_retries=0, stop_satisfied=False)
        == "repair"
    )
    assert (
        decide(
            "needs_human_review", retries_used=0, max_retries=0, stop_satisfied=False
        )
        == "human_review"
    )


# --- Stop conditions (FR-007, FR-013) ---


def test_stop_on_pass_is_satisfied_only_after_a_pass() -> None:
    condition = stop_on_pass()
    assert condition.max_iterations == 1
    empty = LoopState(loop_id="L", loop_definition_id="L")
    assert not condition.satisfied(empty)
    passed = LoopState(
        loop_id="L",
        loop_definition_id="L",
        latest_validation=ValidationResult(status="pass"),
    )
    assert condition.satisfied(passed)
    failed = LoopState(
        loop_id="L",
        loop_definition_id="L",
        latest_validation=ValidationResult(status="fail"),
    )
    assert not condition.satisfied(failed)


def test_max_iterations_condition_stops_at_the_bound() -> None:
    condition = max_iterations(3)
    assert condition.max_iterations == 3
    state = LoopState(loop_id="L", loop_definition_id="L", iteration_index=2)
    assert not condition.satisfied(state)
    state.iteration_index = 3
    assert condition.satisfied(state)


def test_score_threshold_condition_reads_the_evaluation() -> None:
    condition = stop_when_score_at_least(0.9, max_iterations=5)
    low = LoopState(
        loop_id="L",
        loop_definition_id="L",
        latest_evaluation=EvaluationResult(score=0.5),
    )
    assert not condition.satisfied(low)
    high = LoopState(
        loop_id="L",
        loop_definition_id="L",
        latest_evaluation=EvaluationResult(score=0.95),
    )
    assert condition.satisfied(high)


def test_zero_max_iterations_constructor_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        max_iterations(0)


# --- Loop State reconstruction (FR-062, SC-006) ---


def test_reconstruct_state_rebuilds_from_the_event_stream_alone() -> None:
    events = [
        LoopEvent("loop_started", 0, "L", "defL"),
        LoopEvent(
            "loop_iteration_started",
            1,
            "L",
            "defL",
            iteration_index=1,
            payload={"kind": "initial"},
        ),
        LoopEvent(
            "loop_iteration_completed",
            2,
            "L",
            "defL",
            iteration_index=1,
            session_id="s1",
            payload={"termination_reason": "natural-completion"},
        ),
        LoopEvent(
            "validation_completed",
            3,
            "L",
            "defL",
            iteration_index=1,
            session_id="s1",
            payload={"status": "pass", "reason": "looks good"},
        ),
        LoopEvent(
            "loop_completed",
            4,
            "L",
            "defL",
            iteration_index=1,
            payload={"stop_reason": "validation passed"},
        ),
    ]

    state = reconstruct_state(events)

    assert state.loop_id == "L"
    assert state.loop_definition_id == "defL"
    assert state.iteration_index == 1
    assert state.run_refs == (RunReference("s1", "natural-completion"),)
    assert state.latest_validation == ValidationResult(
        status="pass", reason="looks good"
    )
    assert state.stop_reason == "validation passed"
    assert state.approval_status == "none"


def test_reconstruct_state_rejects_an_empty_stream() -> None:
    with pytest.raises(ValueError, match="empty event stream"):
        reconstruct_state([])
