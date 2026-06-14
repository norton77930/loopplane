"""US4: aggregate child artifacts — grouped by subagent, metadata-only (SC-003).
In-process only.

Scripted text loops produce no artifacts, so the populated case is exercised over
constructed ``SubagentResult``s (a public outcome with ``state.artifacts`` set);
``aggregate_artifacts`` is a pure projection over the captured outcome.
"""

from __future__ import annotations

import pytest

from loopplane.engineering import ArtifactRef, LoopOutcome, LoopState
from loopplane.orchestration import (
    AgentRegistry,
    Coordinator,
    SubagentResult,
    aggregate_artifacts,
)
from tests.orchestration_helpers import scripted_subagent_definition


def _result_with_artifacts(name: str, *pairs: tuple[str, str]) -> SubagentResult:
    state = LoopState(
        loop_id=name,
        loop_definition_id=name,
        artifacts=tuple(ArtifactRef(session_id=s, reference=r) for s, r in pairs),
    )
    outcome = LoopOutcome(
        loop_id=name,
        loop_definition_id=name,
        terminal_event=None,
        stop_reason=None,
        state=state,
        events=(),
    )
    return SubagentResult(subagent=name, reference=None, outcome=outcome, failure=None)


def test_aggregate_artifacts_groups_by_subagent() -> None:
    results = (
        _result_with_artifacts("a", ("s1", "ref1"), ("s1", "ref2")),
        _result_with_artifacts("b", ("s2", "ref3")),
    )

    artifacts = aggregate_artifacts(results)

    assert [(x.subagent, x.session_id, x.reference) for x in artifacts] == [
        ("a", "s1", "ref1"),
        ("a", "s1", "ref2"),
        ("b", "s2", "ref3"),
    ]
    assert all(
        set(vars(x)) == {"subagent", "session_id", "reference"} for x in artifacts
    )


def test_aggregate_artifacts_no_artifacts_contributes_nothing() -> None:
    assert aggregate_artifacts((_result_with_artifacts("a"),)) == ()


@pytest.mark.anyio
async def test_aggregate_artifacts_of_a_real_run_is_empty() -> None:
    registry = AgentRegistry()
    registry.register("a", scripted_subagent_definition("a"))

    results = await Coordinator(registry).run(["a"])

    # A scripted text loop produces no artifacts.
    assert aggregate_artifacts(results) == ()
