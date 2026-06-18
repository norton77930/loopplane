"""Unit tests for the read-only inspection projections (unit 027).

The projections are pure and metadata-only — they must exclude risky fields (a skill's
``instructions``, an MCP config's args/url) and bound the memory snippet.
"""

from __future__ import annotations

from loopplane.host.inspect import (
    SNIPPET_LIMIT,
    mcp_view,
    memory_view,
    skills_view,
    tools_view,
)
from loopplane.memory.store import MemoryEntry
from loopplane.model.boundary import ToolDescriptor
from loopplane.skills.loader import LoadedSkill
from loopplane.skills.models import ExecutionProfile, Skill


def _loaded(
    name: str, *, autonomous: bool = True, approval: bool = False
) -> LoadedSkill:
    return LoadedSkill(
        skill=Skill(
            name=name,
            description=f"{name} description",
            instructions="SECRET-INSTRUCTIONS",
            profile=ExecutionProfile(
                autonomous_invocation="allowed" if autonomous else "forbidden",
                approval_required=approval,
            ),
        ),
        source="skills/dir",
    )


def test_skills_view_is_metadata_only_and_excludes_instructions() -> None:
    view = skills_view(
        {"b": _loaded("b"), "a": _loaded("a", autonomous=False, approval=True)}
    )
    assert [s.name for s in view] == ["a", "b"]  # sorted by name
    first = view[0]
    assert first.autonomous is False
    assert first.approval_required is True
    assert first.source == "skills/dir"
    # The risky `instructions` field never appears on the projection.
    assert not hasattr(first, "instructions")
    assert "SECRET-INSTRUCTIONS" not in repr(view)


def test_tools_view_projects_safe_fields_sorted() -> None:
    descriptors = [
        ToolDescriptor(
            name="z",
            description="Z",
            input_schema={},
            read_only=True,
            source="internal",
        ),
        ToolDescriptor(name="a", description="A", input_schema={}, source="internal"),
    ]
    view = tools_view(descriptors)
    assert [t.name for t in view] == ["a", "z"]
    assert view[1].read_only is True
    assert view[1].source == "internal"


def test_mcp_view_groups_external_server_sources() -> None:
    descriptors = [
        ToolDescriptor(
            name="github:search",
            description="",
            input_schema={},
            source="external-server:github",
        ),
        ToolDescriptor(
            name="github:issues",
            description="",
            input_schema={},
            source="external-server:github",
        ),
        ToolDescriptor(
            name="local", description="", input_schema={}, source="internal"
        ),
    ]
    view = mcp_view(descriptors)
    assert len(view) == 1
    assert view[0].name == "github"
    assert view[0].tools == ("github:issues", "github:search")


def test_memory_view_bounds_snippet_and_filters_by_query() -> None:
    entries = [
        MemoryEntry(
            type="user", name="alpha", description="about cats", body="x" * 500
        ),
        MemoryEntry(
            type="project", name="beta", description="about dogs", body="short"
        ),
    ]
    listed = memory_view(entries)
    assert {e.name for e in listed} == {"alpha", "beta"}
    big = next(e for e in listed if e.name == "alpha")
    assert big.snippet.endswith("...")
    assert len(big.snippet) <= SNIPPET_LIMIT + 3

    filtered = memory_view(entries, "dogs")
    assert [e.name for e in filtered] == ["beta"]


def test_empty_inputs_yield_empty_tuples() -> None:
    assert skills_view({}) == ()
    assert tools_view([]) == ()
    assert mcp_view([]) == ()
    assert memory_view([]) == ()
