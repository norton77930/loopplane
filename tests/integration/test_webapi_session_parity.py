"""074 US2: session-management parity endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from tests.integration.webapi_live_helpers import bearer  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    build_test_host,
    make_client,
    multi_text_model,
)

ALICE = bearer("tok-alice")
BOB = bearer("tok-bob")


def _auth() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


def _run(client, prompt: str = "go") -> str:  # type: ignore[no-untyped-def]
    return client.post("/v1/runs", json={"prompt": prompt}, headers=ALICE).json()[
        "session_id"
    ]


def test_star_search_fork_and_bulk_delete_are_owner_scoped(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a", "b", "c"), tools=(), storage=True
    )

    with make_client(create_app(host, authenticator=_auth())) as client:
        first = _run(client, "alpha prompt")
        second = _run(client, "beta prompt")

        assert (
            client.post(f"/v1/sessions/{first}/star", headers=ALICE).status_code == 200
        )
        assert client.post(f"/v1/sessions/{first}/star", headers=BOB).status_code == 404

        starred = client.get("/v1/sessions", headers=ALICE).json()
        assert next(item for item in starred if item["session_id"] == first)["starred"]

        assert (
            client.delete(f"/v1/sessions/{first}/star", headers=ALICE).status_code
            == 200
        )
        unstarred = client.get("/v1/sessions", headers=ALICE).json()
        assert not next(item for item in unstarred if item["session_id"] == first)[
            "starred"
        ]
        assert (
            client.post(f"/v1/sessions/{first}/star", headers=ALICE).status_code == 200
        )

        searched = client.get("/v1/sessions/search?q=alpha", headers=ALICE).json()
        assert [item["session_id"] for item in searched] == [first]
        assert client.get("/v1/sessions/search?q=alpha", headers=BOB).json() == []

        forked = client.post(
            f"/v1/sessions/{first}/fork",
            json={"sequence": 1, "title": "Forked"},
            headers=ALICE,
        )
        assert forked.status_code == 200
        fork_id = forked.json()["session_id"]
        fork_summary = next(
            item
            for item in client.get("/v1/sessions", headers=ALICE).json()
            if item["session_id"] == fork_id
        )
        assert fork_summary["forked_from_session_id"] == first
        assert fork_summary["forked_from_sequence"] == 1
        assert (
            client.post(
                f"/v1/sessions/{first}/fork",
                json={"sequence": 1, "title": "Not mine"},
                headers=BOB,
            ).status_code
            == 404
        )

        bob_deleted = client.post(
            "/v1/sessions/bulk-delete",
            json={"session_ids": [first], "confirm": True},
            headers=BOB,
        )
        assert bob_deleted.json() == {"deleted": []}
        assert first in [
            item["session_id"]
            for item in client.get("/v1/sessions", headers=ALICE).json()
        ]

        deleted = client.post(
            "/v1/sessions/bulk-delete",
            json={"session_ids": [second], "confirm": True},
            headers=ALICE,
        )
        assert deleted.json() == {"deleted": [second]}
        remaining = client.get("/v1/sessions", headers=ALICE).json()
        assert second not in [item["session_id"] for item in remaining]
