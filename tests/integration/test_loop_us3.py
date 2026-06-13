"""US3: retry transient failures and repair bad output (spec US3; SC-004, SC-005).

Retry re-runs the same input up to the count, then fails; repair re-runs with an
intentionally changed input that injects the repair instruction and prior-run
context — kept distinct, with the Loop Definition never mutated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import (
    ArtifactPolicy,
    ConstantBackoff,
    HostRuntimeProfile,
    LoopDefinition,
    ManualTrigger,
    ObservationPolicy,
    RepairPolicy,
    RetryPolicy,
    StaticInput,
    ValidationPolicy,
    run_loop,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
)
from tests.loop_helpers import (
    AppendRepairInstruction,
    LoopEventRecorder,
    RunOutcomeStubHost,
    ScriptedValidator,
    scripted_host,
)

from .conftest import BIG_TOOL

pytestmark = pytest.mark.anyio


def _def(*, host: object, validator: object, **overrides: object) -> LoopDefinition:
    base = dict(
        loop_id="retry-repair",
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(selector=lambda: host),
        validation_policy=ValidationPolicy(validator=validator),
        stop_condition=stop_on_pass(max_iterations=5),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )
    base.update(overrides)
    return LoopDefinition(**base)  # type: ignore[arg-type]


async def test_retry_count_is_honored_exactly(tmp_path: Path) -> None:
    definition = _def(
        host=scripted_host("a", "b", "c", working_scope=tmp_path),
        validator=ScriptedValidator("fail"),
        retry_policy=RetryPolicy(max_retries=2, backoff=ConstantBackoff(0.25)),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_failed"
    assert len(outcome.state.run_refs) == 3  # initial + 2 retries (SC-004)
    retries = [e for e in recorder.events if e.type == "retry_scheduled"]
    assert [e.payload["attempt"] for e in retries] == [1, 2]
    assert all(e.payload["delay_seconds"] == 0.25 for e in retries)


async def test_zero_retries_emits_no_retry_scheduled(tmp_path: Path) -> None:
    definition = _def(
        host=scripted_host("a", working_scope=tmp_path),
        validator=ScriptedValidator("fail"),
        retry_policy=RetryPolicy(max_retries=0),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_failed"
    assert len(outcome.state.run_refs) == 1
    assert "retry_scheduled" not in recorder.types


async def test_non_natural_termination_maps_to_a_failed_iteration(
    tmp_path: Path,
) -> None:
    # FR-016: a cancelled / non-natural run is a failed iteration subject to the
    # retry policy, never a loop crash, and is not validated.
    stub = RunOutcomeStubHost("cancelled", "cancelled")
    definition = _def(
        host=stub,
        validator=ScriptedValidator("pass"),  # never reached
        retry_policy=RetryPolicy(max_retries=1),
    )
    recorder = LoopEventRecorder()

    outcome = await run_loop(definition, on_loop_event=recorder)

    assert outcome.terminal_event == "loop_failed"
    assert len(outcome.state.run_refs) == 2
    assert recorder.types.count("retry_scheduled") == 1
    assert "validation_completed" not in recorder.types
    assert any("non-naturally" in d for d in outcome.diagnostics)


async def test_repair_input_carries_instruction_and_prior_context(
    tmp_path: Path,
) -> None:
    host = scripted_host("first", "second", working_scope=tmp_path)
    definition = _def(
        host=host,
        validator=ScriptedValidator("needs_repair", "pass", reason="too short"),
        repair_policy=RepairPolicy(
            enabled=True, instruction_source=AppendRepairInstruction()
        ),
    )

    outcome = await run_loop(definition)

    assert outcome.terminal_event == "loop_completed"
    assert len(outcome.state.run_refs) == 2
    # The repair (second) run's submitted input — inspected through the Host
    # Interface — contains the repair instruction and the prior-run context
    # (SC-005), while the original definition is unchanged.
    repair_session = outcome.state.run_refs[1].session_id
    history = host.history_snapshot(repair_session)
    submitted = " ".join(
        block.text
        for entry in history
        if entry.role == "user"
        for block in entry.blocks
        if isinstance(block, TextBlock)
    )
    assert AppendRepairInstruction.PREFIX in submitted
    assert "too short" in submitted
    assert outcome.state.run_refs[0].session_id in submitted
    assert definition.input_source.initial() == "go"  # definition unmutated
    # Default checkpoint decision is reset: each iteration is a fresh Agent Run.
    assert outcome.state.run_refs[0].session_id != outcome.state.run_refs[1].session_id


def _big_tool_twice_model() -> ScriptedModel:
    call = ScriptedTurn(
        increments=[ToolCallRequest(call_id="c", tool_name="big", input={})],
        stop_reason="tool-use",
    )
    close = ScriptedTurn(increments=[TextIncrement(text="stored")])
    return ScriptedModel(script=[call, close, call, close], context_capacity=100_000)


async def test_repair_reuses_prior_artifact_by_reference(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=_big_tool_twice_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(root=tmp_path / "data"),
        ),
        working_scope=tmp_path,
    )
    definition = _def(
        host=host,
        validator=ScriptedValidator("needs_repair", "pass"),
        repair_policy=RepairPolicy(
            enabled=True, instruction_source=AppendRepairInstruction()
        ),
        artifact_policy=ArtifactPolicy(reuse=True),
    )

    outcome = await run_loop(definition)

    assert outcome.terminal_event == "loop_completed"
    assert outcome.state.artifacts  # an artifact reference was captured by ref
    artifact_ref = outcome.state.artifacts[0].reference
    repair_session = outcome.state.run_refs[1].session_id
    history = host.history_snapshot(repair_session)
    submitted = " ".join(
        block.text
        for entry in history
        if entry.role == "user"
        for block in entry.blocks
        if isinstance(block, TextBlock)
    )
    assert artifact_ref in submitted  # reused by reference, not regenerated/copied
