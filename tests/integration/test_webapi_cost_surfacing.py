"""Unit 064: read-only cost-surfacing endpoints over the web/API host.

GET /sessions/{id}/cost returns a session's accumulated USD (owner-only; 404 otherwise;
null when no budget is configured). GET /cost/monthly returns the CALLER's own
current-month USD from the durable ledger (never another principal's; null when no
ledger). Read-only; default-off honest; public-safe. In-process only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import anyio
import pytest

pytest.importorskip("fastapi")

from loopplane.host import LoopPlaneHost, RuntimeConfig  # noqa: E402
from loopplane.ledger import FileUsdLedger  # noqa: E402
from loopplane.model import (  # noqa: E402
    ScriptedModel,
    ScriptedTurn,
    TextIncrement,
    TokenUsage,
)
from loopplane.pricing import PricingRate, PricingTable  # noqa: E402
from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from tests.webapi_helpers import make_client, multi_text_model  # noqa: E402

_MODEL_ID = "test-model"
ALICE = {"Authorization": "Bearer tok-alice"}
BOB = {"Authorization": "Bearer tok-bob"}


def _tokens() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


def _pricing() -> PricingTable:
    return PricingTable(
        rates={
            _MODEL_ID: PricingRate(
                input_rate=Decimal("0.000001"), output_rate=Decimal("0.000002")
            )
        }
    )


def _priced_model() -> ScriptedModel:
    # cost per turn = 1000*0.000001 + 1000*0.000002 = 0.003
    return ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[TextIncrement(text="spending")],
                usage=TokenUsage(input_tokens=1000, output_tokens=1000),
            )
            for _ in range(4)
        ],
        context_capacity=100_000,
    )


def _budget_host(working_scope: Path) -> LoopPlaneHost:
    """A host with per-session budget tracking (a high cap; runs never terminate)."""

    return LoopPlaneHost(
        RuntimeConfig(
            model=_priced_model(),
            tools=(),
            pricing_table=_pricing(),
            model_id=_MODEL_ID,
            per_session_usd=Decimal("1000"),
        ),
        working_scope=working_scope,
    )


def _plain_host(working_scope: Path) -> LoopPlaneHost:
    """A host with NO budget / ledger configured (the default-off case)."""

    return LoopPlaneHost(
        RuntimeConfig(model=multi_text_model("a", "b", "c", "d"), tools=()),
        working_scope=working_scope,
    )


def _ledger_host(working_scope: Path, ledger: FileUsdLedger) -> LoopPlaneHost:
    """A host with a durable ledger configured (for the monthly endpoint)."""

    return LoopPlaneHost(
        RuntimeConfig(
            model=multi_text_model("a", "b"),
            tools=(),
            pricing_table=_pricing(),
            model_id=_MODEL_ID,
            usd_ledger=ledger,
            per_user_monthly_usd=Decimal("1000"),
        ),
        working_scope=working_scope,
    )


def _open_and_submit(client, headers: dict[str, str]) -> str:  # type: ignore[no-untyped-def]
    sid = client.post("/v1/sessions", headers=headers).json()["session_id"]
    client.post(f"/v1/sessions/{sid}/submit", json={"prompt": "go"}, headers=headers)
    return sid


# --- session cost ------------------------------------------------------------


def test_owner_reads_session_accumulated_cost(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        resp = client.get(f"/v1/sessions/{sid}/cost", headers=ALICE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == sid
        assert body["usd_spent"] == "0.003000"  # exact Decimal (rate scale preserved)


def test_session_cost_non_owner_is_404(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        assert client.get(f"/v1/sessions/{sid}/cost", headers=BOB).status_code == 404
        # the owner is unaffected
        assert client.get(f"/v1/sessions/{sid}/cost", headers=ALICE).status_code == 200


def test_session_cost_unknown_session_is_404(tmp_path: Path) -> None:
    app = create_app(_budget_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        assert client.get("/v1/sessions/nope/cost", headers=ALICE).status_code == 404


def test_session_cost_not_tracked_when_no_budget(tmp_path: Path) -> None:
    app = create_app(_plain_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        sid = _open_and_submit(client, ALICE)
        body = client.get(f"/v1/sessions/{sid}/cost", headers=ALICE).json()
        assert body["session_id"] == sid
        assert body["usd_spent"] is None  # "not tracked"


# --- monthly spend -----------------------------------------------------------


def test_monthly_spend_reads_own_principal(tmp_path: Path) -> None:
    ledger = FileUsdLedger(tmp_path / "ledger")
    month = datetime.now(UTC).strftime("%Y-%m")
    anyio.run(ledger.add, "alice", month, Decimal("1.50"))
    app = create_app(_ledger_host(tmp_path, ledger), authenticator=_tokens())
    with make_client(app) as client:
        body = client.get("/v1/cost/monthly", headers=ALICE).json()
        assert body["principal_id"] == "alice"
        assert body["month"] == month
        assert body["usd_spent"] == "1.50"


def test_monthly_spend_is_own_principal_only(tmp_path: Path) -> None:
    ledger = FileUsdLedger(tmp_path / "ledger")
    month = datetime.now(UTC).strftime("%Y-%m")
    anyio.run(ledger.add, "alice", month, Decimal("1.50"))
    app = create_app(_ledger_host(tmp_path, ledger), authenticator=_tokens())
    with make_client(app) as client:
        body = client.get("/v1/cost/monthly", headers=BOB).json()
        # bob reads HIS OWN spend (unseen -> 0), never alice's 1.50
        assert body["principal_id"] == "bob"
        assert body["usd_spent"] == "0"
        assert "1.50" not in str(body)


def test_monthly_spend_not_tracked_when_no_ledger(tmp_path: Path) -> None:
    app = create_app(_plain_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        body = client.get("/v1/cost/monthly", headers=ALICE).json()
        assert body["principal_id"] == "alice"
        assert body["usd_spent"] is None  # "not tracked"


def test_cost_endpoints_are_auth_gated(tmp_path: Path) -> None:
    app = create_app(_plain_host(tmp_path), authenticator=_tokens())
    with make_client(app) as client:
        assert client.get("/v1/cost/monthly").status_code == 401
        assert client.get("/v1/sessions/x/cost").status_code == 401


def test_cost_responses_are_public_safe(tmp_path: Path) -> None:
    # responses carry only the caller's own id + a Decimal string — no other principal,
    # no internal/secret material.
    ledger = FileUsdLedger(tmp_path / "ledger")
    month = datetime.now(UTC).strftime("%Y-%m")
    anyio.run(ledger.add, "alice", month, Decimal("2.25"))
    app = create_app(_ledger_host(tmp_path, ledger), authenticator=_tokens())
    with make_client(app) as client:
        body = client.get("/v1/cost/monthly", headers=ALICE).json()
        assert set(body) == {"principal_id", "month", "usd_spent"}
        assert "bob" not in str(body)
