"""US3: conduct an interactive session over the API — open, submit, answer, and
cancel (FR-007-FR-010). In-process only.

Coverage note: the session's **live** event stream is an *infinite* SSE response
(it stays open for the session's lifetime), which the buffering in-process
``TestClient`` cannot read incrementally — so the mid-stream out-of-band approval
round-trip is not exercised here. The SSE framing mechanism is proven by the US2
finite-stream tests, and the Session-level approval / cancel round-trip is proven
by the Phase-2 host suite (``test_approval_ask_round_trips_to_host_handler``,
``test_cancel_resolves_a_pending_approval_without_hanging``). This suite covers
the web layer's route mapping: open, submit-to-outcome, out-of-band answer
mapping, cancel, and not-found handling.
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
)


def test_open_and_cancel_session(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    with make_client(create_app(host, authenticator=allow_all)) as client:
        opened = client.post("/v1/sessions")
        assert opened.status_code == 200
        session_id = opened.json()["session_id"]
        assert session_id

        cancelled = client.post(f"/v1/sessions/{session_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json() == {"resolved": True}


def test_unknown_session_is_not_found(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    with make_client(create_app(host, authenticator=allow_all)) as client:
        assert (
            client.post("/v1/sessions/ghost/submit", json={"prompt": "x"}).status_code
            == 404
        )
        assert client.post("/v1/sessions/ghost/cancel").status_code == 404
        assert client.get("/v1/sessions/ghost/events").status_code == 404


def test_submit_to_session_returns_outcome(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("hello"), tools=())
    with make_client(create_app(host, authenticator=allow_all)) as client:
        session_id = client.post("/v1/sessions").json()["session_id"]

        response = client.post(
            f"/v1/sessions/{session_id}/submit", json={"prompt": "go"}
        )

        assert response.status_code == 200
        assert response.json()["termination_reason"] == "natural-completion"
        client.post(f"/v1/sessions/{session_id}/cancel")


def test_answer_unknown_request_is_not_resolved(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    with make_client(create_app(host, authenticator=allow_all)) as client:
        session_id = client.post("/v1/sessions").json()["session_id"]

        approval = client.post(
            f"/v1/sessions/{session_id}/approvals/ghost", json={"allow": True}
        )
        question = client.post(
            f"/v1/sessions/{session_id}/questions/ghost", json={"answers": ["x"]}
        )

        assert approval.json() == {"resolved": False}
        assert question.json() == {"resolved": False}
        client.post(f"/v1/sessions/{session_id}/cancel")
