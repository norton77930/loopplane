"""US4: the reference runner end-to-end as a deterministic smoke test —
determinism, durable checkpoint, artifact offload/retrieval, and the example
runner (spec US4; SC-002/004, FR-024/030–033/042).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig

from .conftest import (
    BIG_TOOL,
    ECHO_DESCRIPTOR,
    ECHO_TOOL,
    EventCollector,
    big_tool_model,
    text_model,
    tool_then_text_model,
)

pytestmark = pytest.mark.anyio

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from host_quickstart import run_scenario  # noqa: E402


async def test_same_scenario_twice_is_identical(tmp_path: Path) -> None:
    def make_host() -> LoopPlaneHost:
        return LoopPlaneHost(
            RuntimeConfig(model=tool_then_text_model(), tools=(ECHO_TOOL,)),
            working_scope=tmp_path,
        )

    first = EventCollector()
    outcome_one = await make_host().run("go", first)
    second = EventCollector()
    outcome_two = await make_host().run("go", second)

    assert first.types == second.types
    assert outcome_one.termination_reason == outcome_two.termination_reason
    assert outcome_one.turns_taken == outcome_two.turns_taken


async def test_checkpoint_records_are_durable_and_resumable(tmp_path: Path) -> None:
    root = tmp_path / "data"
    host = LoopPlaneHost(
        RuntimeConfig(
            model=tool_then_text_model(),
            tools=(ECHO_TOOL,),
            storage=StorageConfig(root=root),
        ),
        working_scope=tmp_path,
    )
    outcome = await host.run("go", EventCollector())

    # A fresh host over the same storage reconstructs the session from records
    # alone — proving the run was durably recorded (reuses the Phase-1 guarantee).
    reopened = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            tools=(ECHO_TOOL,),
            storage=StorageConfig(root=root),
        ),
        working_scope=tmp_path,
    )
    await reopened.resume(outcome.session_id)
    restored = reopened.history_snapshot(outcome.session_id)

    assert [entry.role for entry in restored] == [
        entry.role for entry in outcome.history
    ]
    assert restored != ()


async def test_oversized_output_is_offloaded_and_retrievable(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(root=tmp_path / "data"),
        ),
        working_scope=tmp_path,
    )
    sink = EventCollector()

    outcome = await host.run("go", sink)

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.artifact_reference is not None
    full = host.retrieve_artifact(
        outcome.session_id, completed.payload.artifact_reference
    )
    assert full is not None
    assert len(full) >= 200_000


async def test_example_runner_drives_a_deterministic_scenario(tmp_path: Path) -> None:
    outcome_one = await run_scenario("tool", working_scope=tmp_path)
    outcome_two = await run_scenario("tool", working_scope=tmp_path)
    assert outcome_one.termination_reason == "natural-completion"
    assert outcome_one.termination_reason == outcome_two.termination_reason


async def test_example_runner_reports_a_clear_message_on_unknown_scenario(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError) as excinfo:
        await run_scenario("does-not-exist", working_scope=tmp_path)
    assert "unknown scenario" in str(excinfo.value)


def test_example_uses_the_single_assembly_path() -> None:
    # The facade and the example reach the runtime through the same assemble()
    # path — the example embeds via LoopPlaneHost, never a parallel wiring of the
    # Runtime Controller (FR-024).
    import host_quickstart

    source = Path(host_quickstart.__file__).read_text(encoding="utf-8")
    assert "LoopPlaneHost" in source
    assert "RuntimeController" not in source


def test_example_echo_tool_matches_the_test_fixture() -> None:
    # The example intentionally defines its own self-contained echo tool (so it
    # stays copy-pasteable); this guards it against silently drifting from the
    # test fixture's contract (review #8).
    from host_quickstart import _ECHO

    assert _ECHO.name == ECHO_DESCRIPTOR.name
    assert _ECHO.input_schema == ECHO_DESCRIPTOR.input_schema
