"""US5: delegate and fail safe — a delegation policy selects subagents; a failing
subagent / raising policy / empty selection is contained (SC-004). In-process only.
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
async def test_failing_subagent_is_captured_others_complete() -> None:
    registry = AgentRegistry()
    registry.register("ok", scripted_subagent_definition("ok"))
    registry.register("bad", scripted_subagent_definition("bad", fail=True))

    results = await Coordinator(registry).run(["ok", "bad"])

    by_name = {r.subagent: r for r in results}
    assert by_name["ok"].failure is None
    assert by_name["ok"].outcome is not None
    # The failing subagent is captured (a fixed marker, no raw detail), and the
    # coordinator still completed with the healthy subagent's result.
    assert by_name["bad"].failure == "failed"
    assert by_name["bad"].outcome is None


@pytest.mark.anyio
async def test_delegate_runs_exactly_the_policy_selection() -> None:
    registry = _registry("a", "b", "c")

    results = await Coordinator(registry).delegate(lambda reg: ["c", "a"])

    # Registration order, regardless of the policy's selection order.
    assert [r.subagent for r in results] == ["a", "c"]


@pytest.mark.anyio
async def test_raising_policy_yields_an_empty_result() -> None:
    def boom(reg: AgentRegistry) -> list[str]:
        raise RuntimeError("policy boom")

    results = await Coordinator(_registry("a")).delegate(boom)

    assert results == ()


@pytest.mark.anyio
async def test_empty_selection_is_an_empty_result() -> None:
    results = await Coordinator(_registry("a")).run([])
    assert results == ()
