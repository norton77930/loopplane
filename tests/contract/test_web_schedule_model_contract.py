"""075 foundation contracts for schedule and model-default management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import allow_all, build_test_host, make_client  # noqa: E402


def test_schedule_list_and_model_default_exist(tmp_path: Path) -> None:
    host = build_test_host(tmp_path)
    client = make_client(create_app(host, authenticator=allow_all))

    schedules = client.get("/v1/capabilities/schedules")
    model_default = client.get("/v1/capabilities/model-default")

    assert schedules.status_code == 200
    assert model_default.status_code == 200
    assert schedules.json() == []
    assert model_default.json()["status"] == "fallback"
