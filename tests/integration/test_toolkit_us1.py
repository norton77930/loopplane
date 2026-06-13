"""US1: discover and catalog the tools a set of sources expose (SC-001/002/003)."""

from __future__ import annotations

from loopplane.toolkit import discover
from tests.toolkit_helpers import ScriptedToolAdapter, tool_descriptor


def test_discover_lists_tools_keyed_by_source_and_name() -> None:
    fs = ScriptedToolAdapter(
        [tool_descriptor("write", source="fs"), tool_descriptor("read", source="fs")]
    )
    net = ScriptedToolAdapter([tool_descriptor("fetch", source="net")])
    catalog = discover([fs, net])
    assert [(t.source, t.name) for t in catalog.tools] == [
        ("fs", "read"),
        ("fs", "write"),
        ("net", "fetch"),
    ]
    assert catalog.failed_sources == ()


def test_discover_is_deterministic() -> None:
    adapter = ScriptedToolAdapter(
        [tool_descriptor("b", source="s"), tool_descriptor("a", source="s")]
    )
    assert discover([adapter]) == discover([adapter])


def test_discover_records_a_raising_source() -> None:
    good = ScriptedToolAdapter([tool_descriptor("ok", source="s")])
    bad = ScriptedToolAdapter(raising=True)
    catalog = discover([good, bad])
    assert [t.name for t in catalog.tools] == ["ok"]
    assert catalog.failed_sources == ("source[1]",)


def test_discover_never_invokes_a_tool() -> None:
    # ScriptedToolAdapter.invoke raises AssertionError; discover must not call it.
    adapter = ScriptedToolAdapter([tool_descriptor("t", source="s")])
    catalog = discover([adapter])
    assert [t.name for t in catalog.tools] == ["t"]


def test_discover_empty_sources_is_empty() -> None:
    catalog = discover([])
    assert catalog.tools == ()
    assert catalog.failed_sources == ()
