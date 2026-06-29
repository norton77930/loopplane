"""075 foundation contracts for memory and skill capability management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import allow_all, build_test_host, make_client  # noqa: E402


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
