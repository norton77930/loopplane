"""US4: inspect sessions, history, and artifacts over the API — read-only,
metadata-only (SC-003). In-process only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    multi_text_model,
    tool_then_text_model,
)


def test_list_and_history_are_metadata_only(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=tool_then_text_model(), storage=True)
    client = make_client(create_app(host, authenticator=allow_all))

    session_id = client.post("/v1/runs", json={"prompt": "go"}).json()["session_id"]

    listing = client.get("/v1/sessions")
    assert listing.status_code == 200
    assert session_id in [item["session_id"] for item in listing.json()]
    summary_fields = {
        "session_id",
        "label",
        "last_active_at",
        "created_at",
        "model",
        "starred",
        "forked_from_session_id",
        "forked_from_sequence",
        "context_id",
        "context_name",
        "context_workspace_label",
        "context_status",
        "search_snippet",
    }
    assert all(set(item) == summary_fields for item in listing.json())

    history = client.get(f"/v1/sessions/{session_id}/history")
    assert history.status_code == 200
    assert len(history.json()) >= 2
    assert all(set(entry) == {"role", "block_count"} for entry in history.json())
    # No conversation content leaks into the metadata projection (FR-016).
    assert "hello" not in history.text
    assert "done" not in history.text


def test_history_unknown_session_is_404(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=allow_all))

    assert client.get("/v1/sessions/ghost/history").status_code == 404


def test_resume_existing_and_unknown(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=tool_then_text_model(), storage=True)
    client = make_client(create_app(host, authenticator=allow_all))

    session_id = client.post("/v1/runs", json={"prompt": "go"}).json()["session_id"]

    assert client.post(f"/v1/sessions/{session_id}/resume").status_code == 200
    assert client.post("/v1/sessions/ghost/resume").status_code == 404


def test_artifact_unknown_reference_is_not_found(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=allow_all))

    session_id = client.post("/v1/runs", json={"prompt": "go"}).json()["session_id"]

    response = client.get(f"/v1/sessions/{session_id}/artifacts/ghostref")
    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}
