"""US2: enable only the plugins you trust (T009; FR-003, FR-004, SC-002)."""

from __future__ import annotations

from pathlib import Path

from loopplane.plugins import load_plugins
from tests.plugins_helpers import write_plugin


def test_only_enabled_plugins_are_collected(tmp_path: Path) -> None:
    write_plugin(tmp_path, "a")
    write_plugin(tmp_path, "b")
    result = load_plugins([tmp_path], enabled={"a"})
    assert [info.name for info in result.loaded] == ["a"]


def test_empty_enable_list_collects_nothing(tmp_path: Path) -> None:
    write_plugin(tmp_path, "a", skills=["skills"])
    result = load_plugins([tmp_path], enabled=set())
    assert result.loaded == ()
    assert result.skill_dirs == ()
    assert result.mcp_layer == {}
    assert result.hook_count == 0
