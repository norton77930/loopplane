"""US4: a plugin contributes MCP servers and hooks (T011; FR-006, FR-007, SC-005)."""

from __future__ import annotations

from pathlib import Path

from loopplane.hooks import HookRegistry, LifecyclePoint
from loopplane.plugins import load_plugins
from tests.plugins_helpers import write_plugin


def test_mcp_server_is_namespaced_and_hook_is_registered(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        "alpha",
        mcp_servers={
            "docs": {"transport": "http", "url": "https://example.invalid/mcp"}
        },
        hooks=[
            {"point": "after_tool_use", "target": "tests.plugins_helpers:sample_hook"}
        ],
    )
    registry = HookRegistry()
    result = load_plugins([tmp_path], enabled={"alpha"}, hook_registry=registry)

    assert "alpha__docs" in result.mcp_layer
    assert result.hook_count == 1
    assert len(registry.callbacks(LifecyclePoint.after_tool_use)) == 1


def test_two_plugins_with_the_same_server_name_do_not_collide(tmp_path: Path) -> None:
    write_plugin(
        tmp_path, "a", mcp_servers={"s": {"transport": "http", "url": "https://h"}}
    )
    write_plugin(
        tmp_path, "b", mcp_servers={"s": {"transport": "http", "url": "https://h"}}
    )
    result = load_plugins([tmp_path], enabled={"a", "b"})
    assert set(result.mcp_layer) == {"a__s", "b__s"}
