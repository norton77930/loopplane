"""075 web/API integration for memory and skill capability management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import (  # noqa: E402
    LoopPlaneHost,
    MemoryConfig,
    RuntimeConfig,
    SkillsConfig,
)
from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import allow_all, make_client, text_model  # noqa: E402


def _host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            memory=MemoryConfig(source=tmp_path / "memory"),
            skills=SkillsConfig(sources=(tmp_path / "skills",)),
        ),
        working_scope=tmp_path,
    )


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
