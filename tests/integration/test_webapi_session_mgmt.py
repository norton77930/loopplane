"""Unit 030: session management over the web/API host — rename + delete.

Owner-scoped (a non-owner gets a 404, never another principal's data or its
existence); a rename persists across a restart; a blank title is rejected; an
unknown session is a 404; and rename/delete also work for an in-memory session
with no checkpoint store. In-process only (Starlette ``TestClient``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    multi_text_model,
)

ALICE = {"Authorization": "Bearer tok-alice"}
BOB = {"Authorization": "Bearer tok-bob"}


def _tokens() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


def _run(client, headers=ALICE) -> str:  # type: ignore[no-untyped-def]
    return client.post("/v1/runs", json={"prompt": "go"}, headers=headers).json()[
        "session_id"
    ]


def _label(client, sid, headers=ALICE):  # type: ignore[no-untyped-def]
    listing = client.get("/v1/sessions", headers=headers).json()
    return next((s["label"] for s in listing if s["session_id"] == sid), None)


def test_rename_shows_in_listing_and_survives_restart(tmp_path: Path) -> None:
    auth = _tokens()
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=auth))
    sid = _run(client)

    assert (
        client.patch(
            f"/v1/sessions/{sid}", json={"title": "My Chat"}, headers=ALICE
        ).status_code
        == 200
    )
    assert _label(client, sid) == "My Chat"

    # A fresh host over the SAME storage still shows the renamed title.
    host2 = build_test_host(
        tmp_path, model=multi_text_model("c", "d"), tools=(), storage=True
    )
    client2 = make_client(create_app(host2, authenticator=auth))
    assert _label(client2, sid) == "My Chat"


def test_rename_rejects_blank_title(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=allow_all))
    sid = _run(client, headers={})

    assert client.patch(f"/v1/sessions/{sid}", json={"title": "   "}).status_code == 422
    assert client.patch(f"/v1/sessions/{sid}", json={"title": ""}).status_code == 422


def test_delete_removes_and_survives_restart(tmp_path: Path) -> None:
    auth = _tokens()
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=auth))
    sid = _run(client)
    assert sid in [
        s["session_id"] for s in client.get("/v1/sessions", headers=ALICE).json()
    ]

    assert client.delete(f"/v1/sessions/{sid}", headers=ALICE).status_code == 200
    assert sid not in [
        s["session_id"] for s in client.get("/v1/sessions", headers=ALICE).json()
    ]

    host2 = build_test_host(
        tmp_path, model=multi_text_model("c", "d"), tools=(), storage=True
    )
    client2 = make_client(create_app(host2, authenticator=auth))
    assert sid not in [
        s["session_id"] for s in client2.get("/v1/sessions", headers=ALICE).json()
    ]


def test_non_owner_rename_and_delete_are_404(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=_tokens()))
    sid = _run(client, ALICE)

    denied = client.patch(f"/v1/sessions/{sid}", json={"title": "x"}, headers=BOB)
    assert denied.status_code == 404
    assert denied.json() == {"detail": "not found"}
    assert "alice" not in denied.text
    assert client.delete(f"/v1/sessions/{sid}", headers=BOB).status_code == 404

    # The owner is unaffected.
    assert _label(client, sid) is None or sid in [
        s["session_id"] for s in client.get("/v1/sessions", headers=ALICE).json()
    ]
    assert (
        client.patch(
            f"/v1/sessions/{sid}", json={"title": "ok"}, headers=ALICE
        ).status_code
        == 200
    )


def test_unknown_session_rename_and_delete_are_404(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=allow_all))

    assert client.patch("/v1/sessions/ghost", json={"title": "x"}).status_code == 404
    assert client.delete("/v1/sessions/ghost").status_code == 404


def test_in_memory_rename_and_delete_without_storage(tmp_path: Path) -> None:
    # No checkpoint store: a live (in-memory) session still renames and deletes.
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b"), tools=(), storage=False
    )
    client = make_client(create_app(host, authenticator=allow_all))
    sid = _run(client, headers={})

    assert client.patch(f"/v1/sessions/{sid}", json={"title": "Mem"}).status_code == 200
    assert _label(client, sid, headers={}) == "Mem"
    assert client.delete(f"/v1/sessions/{sid}").status_code == 200
    assert sid not in [s["session_id"] for s in client.get("/v1/sessions").json()]
