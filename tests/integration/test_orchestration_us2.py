"""US2: coordinate a set of subagents — registration-ordered, deterministic,
each run once (SC-002/006). In-process only.
"""

from __future__ import annotations

import pytest

from loopplane.orchestration import AgentRegistry, Coordinator
from tests.orchestration_helpers import scripted_subagent_definition


def _registry(*names: str) -> AgentRegistry:
    registry = AgentRegistry()
    for name in names:
        registry.register(name, scripted_subagent_definition(name))
    return registry


@pytest.mark.anyio
async def test_results_are_in_registration_order() -> None:
    registry = _registry("a", "b", "c")

    # Selection order differs from registration order; results follow registration.
    results = await Coordinator(registry).run(["c", "a"])

    assert [r.subagent for r in results] == ["a", "c"]
    assert all(r.failure is None for r in results)
    assert all(
        r.outcome is not None and r.outcome.terminal_event == "loop_completed"
        for r in results
    )


@pytest.mark.anyio
async def test_coordination_is_deterministic_and_each_runs_once() -> None:
    coord = Coordinator(_registry("a", "b"))

    first = await coord.run(["a", "b", "a"])  # a duplicate is de-duped
    second = await coord.run(["a", "b"])

    assert [r.subagent for r in first] == ["a", "b"]
    assert [r.subagent for r in first] == [r.subagent for r in second]


@pytest.mark.anyio
async def test_unknown_in_selection_does_not_stop_the_known() -> None:
    results = await Coordinator(_registry("a")).run(["a", "ghost"])

    by_name = {r.subagent: r for r in results}
    assert by_name["a"].failure is None
    assert by_name["a"].outcome is not None
    assert by_name["ghost"].failure == "not found"
    assert len(results) == 2
