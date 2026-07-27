"""075 web/API integration for schedules and model-default management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import (  # noqa: E402
    CapabilityManagementConfig,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
)
from loopplane.host.capabilities import ManagedSchedule  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.app import ModelHost  # noqa: E402
from loopplane.webapi.auth import Principal  # noqa: E402
from tests.webapi_helpers import make_client, text_model  # noqa: E402


class _RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ManagedSchedule]] = []

    def run_now(self, principal_id: str, schedule: ManagedSchedule) -> None:
        self.calls.append((principal_id, schedule))


async def principal_from_header(credential: str | None) -> Principal | None:
    if credential is None:
        return Principal(id="owner")
    scheme, _, subject = credential.partition(" ")
    if scheme.lower() != "bearer" or not subject:
        return None
    return Principal(id=subject)


def _host(tmp_path: Path, runner: _RecordingRunner | None = None) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                schedule_runner=runner,
            ),
        ),
        working_scope=tmp_path,
    )


def test_schedule_management_api(tmp_path: Path) -> None:
    runner = _RecordingRunner()
    client = make_client(
        create_app(_host(tmp_path, runner), authenticator=principal_from_header)
    )

    created = client.post(
        "/v1/capabilities/schedules",
        json={
            "name": "daily-notes",
            "description": "refresh notes",
            "trigger": "manual",
            "instruction": "refresh documentation notes",
            "enabled": True,
        },
    )

    assert created.status_code == 200
    assert created.json()["schedule"]["status"] == "enabled"
    assert created.json()["schedule"]["instruction"] == "refresh documentation notes"
    [schedule] = client.get("/v1/capabilities/schedules").json()
    assert schedule["name"] == "daily-notes"
    assert (
        client.get("/v1/capabilities/schedules/daily-notes").json()["trigger"]
        == "manual"
    )

    disabled = client.post("/v1/capabilities/schedules/daily-notes/disable")
    assert disabled.json()["status"] == "disabled"
    refused = client.post("/v1/capabilities/schedules/daily-notes/run-now")
    assert refused.json()["status"] == "disabled"

    enabled = client.post("/v1/capabilities/schedules/daily-notes/enable")
    assert enabled.json()["status"] == "enabled"
    run_now = client.post("/v1/capabilities/schedules/daily-notes/run-now")
    assert run_now.status_code == 200
    assert run_now.json()["status"] == "running"
    [(principal_id, schedule)] = runner.calls
    assert principal_id == "owner"
    assert schedule.instruction == "refresh documentation notes"

    other = {"Authorization": "Bearer other"}
    assert client.get("/v1/capabilities/schedules", headers=other).json() == []
    non_owner = client.get("/v1/capabilities/schedules/daily-notes", headers=other)
    unknown = client.get("/v1/capabilities/schedules/missing")
    assert non_owner.status_code == unknown.status_code == 404
    assert non_owner.json() == unknown.json()

    restarted = make_client(
        create_app(_host(tmp_path, runner), authenticator=principal_from_header)
    )
    [durable] = restarted.get("/v1/capabilities/schedules").json()
    assert durable["instruction"] == "refresh documentation notes"

    deleted = client.delete(
        "/v1/capabilities/schedules/daily-notes", params={"confirm": True}
    )
    assert deleted.json()["ok"] is True


def test_model_default_management_api_uses_host_catalog_and_precedence(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    app = create_app(
        host,
        authenticator=principal_from_header,
        models={
            "fast": ModelHost(label="Fast model", host=host),
            "slow": ModelHost(label="Slow model", host=host),
        },
    )
    with make_client(app) as client:
        invalid = client.post(
            "/v1/capabilities/model-default", json={"model_id": "missing"}
        )
        assert invalid.status_code == 200
        assert invalid.json()["result"]["ok"] is False
        assert invalid.json()["default"]["status"] == "fallback"

        selected = client.post(
            "/v1/capabilities/model-default", json={"model_id": "fast"}
        )
        assert selected.status_code == 200
        assert selected.json()["default"]["model_id"] == "fast"
        opened = client.post("/v1/sessions").json()["session_id"]
        submitted = client.post(
            f"/v1/sessions/{opened}/submit",
            json={"prompt": "record default model"},
        )
        assert submitted.status_code == 200
    [summary] = host.list_sessions()
    assert summary.session_id == opened
    assert summary.model == "fast"

    restarted_host = _host(tmp_path)
    restarted_app = create_app(
        restarted_host,
        authenticator=principal_from_header,
        models={
            "fast": ModelHost(label="Fast model", host=restarted_host),
            "slow": ModelHost(label="Slow model", host=restarted_host),
        },
    )
    with make_client(restarted_app) as restarted:
        assert (
            restarted.get("/v1/capabilities/model-default").json()["model_id"] == "fast"
        )
        explicit = restarted.post("/v1/sessions", params={"model": "slow"}).json()[
            "session_id"
        ]
        submitted = restarted.post(
            f"/v1/sessions/{explicit}/submit",
            json={"prompt": "record explicit model"},
        )
        assert submitted.status_code == 200

        other = {"Authorization": "Bearer other"}
        assert (
            restarted.get("/v1/capabilities/model-default", headers=other).json()[
                "status"
            ]
            == "fallback"
        )
        cleared = restarted.delete("/v1/capabilities/model-default")
        assert cleared.json()["result"]["ok"] is True
        assert cleared.json()["default"]["status"] == "fallback"
    summaries = restarted_host.list_sessions()
    assert (
        next(item for item in summaries if item.session_id == explicit).model == "slow"
    )


def test_capability_requests_reject_credential_like_extra_fields(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path, _RecordingRunner())
    client = make_client(
        create_app(
            host,
            authenticator=principal_from_header,
            models={"fast": ModelHost(label="Fast model", host=host)},
        )
    )

    schedule = client.post(
        "/v1/capabilities/schedules",
        json={
            "name": "daily-notes",
            "trigger": "manual",
            "instruction": "refresh notes",
            "enabled": True,
            "api_key": "not-a-credential",
        },
    )
    model = client.post(
        "/v1/capabilities/model-default",
        json={"model_id": "fast", "auth_token": "not-a-credential"},
    )

    assert schedule.status_code == model.status_code == 422
    assert schedule.json() == model.json() == {"detail": "invalid request"}
