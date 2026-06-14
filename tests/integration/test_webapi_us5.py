"""US5: every request passes the authentication boundary — default-deny,
fail-safe, no credential echo — on the real routes (SC-004, FR-013-FR-015).
In-process only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    VALID,
    accept_valid,
    build_test_host,
    deny_all,
    make_client,
    multi_text_model,
    raising,
)


def _app(tmp_path: Path, authenticator=None):  # type: ignore[no-untyped-def]
    host = build_test_host(tmp_path, model=multi_text_model("hi"), tools=())
    return create_app(host, authenticator=authenticator)


def test_default_deny_guards_every_route_group(tmp_path: Path) -> None:
    # No authenticator → deny-all; the guard sits in front of run, session, and
    # inspection routes alike.
    client = make_client(_app(tmp_path))

    assert client.post("/v1/runs", json={"prompt": "x"}).status_code == 401
    assert client.post("/v1/sessions").status_code == 401
    assert client.get("/v1/sessions").status_code == 401


def test_missing_and_wrong_credential_denied_valid_admitted(tmp_path: Path) -> None:
    client = make_client(_app(tmp_path, authenticator=accept_valid))

    assert client.post("/v1/runs", json={"prompt": "x"}).status_code == 401
    assert (
        client.post(
            "/v1/runs", json={"prompt": "x"}, headers={"Authorization": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/runs", json={"prompt": "x"}, headers={"Authorization": VALID}
        ).status_code
        == 200
    )


def test_raising_authenticator_is_denied_not_500(tmp_path: Path) -> None:
    client = make_client(_app(tmp_path, authenticator=raising))

    assert client.post("/v1/runs", json={"prompt": "x"}).status_code == 401


def test_denial_never_echoes_the_credential(tmp_path: Path) -> None:
    client = make_client(_app(tmp_path, authenticator=deny_all))

    response = client.post(
        "/v1/runs", json={"prompt": "x"}, headers={"Authorization": "bad-cred-1234"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}
    assert "bad-cred-1234" not in response.text
