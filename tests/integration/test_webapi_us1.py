"""US1: start a run over the API and receive a metadata-only outcome (SC-001).

All requests run in-process via Starlette's ``TestClient`` — no real socket.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from pathlib import Path  # noqa: E402

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    tool_then_text_model,
)


def test_post_run_returns_metadata_only_outcome(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=tool_then_text_model())
    client = make_client(create_app(host, authenticator=allow_all))

    response = client.post("/v1/runs", json={"prompt": "please run"})

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["termination_reason"] == "natural-completion"
    assert isinstance(body["turns_taken"], int)
    assert len(body["history"]) >= 2
    # Metadata-only: each entry is role + block_count, nothing else.
    assert all(set(entry) == {"role", "block_count"} for entry in body["history"])
    # The run's own content (the echoed tool text, the closing "done") must not
    # leak into the response (FR-016).
    assert "hello" not in response.text
    assert "done" not in response.text


def test_post_run_rejects_empty_prompt(tmp_path: Path) -> None:
    client = make_client(create_app(build_test_host(tmp_path), authenticator=allow_all))

    response = client.post("/v1/runs", json={"prompt": ""})

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid request"}


def test_post_run_without_credential_is_denied(tmp_path: Path) -> None:
    # No authenticator → deny-all default (FR-014).
    client = make_client(create_app(build_test_host(tmp_path)))

    response = client.post("/v1/runs", json={"prompt": "hi"})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_concurrent_run_returns_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The route maps the host's sequential-run RuntimeError to 409; the host's
    # sequential guarantee itself is covered by the Phase-2 host suite.
    async def conflict(*args: object, **kwargs: object) -> object:
        raise RuntimeError("a run is already active")

    host = build_test_host(tmp_path)
    monkeypatch.setattr(host, "run", conflict)
    client = make_client(create_app(host, authenticator=allow_all))

    response = client.post("/v1/runs", json={"prompt": "x"})

    assert response.status_code == 409
    assert response.json() == {"detail": "a run is already active"}
