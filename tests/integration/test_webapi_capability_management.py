"""075 web/API integration for memory and skill capability management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import (  # noqa: E402
    CapabilityManagementConfig,
    LoopPlaneHost,
    MemoryConfig,
    RuntimeConfig,
    SkillsConfig,
    StorageConfig,
)
from loopplane.memory import MemoryEntry, MemoryStore  # noqa: E402
from loopplane.skills import Skill  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.auth import Principal  # noqa: E402
from tests.webapi_helpers import allow_all, make_client, text_model  # noqa: E402


def _host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            memory=MemoryConfig(source=tmp_path / "memory"),
            skills=SkillsConfig(sources=(tmp_path / "skills",)),
            capability_management=CapabilityManagementConfig(mutations_enabled=True),
        ),
        working_scope=tmp_path,
    )


async def _principal_from_header(credential: str | None) -> Principal | None:
    if credential is None:
        return Principal(id="owner")
    scheme, _, subject = credential.partition(" ")
    if scheme.lower() != "bearer" or not subject:
        return None
    return Principal(id=subject)


def test_memory_management_api_create_get_delete(tmp_path: Path) -> None:
    client = make_client(create_app(_host(tmp_path), authenticator=allow_all))

    created = client.post(
        "/v1/capabilities/memory",
        json={
            "name": "pref",
            "kind": "user",
            "description": "editor preference",
            "content": "likes tabs",
        },
    )

    assert created.status_code == 200
    assert created.json()["result"]["ok"] is True
    assert client.get("/v1/capabilities/memory/pref").json()["content"] == "likes tabs"

    deleted = client.delete("/v1/capabilities/memory/pref", params={"confirm": True})

    assert deleted.status_code == 200
    assert client.get("/v1/capabilities/memory").json() == []


def test_skill_management_api_write_import_delete(tmp_path: Path) -> None:
    client = make_client(create_app(_host(tmp_path), authenticator=allow_all))

    written = client.post(
        "/v1/capabilities/skills",
        json={
            "name": "writer",
            "description": "writes notes",
            "instructions": "write concise notes",
        },
    )

    assert written.status_code == 200
    assert written.json()["result"]["resource_id"] == "writer"
    assert (
        client.get("/v1/capabilities/skills/writer").json()["instructions"]
        == "write concise notes"
    )

    imported = client.post(
        "/v1/capabilities/skills/import",
        json={
            "definition": {
                "name": "reviewer",
                "description": "reviews notes",
                "instructions": "review concise notes",
            }
        },
    )

    assert imported.status_code == 200
    names = {item["name"] for item in client.get("/v1/capabilities/skills").json()}
    assert names == {"reviewer", "writer"}

    deleted = client.delete("/v1/capabilities/skills/writer", params={"confirm": True})

    assert deleted.status_code == 200
    assert [item["name"] for item in client.get("/v1/capabilities/skills").json()] == [
        "reviewer"
    ]


def test_memory_and_skill_api_are_owner_scoped_with_shared_read_only_items(
    tmp_path: Path,
) -> None:
    MemoryStore(tmp_path / "memory").write(
        MemoryEntry(
            type="project",
            name="host-memory",
            description="shared memory",
            body="界" * 170 + "private suffix",
        )
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "host-skill.json").write_text(
        Skill(
            name="host-skill",
            description="shared skill",
            instructions="shared host instructions",
        ).model_dump_json(),
        encoding="utf-8",
    )
    client = make_client(
        create_app(_host(tmp_path), authenticator=_principal_from_header)
    )

    memory_created = client.post(
        "/v1/capabilities/memory",
        json={
            "name": "owner-memory",
            "kind": "user",
            "description": "private memory",
            "content": "owner memory content",
        },
    )
    skill_created = client.post(
        "/v1/capabilities/skills",
        json={
            "name": "owner-skill",
            "description": "private skill",
            "instructions": "owner skill instructions",
        },
    )
    assert memory_created.json()["result"]["ok"] is True
    assert skill_created.json()["result"]["ok"] is True

    owner_memory = {
        item["id"]: item for item in client.get("/v1/capabilities/memory").json()
    }
    owner_skills = {
        item["id"]: item for item in client.get("/v1/capabilities/skills").json()
    }
    assert set(owner_memory) == {"host-memory", "owner-memory"}
    assert set(owner_skills) == {"host-skill", "owner-skill"}
    assert owner_memory["host-memory"]["scope"] == "shared_read_only"
    assert owner_memory["host-memory"]["actions"] == ["open"]
    assert owner_memory["host-memory"]["snippet"] == "界" * 160
    assert owner_skills["host-skill"]["scope"] == "shared_read_only"
    assert owner_skills["host-skill"]["actions"] == ["open"]

    shared_memory = client.get("/v1/capabilities/memory/host-memory").json()
    assert shared_memory["snippet"] == "界" * 160
    assert shared_memory["content"] == ""
    assert "private suffix" not in str(shared_memory)
    shared_skill = client.get("/v1/capabilities/skills/host-skill").json()
    assert shared_skill["instructions"] == ""
    assert "shared host instructions" not in str(shared_skill)

    other = {"Authorization": "Bearer other"}
    assert {
        item["id"]
        for item in client.get("/v1/capabilities/memory", headers=other).json()
    } == {"host-memory"}
    assert {
        item["id"]
        for item in client.get("/v1/capabilities/skills", headers=other).json()
    } == {"host-skill"}

    for path in ("memory/owner-memory", "skills/owner-skill"):
        non_owner = client.get(f"/v1/capabilities/{path}", headers=other)
        unknown = client.get(f"/v1/capabilities/{path.rsplit('/', 1)[0]}/missing")
        assert non_owner.status_code == unknown.status_code == 404
        assert non_owner.json() == unknown.json()
