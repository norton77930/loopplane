"""US1: discover and load an enabled plugin (T008; FR-001, SC-001)."""

from __future__ import annotations

from pathlib import Path

from loopplane.plugins import load_plugins
from tests.plugins_helpers import write_plugin


def test_enabled_plugin_loads_with_its_contributions(tmp_path: Path) -> None:
    directory = write_plugin(tmp_path, "greeter", skills=["skills"])
    (directory / "skills").mkdir()
    result = load_plugins([tmp_path], enabled={"greeter"})
    assert [info.name for info in result.loaded] == ["greeter"]
    assert result.skill_dirs == (directory / "skills",)
    assert result.problems == ()


def test_a_directory_without_a_manifest_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    result = load_plugins([tmp_path], enabled={"plain"})
    assert result.loaded == ()
