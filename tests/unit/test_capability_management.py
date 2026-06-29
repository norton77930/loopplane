"""075 capability-management unit coverage for memory and skills."""

from __future__ import annotations

from pathlib import Path

from loopplane.host import LoopPlaneHost, MemoryConfig, RuntimeConfig, SkillsConfig
from tests.webapi_helpers import text_model


def _host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            memory=MemoryConfig(source=tmp_path / "memory"),
            skills=SkillsConfig(sources=(tmp_path / "skills",)),
        ),
        working_scope=tmp_path,
    )


def test_memory_management_write_get_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    written = host.write_managed_memory(
        name="pref",
        kind="user",
        description="editor preference",
        content="likes tabs",
    )

    assert written.ok is True
    assert written.resource_id == "pref"
    assert [entry.name for entry in host.list_managed_memory()] == ["pref"]
    assert host.get_managed_memory("pref").content == "likes tabs"

    deleted = host.delete_managed_memory("pref", confirm=True)

    assert deleted.ok is True
    assert host.list_managed_memory() == ()


def test_skill_management_write_import_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    written = host.write_managed_skill(
        name="writer",
        description="writes notes",
        instructions="write concise notes",
    )

    assert written.ok is True
    assert [skill.name for skill in host.list_managed_skills()] == ["writer"]
    assert host.get_managed_skill("writer").instructions == "write concise notes"

    imported = host.import_managed_skill(
        {
            "name": "reviewer",
            "description": "reviews notes",
            "instructions": "review concise notes",
        }
    )

    assert imported.ok is True
    assert {skill.name for skill in host.list_managed_skills()} == {
        "reviewer",
        "writer",
    }

    deleted = host.delete_managed_skill("writer", confirm=True)

    assert deleted.ok is True
    assert [skill.name for skill in host.list_managed_skills()] == ["reviewer"]
