"""075 capability-management unit coverage for memory and skills."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.host import (
    LoopPlaneHost,
    MemoryConfig,
    RuntimeConfig,
    SkillsConfig,
    StorageConfig,
)
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


async def _discard(*_args: object) -> None:
    return None


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


def test_mcp_management_upsert_reconnect_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    upserted = host.upsert_managed_mcp(
        name="docs", transport="http", url="https://mcp.example.invalid"
    )

    assert upserted.ok is True
    assert upserted.resource_id == "docs"
    [config] = host.list_managed_mcp()
    assert config.name == "docs"
    assert config.status == "disconnected"
    assert config.tool_count == 0

    reconnected = host.reconnect_managed_mcp("docs")

    assert reconnected.ok is True
    assert reconnected.resource_id == "docs"

    deleted = host.delete_managed_mcp("docs", confirm=True)

    assert deleted.ok is True
    assert host.list_managed_mcp() == ()


def test_workspace_context_write_get_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    written = host.upsert_workspace_context(
        name="Docs",
        description="documentation workspace",
        workspace_label="docs-repo",
    )

    assert written.ok is True
    assert written.resource_id == "Docs"
    [context] = host.list_workspace_contexts()
    assert context.name == "Docs"
    assert context.workspace_label == "docs-repo"
    assert host.get_workspace_context("Docs").description == "documentation workspace"

    deleted = host.delete_workspace_context("Docs", confirm=True)

    assert deleted.ok is True
    assert host.list_workspace_contexts() == ()


@pytest.mark.anyio
async def test_session_context_binding_updates_session_metadata(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
        ),
        working_scope=tmp_path,
    )
    host.upsert_workspace_context(
        name="Docs",
        description="documentation workspace",
        workspace_label="docs-repo",
        principal_id="owner",
    )

    async with host.session(_discard, principal_id="owner") as session:
        bound = await host.bind_session_context(
            session.session_id,
            "Docs",
            principal_id="owner",
        )

    assert bound.context_id == "Docs"
    [summary] = host.list_sessions()
    assert summary.context_id == "Docs"
    assert summary.context_name == "Docs"
    assert summary.context_workspace_label == "docs-repo"
