"""US2: look up and list catalog tools, surfacing collisions (SC-004)."""

from __future__ import annotations

from loopplane.toolkit import discover
from tests.toolkit_helpers import ScriptedToolAdapter, tool_descriptor


def test_lookup_returns_match_or_none() -> None:
    catalog = discover([ScriptedToolAdapter([tool_descriptor("read", source="fs")])])
    found = catalog.lookup("read")
    assert found is not None and found.name == "read"
    assert catalog.lookup("absent") is None


def test_list_by_source() -> None:
    adapter = ScriptedToolAdapter(
        [tool_descriptor("x", source="fs"), tool_descriptor("y", source="net")]
    )
    catalog = discover([adapter])
    assert [t.name for t in catalog.list_by_source("fs")] == ["x"]
    assert [t.name for t in catalog.list_by_source("net")] == ["y"]


def test_list_by_capability() -> None:
    adapter = ScriptedToolAdapter(
        [
            tool_descriptor("ro", source="s", read_only=True),
            tool_descriptor("rw", source="s", read_only=False),
            tool_descriptor("safe", source="s", concurrency_safe=True),
        ]
    )
    catalog = discover([adapter])
    assert [t.name for t in catalog.list_by_capability(read_only=True)] == ["ro"]
    assert [t.name for t in catalog.list_by_capability(concurrency_safe=True)] == [
        "safe"
    ]


def test_collisions_reported_without_overwrite() -> None:
    fs = ScriptedToolAdapter([tool_descriptor("shared", source="fs")])
    net = ScriptedToolAdapter([tool_descriptor("shared", source="net")])
    catalog = discover([fs, net])
    # Both entries are kept (no silent overwrite); the collision is reported.
    assert len([t for t in catalog.tools if t.name == "shared"]) == 2
    assert catalog.collisions() == ("shared",)


def test_no_collision_when_names_unique() -> None:
    adapter = ScriptedToolAdapter(
        [tool_descriptor("a", source="s"), tool_descriptor("b", source="s")]
    )
    assert discover([adapter]).collisions() == ()
