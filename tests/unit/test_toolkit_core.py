"""Foundational unit tests for the toolkit layer (008): the discovered-tool value
type and the catalog container. Host-free.
"""

from __future__ import annotations

from loopplane.toolkit import DiscoveredTool, ToolCatalog


def test_discovered_tool_shape() -> None:
    tool = DiscoveredTool(
        source="s",
        name="n",
        description="d",
        read_only=True,
        concurrency_safe=False,
        input_schema={"type": "object"},
    )
    assert (tool.source, tool.name, tool.read_only, tool.concurrency_safe) == (
        "s",
        "n",
        True,
        False,
    )


def test_tool_catalog_list_returns_its_tools() -> None:
    tool = DiscoveredTool("s", "n", "d", False, False, {})
    catalog = ToolCatalog(tools=(tool,), failed_sources=())
    assert catalog.list() == (tool,)


def test_empty_catalog_lists_nothing() -> None:
    assert ToolCatalog(tools=(), failed_sources=()).list() == ()
