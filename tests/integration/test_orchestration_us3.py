"""US3: aggregate child events — grouped by subagent, ordered by sequence,
metadata-only (SC-002/003). In-process only.
"""

from __future__ import annotations

import pytest

from loopplane.orchestration import AgentRegistry, Coordinator, aggregate_events
from tests.orchestration_helpers import scripted_subagent_definition


def _registry(*names: str) -> AgentRegistry:
    registry = AgentRegistry()
    for name in names:
        registry.register(name, scripted_subagent_definition(name))
    return registry


@pytest.mark.anyio
async def test_aggregate_events_grouped_and_ordered() -> None:
    results = await Coordinator(_registry("a", "b")).run(["a", "b"])

    events = aggregate_events(results)

    assert len(events) >= 2
    # Each subagent's events form a contiguous group, in registration order.
    a_indices = [i for i, e in enumerate(events) if e.subagent == "a"]
    b_indices = [i for i, e in enumerate(events) if e.subagent == "b"]
    assert a_indices and b_indices
    assert max(a_indices) < min(b_indices)
    # Ordered by sequence within a subagent.
    a_sequences = [e.sequence for e in events if e.subagent == "a"]
    assert a_sequences == sorted(a_sequences)
    # Metadata only — no payload / content field.
    assert all(set(vars(e)) == {"subagent", "type", "sequence"} for e in events)


@pytest.mark.anyio
async def test_aggregate_events_is_deterministic() -> None:
    coord = Coordinator(_registry("a", "b"))

    first = aggregate_events(await coord.run(["a", "b"]))
    second = aggregate_events(await coord.run(["a", "b"]))

    assert first == second


@pytest.mark.anyio
async def test_aggregate_events_of_a_not_found_result_is_empty() -> None:
    results = await Coordinator(_registry()).run(["ghost"])
    assert aggregate_events(results) == ()
