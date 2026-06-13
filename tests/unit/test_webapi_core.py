"""Unit tests for the web/API host foundations (011): metadata-only model
projections + the fail-safe default-deny auth boundary.

All auth checks run in-process through Starlette's ``TestClient`` over a tiny
guarded app — no real socket, no external network (NFR-006/NFR-007).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from datetime import UTC, datetime  # noqa: E402

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from loopplane.host import RunOutcome  # noqa: E402
from loopplane.loop.history import HistoryEntry  # noqa: E402
from loopplane.model import TextBlock  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.auth import (  # noqa: E402
    DENY_ALL,
    Authenticator,
    make_auth_dependency,
)
from loopplane.webapi.models import (  # noqa: E402
    ErrorResponse,
    HistoryEntryView,
    RunResult,
)
from tests.webapi_helpers import (  # noqa: E402
    VALID,
    accept_valid,
    allow_all,
    build_test_host,
    deny_all,
    raising,
)

# --- metadata-only projections ----------------------------------------------


def test_history_entry_view_is_metadata_only() -> None:
    view = HistoryEntryView(role="assistant", block_count=3)
    assert view.model_dump() == {"role": "assistant", "block_count": 3}


def test_run_result_projection_drops_block_content() -> None:
    entry = HistoryEntry(
        role="assistant",
        blocks=(TextBlock(text="alpha"), TextBlock(text="beta")),
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    outcome = RunOutcome(
        session_id="s1",
        termination_reason="natural-completion",
        turns_taken=2,
        history=(entry,),
        consumer_failures=(),
    )

    result = RunResult.from_outcome(outcome)

    assert result.session_id == "s1"
    assert result.termination_reason == "natural-completion"
    assert result.turns_taken == 2
    assert result.history == [HistoryEntryView(role="assistant", block_count=2)]
    # The block text must never appear in the serialized response (FR-016).
    dumped = result.model_dump_json()
    assert "alpha" not in dumped
    assert "beta" not in dumped


def test_error_response_is_a_fixed_detail_envelope() -> None:
    assert ErrorResponse(detail="not found").model_dump() == {"detail": "not found"}


# --- auth boundary -----------------------------------------------------------


def _guarded_app(authenticator: Authenticator) -> FastAPI:
    app = FastAPI()
    dep = make_auth_dependency(authenticator)

    @app.get("/probe", dependencies=[Depends(dep)])
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_allow_all_admits() -> None:
    client = TestClient(_guarded_app(allow_all))
    assert client.get("/probe").status_code == 200


def test_default_deny_all_denies() -> None:
    client = TestClient(_guarded_app(DENY_ALL))
    response = client.get("/probe")
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_missing_and_wrong_credential_denied_valid_admitted() -> None:
    client = TestClient(_guarded_app(accept_valid))
    assert client.get("/probe").status_code == 401  # no credential
    assert client.get("/probe", headers={"Authorization": "nope"}).status_code == 401
    assert client.get("/probe", headers={"Authorization": VALID}).status_code == 200


def test_raising_authenticator_is_denied_not_500() -> None:
    client = TestClient(_guarded_app(raising))
    assert client.get("/probe").status_code == 401


def test_denial_never_echoes_the_credential() -> None:
    client = TestClient(_guarded_app(deny_all))
    response = client.get("/probe", headers={"Authorization": "my-credential-xyz"})
    assert response.status_code == 401
    assert "my-credential-xyz" not in response.text


# --- factory smoke -----------------------------------------------------------


def test_create_app_builds(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = create_app(build_test_host(tmp_path))
    assert isinstance(app, FastAPI)
