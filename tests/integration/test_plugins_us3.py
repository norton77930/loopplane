"""US3: a plugin contributes skills (T010; FR-005, SC-006)."""

from __future__ import annotations

from pathlib import Path

from loopplane.plugins import load_plugins
from loopplane.skills import load_skills
from tests.plugins_helpers import write_plugin, write_skill


def test_plugin_skills_load_through_the_existing_loader(tmp_path: Path) -> None:
    directory = write_plugin(tmp_path, "greeter", skills=["skills"])
    write_skill(directory, "skills", "greet")
    result = load_plugins([tmp_path], enabled={"greeter"})

    skills, problems = load_skills(list(result.skill_dirs))
    assert "greet" in skills
    assert problems == []


def test_missing_skill_directory_is_skipped_not_fatal(tmp_path: Path) -> None:
    write_plugin(tmp_path, "greeter", skills=["missing"])
    result = load_plugins([tmp_path], enabled={"greeter"})
    assert result.skill_dirs == ()
    assert any("skill directory" in p for p in result.problems)
    assert [info.name for info in result.loaded] == ["greeter"]  # plugin still loads
