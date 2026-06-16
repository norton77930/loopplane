"""Unit 022: per-principal authentication + session ownership scoping over the
web/API host. Two principals are isolated — each sees and drives only its own
sessions; a non-owner gets a 404 (never another principal's data or existence);
durable ownership survives a restart; default-deny and no-leak still hold.

In-process only (Starlette ``TestClient``); no real socket (NFR-006/NFR-007).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    build_test_host,
    make_client,
    multi_text_model,
)

ALICE = {"Authorization": "Bearer tok-alice"}
BOB = {"Authorization": "Bearer tok-bob"}


def _tokens() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


def _client(tmp_path: Path, *, storage: bool = True):  # type: ignore[no-untyped-def]
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b", "c", "d"), tools=(), storage=storage
    )
    return make_client(create_app(host, authenticator=_tokens()))


def test_a_principal_lists_only_their_own_sessions(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sid = client.post("/v1/runs", json={"prompt": "go"}, headers=ALICE).json()[
        "session_id"
    ]

    alice_list = client.get("/v1/sessions", headers=ALICE).json()
    assert sid in [s["session_id"] for s in alice_list]

    bob_list = client.get("/v1/sessions", headers=BOB).json()
    assert sid not in [s["session_id"] for s in bob_list]


def test_cross_principal_access_is_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sid = client.post("/v1/runs", json={"prompt": "go"}, headers=ALICE).json()[
        "session_id"
    ]

    assert client.get(f"/v1/sessions/{sid}/history", headers=BOB).status_code == 404
    assert client.post(f"/v1/sessions/{sid}/resume", headers=BOB).status_code == 404
    assert (
        client.get(f"/v1/sessions/{sid}/artifacts/ref", headers=BOB).status_code == 404
    )
    # The owner is unaffected.
    assert client.get(f"/v1/sessions/{sid}/history", headers=ALICE).status_code == 200


def test_a_principal_cannot_drive_anothers_live_session(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a", "b"), tools=())
    with make_client(create_app(host, authenticator=_tokens())) as client:
        sid = client.post("/v1/sessions", headers=ALICE).json()["session_id"]

        assert (
            client.post(
                f"/v1/sessions/{sid}/submit", json={"prompt": "x"}, headers=BOB
            ).status_code
            == 404
        )
        assert client.post(f"/v1/sessions/{sid}/cancel", headers=BOB).status_code == 404
        # The owner can.
        assert (
            client.post(f"/v1/sessions/{sid}/cancel", headers=ALICE).status_code == 200
        )


def test_default_deny_with_no_authenticator(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    client = make_client(create_app(host))  # no authenticator → deny all

    assert client.post("/v1/runs", json={"prompt": "x"}).status_code == 401
    assert client.get("/v1/sessions", headers=ALICE).status_code == 401


def test_no_credential_or_existence_leaks(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sid = client.post("/v1/runs", json={"prompt": "go"}, headers=ALICE).json()[
        "session_id"
    ]

    # Bob's cross-owner 404 leaks neither the owner nor the session existence.
    denied = client.get(f"/v1/sessions/{sid}/history", headers=BOB)
    assert denied.status_code == 404
    assert denied.json() == {"detail": "not found"}
    assert "alice" not in denied.text

    # A 401 never echoes the bearer token.
    no_auth = make_client(create_app(build_test_host(tmp_path, tools=())))
    refused = no_auth.get("/v1/sessions", headers={"Authorization": "Bearer s3cr3t"})
    assert refused.status_code == 401
    assert "s3cr3t" not in refused.text


def test_durable_ownership_survives_restart(tmp_path: Path) -> None:
    auth = _tokens()
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b"), tools=(), storage=True
    )
    client = make_client(create_app(host, authenticator=auth))
    sid = client.post("/v1/runs", json={"prompt": "go"}, headers=ALICE).json()[
        "session_id"
    ]

    # A fresh host + app over the SAME storage root still scopes per principal.
    host2 = build_test_host(
        tmp_path, model=multi_text_model("c", "d"), tools=(), storage=True
    )
    client2 = make_client(create_app(host2, authenticator=auth))

    assert sid in [
        s["session_id"] for s in client2.get("/v1/sessions", headers=ALICE).json()
    ]
    assert sid not in [
        s["session_id"] for s in client2.get("/v1/sessions", headers=BOB).json()
    ]
    assert client2.post(f"/v1/sessions/{sid}/resume", headers=ALICE).status_code == 200
    assert client2.post(f"/v1/sessions/{sid}/resume", headers=BOB).status_code == 404
