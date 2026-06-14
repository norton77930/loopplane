"""US1: register and run a subagent -> a child run reference + outcome (SC-001).
In-process only.
"""

from __future__ import annotations

import pytest

from loopplane.orchestration import AgentRegistry, ChildRunReference, Coordinator
from tests.orchestration_helpers import scripted_subagent_definition


@pytest.mark.anyio
async def test_run_one_subagent_returns_reference_and_outcome() -> None:
    registry = AgentRegistry()
    registry.register("a", scripted_subagent_definition("a"))

    results = await Coordinator(registry).run(["a"])

    assert len(results) == 1
    result = results[0]
    assert result.subagent == "a"
    assert result.failure is None
    assert isinstance(result.reference, ChildRunReference)
    assert result.reference.subagent == "a"
    assert result.reference.loop_id
    assert len(result.reference.run_refs) == 1
    assert result.outcome is not None
    assert result.outcome.terminal_event == "loop_completed"


@pytest.mark.anyio
async def test_run_unknown_subagent_is_not_found() -> None:
    results = await Coordinator(AgentRegistry()).run(["ghost"])

    assert len(results) == 1
    result = results[0]
    assert result.subagent == "ghost"
    assert result.failure == "not found"
    assert result.outcome is None
    assert result.reference is None
