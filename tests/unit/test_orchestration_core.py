"""Unit tests for the multi-agent orchestration foundations (013): the agent
registry + the coordinator result value types.
"""

from __future__ import annotations

import pytest

from loopplane.orchestration import (
    AgentRegistry,
    ChildRunReference,
    DuplicateSubagentError,
    SubagentResult,
)
from tests.orchestration_helpers import scripted_subagent_definition


def test_registry_register_get_names() -> None:
    registry = AgentRegistry()
    subagent_a = registry.register("a", scripted_subagent_definition("a"))
    registry.register("b", scripted_subagent_definition("b"))

    assert registry.names() == ("a", "b")  # registration order
    assert registry.get("a") is subagent_a
    assert registry.get("ghost") is None
    assert "a" in registry
    assert "ghost" not in registry


def test_duplicate_subagent_raises() -> None:
    registry = AgentRegistry()
    registry.register("a", scripted_subagent_definition("a"))

    with pytest.raises(DuplicateSubagentError):
        registry.register("a", scripted_subagent_definition("a"))


def test_result_value_types_are_metadata_only() -> None:
    assert set(ChildRunReference.__dataclass_fields__) == {
        "subagent",
        "loop_id",
        "run_refs",
    }
    assert set(SubagentResult.__dataclass_fields__) == {
        "subagent",
        "reference",
        "outcome",
        "failure",
    }
