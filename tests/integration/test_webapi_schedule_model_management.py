"""075 web/API integration for schedules and model-default management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.app import ModelHost  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    text_model,
)


def test_schedule_management_api(tmp_path: Path) -> None:
    client = make_client(create_app(build_test_host(tmp_path), authenticator=allow_all))

    created = client.post(
        "/v1/capabilities/schedules",
        json={
            "name": "daily-notes",
            "description": "refresh notes",
            "trigger": "manual",
            "enabled": True,
        },
    )

    assert created.status_code == 200
    assert created.json()["schedule"]["status"] == "enabled"
    [schedule] = client.get("/v1/capabilities/schedules").json()
    assert schedule["name"] == "daily-notes"
    assert (
        client.get("/v1/capabilities/schedules/daily-notes").json()["trigger"]
        == "manual"
    )

    run_now = client.post("/v1/capabilities/schedules/daily-notes/run-now")
    assert run_now.status_code == 200
    assert run_now.json()["status"] == "running"

    deleted = client.delete(
        "/v1/capabilities/schedules/daily-notes", params={"confirm": True}
    )
    assert deleted.json()["ok"] is True


def test_model_default_management_api_uses_host_catalog(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=text_model())
    app = create_app(
        host,
        authenticator=allow_all,
        models={"fast": ModelHost(label="Fast model", host=host)},
    )
    client = make_client(app)

    invalid = client.post(
        "/v1/capabilities/model-default", json={"model_id": "missing"}
    )

    assert invalid.status_code == 200
    assert invalid.json()["result"]["ok"] is False
    assert invalid.json()["default"]["status"] == "fallback"

    selected = client.post("/v1/capabilities/model-default", json={"model_id": "fast"})

    assert selected.status_code == 200
    assert selected.json()["default"]["model_id"] == "fast"
    assert selected.json()["default"]["label"] == "Fast model"
    assert client.get("/v1/capabilities/model-default").json()["model_id"] == "fast"
