"""Unit 065: the web/API POST /commands endpoint (backend slash commands).

Commands dispatch against EXISTING host seams; session-scoped commands (/cost,
/compact) are owner-scoped (404 for a non-owner) and require a session_id; results
are public-safe (the caller's own data only). In-process only.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import LoopPlaneHost, RuntimeConfig  # noqa: E402
from loopplane.model import (  # noqa: E402
    ScriptedModel,
    ScriptedTurn,
    TextIncrement,
    TokenUsage,
)
from loopplane.pricing import PricingRate, PricingTable  # noqa: E402
from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from tests.webapi_helpers import make_client  # noqa: E402

_MODEL_ID = "test-model"
ALICE = {"Authorization": "Bearer tok-alice"}
BOB = {"Authorization": "Bearer tok-bob"}


def _tokens() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


def _budget_host(working_scope: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[TextIncrement(text="spending")],
                usage=TokenUsage(input_tokens=1000, output_tokens=1000),
            )
            for _ in range(4)
        ],
        context_capacity=100_000,
    )
    return LoopPlaneHost(
        RuntimeConfig(
            model=model,
            tools=(),
            pricing_table=PricingTable(
                rates={
                    _MODEL_ID: PricingRate(
                        input_rate=Decimal("0.000001"),
                        output_rate=Decimal("0.000002"),
                    )
                }
            ),
            model_id=_MODEL_ID,
            per_session_usd=Decimal("1000"),
        ),
        working_scope=working_scope,
    )


def _open_and_submit(client, headers):  # type: ignore[no-untyped-def]
    sid = client.post("/v1/sessions", headers=headers).json()["session_id"]
    client.post(f"/v1/sessions/{sid}/submit", json={"prompt": "go"}, headers=headers)
    return sid


def test_cost_command_owner(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.post(
            "/v1/commands", json={"command": "/cost", "session_id": sid}, headers=ALICE
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "ok"
        assert "session: 0.003000" in body["text"]
        assert set(body) == {"kind", "text"}


def test_cost_command_non_owner_is_404(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.post(
            "/v1/commands", json={"command": "/cost", "session_id": sid}, headers=BOB
        )
        assert resp.status_code == 404
        assert "0.003000" not in str(resp.json())


def test_cost_command_requires_session(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        resp = client.post("/v1/commands", json={"command": "/cost"}, headers=ALICE)
        assert resp.status_code == 400


def test_compact_command_owner(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.post(
            "/v1/commands",
            json={"command": "/compact", "session_id": sid},
            headers=ALICE,
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "ok"


def test_memory_command(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        resp = client.post("/v1/commands", json={"command": "/memory"}, headers=ALICE)
        assert resp.status_code == 200
        assert resp.json()["kind"] == "ok"


def test_unknown_command(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        resp = client.post("/v1/commands", json={"command": "/bogus"}, headers=ALICE)
        assert resp.status_code == 200
        assert resp.json()["kind"] == "unknown"


def test_commands_are_auth_gated(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        assert (
            client.post("/v1/commands", json={"command": "/memory"}).status_code == 401
        )


# --- 079: the new session-scoped commands must be gated the same way ---------


def test_history_command_non_owner_is_404(tmp_path: Path) -> None:
    """The disclosure this unit shipped once: /history is session-scoped, so a
    non-owner must get the same 404 /cost gets — and learn nothing."""

    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.post(
            "/v1/commands",
            json={"command": "/history", "session_id": sid},
            headers=BOB,
        )
        assert resp.status_code == 404
        body = str(resp.json())
        assert "block(s)" not in body
        assert sid not in body


def test_permission_command_non_owner_is_404(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.post(
            "/v1/commands",
            json={"command": "/permission", "session_id": sid},
            headers=BOB,
        )
        assert resp.status_code == 404
        body = str(resp.json())
        assert "mode:" not in body
        assert sid not in body


def test_a_non_owned_session_is_indistinguishable_from_a_missing_one(
    tmp_path: Path,
) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        owned_by_other = client.post(
            "/v1/commands",
            json={"command": "/history", "session_id": sid},
            headers=BOB,
        )
        never_existed = client.post(
            "/v1/commands",
            json={"command": "/history", "session_id": "no-such-session"},
            headers=BOB,
        )
        assert owned_by_other.status_code == never_existed.status_code == 404
        assert owned_by_other.json() == never_existed.json()


def test_history_and_permission_require_a_session(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        for command in ("/history", "/permission"):
            resp = client.post("/v1/commands", json={"command": command}, headers=ALICE)
            assert resp.status_code == 400, command


def test_history_command_owner_succeeds(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.post(
            "/v1/commands",
            json={"command": "/history", "session_id": sid},
            headers=ALICE,
        )
        assert resp.status_code == 200
        assert "block(s)" in resp.json()["text"]


def test_the_gate_covers_every_session_scoped_command(tmp_path: Path) -> None:
    """The gate is driven by the registry, so it cannot fall out of step with
    the command set. This asserts that coupling directly."""

    from loopplane.commands import default_registry

    scoped = default_registry().session_scoped_names()
    assert scoped == {"cost", "compact", "history", "permission"}

    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        for name in sorted(scoped):
            resp = client.post(
                "/v1/commands",
                json={"command": f"/{name}", "session_id": sid},
                headers=BOB,
            )
            assert resp.status_code == 404, name
