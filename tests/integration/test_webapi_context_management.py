"""075 web/API integration for MCP and workspace-context management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.auth import Principal  # noqa: E402
from tests.webapi_helpers import make_client, text_model  # noqa: E402


async def principal_from_header(credential: str | None) -> Principal | None:
    if credential is None:
        return Principal(id="owner")
    scheme, _, subject = credential.partition(" ")
    if scheme.lower() != "bearer" or not subject:
        return None
    return Principal(id=subject)


def _host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
        ),
        working_scope=tmp_path,
    )


def test_mcp_and_context_management_api(tmp_path: Path) -> None:
    client = make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    )

    mcp = client.post(
        "/v1/capabilities/mcp",
        json={
            "name": "docs",
            "transport": "http",
            "url": "https://mcp.example.invalid",
        },
    )

    assert mcp.status_code == 200
    assert mcp.json()["result"]["resource_id"] == "docs"
    [config] = client.get("/v1/capabilities/mcp").json()
    assert config["name"] == "docs"
    assert "url" not in config

    reconnect = client.post("/v1/capabilities/mcp/docs/reconnect")
    assert reconnect.status_code == 200
    assert reconnect.json()["ok"] is True

    context = client.post(
        "/v1/capabilities/contexts",
        json={
            "name": "Docs",
            "description": "documentation workspace",
            "workspace_label": "docs-repo",
        },
    )

    assert context.status_code == 200
    assert context.json()["context"]["workspace_label"] == "docs-repo"
    assert (
        client.get("/v1/capabilities/contexts/Docs").json()["description"]
        == "documentation workspace"
    )

    assert client.delete("/v1/capabilities/mcp/docs", params={"confirm": True}).json()[
        "ok"
    ]


def test_session_context_binding_is_owner_scoped(tmp_path: Path) -> None:
    with make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    ) as client:
        context = client.post(
            "/v1/capabilities/contexts",
            json={
                "name": "Docs",
                "description": "documentation workspace",
                "workspace_label": "docs-repo",
            },
        )
        session_id = client.post("/v1/sessions").json()["session_id"]

        bound = client.post(
            f"/v1/sessions/{session_id}/context",
            json={"context_id": context.json()["context"]["id"]},
        )

        assert bound.status_code == 200
        assert bound.json()["context_id"] == "Docs"
        [summary] = client.get("/v1/sessions").json()
        assert summary["context_id"] == "Docs"
        assert summary["context_name"] == "Docs"

        denied = client.post(
            f"/v1/sessions/{session_id}/context",
            headers={"Authorization": "Bearer other"},
            json={"context_id": "Docs"},
        )
        assert denied.status_code == 404
        assert (
            client.get(
                "/v1/capabilities/contexts",
                headers={"Authorization": "Bearer other"},
            ).json()
            == []
        )
