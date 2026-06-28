"""074 US1: additive live-channel session transport."""

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


def test_live_ticket_is_issued_only_for_owned_session(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())

    with make_client(create_app(host, authenticator=_auth())) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]

        allowed = client.post(f"/v1/sessions/{session_id}/live-ticket", headers=ALICE)
        denied = client.post(f"/v1/sessions/{session_id}/live-ticket", headers=BOB)

    assert allowed.status_code == 200
    assert allowed.json()["session_id"] == session_id
    assert allowed.json()["ticket"]
    assert denied.status_code == 404


def test_live_channel_submits_and_replays_session_events(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("hello"), tools=())

    with make_client(
        create_app(host, authenticator=_auth(), sse_replay_buffer=20)
    ) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]
        ticket = client.post(
            f"/v1/sessions/{session_id}/live-ticket", headers=ALICE
        ).json()["ticket"]

        with client.websocket_connect(
            f"/v1/sessions/{session_id}/live?ticket={ticket}"
        ) as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json(
                {
                    "type": "submit",
                    "client_message_id": "c1",
                    "payload": {"prompt": "go"},
                }
            )
            received: list[str] = []
            for _ in range(5):
                message = ws.receive_json()
                if message["type"] == "event":
                    received.append(message["payload"]["type"])
                if "run-terminated" in received:
                    break

    assert "assistant-output-increment" in received
    assert "run-terminated" in received


def test_live_channel_abort_and_unknown_answers_are_public_safe(
    tmp_path: Path,
) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())

    with make_client(create_app(host, authenticator=_auth())) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]
        ticket = client.post(
            f"/v1/sessions/{session_id}/live-ticket", headers=ALICE
        ).json()["ticket"]

        with client.websocket_connect(
            f"/v1/sessions/{session_id}/live?ticket={ticket}"
        ) as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"type": "approval_decision", "payload": {"request_id": "x"}})
            assert ws.receive_json() == {
                "type": "notice",
                "payload": {"resolved": False},
            }
            ws.send_json({"type": "question_answer", "payload": {"request_id": "x"}})
            assert ws.receive_json() == {
                "type": "notice",
                "payload": {"resolved": False},
            }
            ws.send_json({"type": "abort", "payload": {}})
            assert ws.receive_json() == {
                "type": "notice",
                "payload": {"aborted": True},
            }
