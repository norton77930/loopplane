"""075 foundation contracts for memory and skill capability management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import (  # noqa: E402
    CapabilityManagementConfig,
    LoopPlaneHost,
    MemoryConfig,
    RuntimeConfig,
    StorageConfig,
)
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.auth import Principal  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    text_model,
)


async def principal_from_header(credential: str | None) -> Principal | None:
    if credential is None:
        return Principal(id="owner")
    scheme, _, subject = credential.partition(" ")
    if scheme.lower() != "bearer" or not subject:
        return None
    return Principal(id=subject)


def _managed_host(tmp_path: Path, *, mutations_enabled: bool) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            memory=MemoryConfig(source=tmp_path / "memory"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=mutations_enabled
            ),
        ),
        working_scope=tmp_path,
    )


def test_memory_and_skill_management_lists_are_metadata_only(
    tmp_path: Path,
) -> None:
    host = build_test_host(tmp_path)
    client = make_client(create_app(host, authenticator=allow_all))

    memory = client.get("/v1/capabilities/memory")
    skills = client.get("/v1/capabilities/skills")

    assert memory.status_code == 200
    assert skills.status_code == 200
    assert memory.json() == []
    assert skills.json() == []


def test_capability_mutation_validation_uses_public_safe_error(
    tmp_path: Path,
) -> None:
    host = build_test_host(tmp_path)
    client = make_client(create_app(host, authenticator=allow_all))

    response = client.post(
        "/v1/capabilities/memory",
        json={"name": " ", "kind": "note", "content": "x"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid request"}


@pytest.mark.parametrize(
    ("transport", "url", "command"),
    [
        ("http", "https://user@example.invalid/mcp", None),
        ("http", "https://example.invalid/mcp?mode=sample", None),
        ("http", "https://example.invalid/mcp#section", None),
        ("websocket", "https://example.invalid/mcp", None),
        ("stdio", None, "synthetic-command"),
    ],
)
def test_unsafe_mcp_write_uses_unchanged_public_safe_domain_envelope(
    tmp_path: Path,
    transport: str,
    url: str | None,
    command: str | None,
) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                mcp_endpoint_policy=lambda *_args: True,
            ),
        ),
        working_scope=tmp_path,
    )
    client = make_client(create_app(host, authenticator=allow_all))
    payload: dict[str, object] = {
        "name": "docs",
        "transport": transport,
    }
    if url is not None:
        payload["url"] = url
    if command is not None:
        payload["command"] = command

    response = client.post("/v1/capabilities/mcp", json=payload)

    assert response.status_code == 200
    assert response.json()["result"] == {
        "ok": False,
        "resource_id": None,
        "status": "invalid",
        "message": "mcp configuration is invalid",
    }
    assert (url or command or "") not in response.text
    assert client.get("/v1/capabilities/mcp").json() == []


def test_capability_settings_status_is_public_safe_and_default_off(
    tmp_path: Path,
) -> None:
    client = make_client(create_app(build_test_host(tmp_path), authenticator=allow_all))

    response = client.get("/v1/capabilities/settings")

    assert response.status_code == 200
    assert response.json() == {
        "storage_available": False,
        "mutations_enabled": False,
        "runtime_activation_enabled": False,
        "mcp_endpoint_policy_available": False,
        "schedule_runner_available": False,
    }


def test_capability_mutation_gate_returns_domain_refusal(
    tmp_path: Path,
) -> None:
    client = make_client(
        create_app(
            _managed_host(tmp_path, mutations_enabled=False),
            authenticator=principal_from_header,
        )
    )

    response = client.post(
        "/v1/capabilities/memory",
        json={
            "name": "pref",
            "kind": "user",
            "description": "editor preference",
            "content": "likes tabs",
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == {
        "ok": False,
        "resource_id": None,
        "status": "disabled_by_policy",
        "message": "capability mutations are disabled",
    }
    assert client.get("/v1/capabilities/memory").json() == []


def test_owned_capability_actions_and_non_disclosure(
    tmp_path: Path,
) -> None:
    client = make_client(
        create_app(
            _managed_host(tmp_path, mutations_enabled=True),
            authenticator=principal_from_header,
        )
    )
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
    [owned] = client.get("/v1/capabilities/memory").json()
    assert owned["scope"] == "owned"
    assert set(owned["actions"]) == {"open", "update", "delete"}
    assert owned["problem"] is None
    assert "updated_at" in owned

    other_headers = {"Authorization": "Bearer other"}
    assert client.get("/v1/capabilities/memory", headers=other_headers).json() == []
    non_owner = client.get("/v1/capabilities/memory/pref", headers=other_headers)
    unknown = client.get("/v1/capabilities/memory/missing")
    assert non_owner.status_code == unknown.status_code == 404
    assert non_owner.json() == unknown.json()
