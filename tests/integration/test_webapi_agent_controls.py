"""US1 owner-scoped WebAPI agent-control integration tests (spec 077 T006/T013)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import LoopPlaneHost, RuntimeConfig  # noqa: E402
from loopplane.host.upload_tool import make_read_upload_tool  # noqa: E402
from loopplane.model import (  # noqa: E402
    ScriptedModel,
    ScriptedTurn,
    TextIncrement,
    ToolCallRequest,
)
from loopplane.pricing import PricingRate, PricingTable  # noqa: E402
from loopplane.tools import InternalToolAdapter  # noqa: E402
from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from loopplane.webapi.app import ModelHost  # noqa: E402
from loopplane.webapi.uploads import UploadStore  # noqa: E402
from tests.integration.webapi_live_helpers import bearer  # noqa: E402
from tests.webapi_helpers import make_client  # noqa: E402

ALICE = bearer("tok-alice")
BOB = bearer("tok-bob")


def _auth() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


def _host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[
                    ScriptedTurn(increments=[TextIncrement(text="session")]),
                    ScriptedTurn(increments=[TextIncrement(text="run")]),
                ],
                context_capacity=1_000,
            ),
            browser_permission_modes=("plan",),
        ),
        working_scope=tmp_path,
    )


def _plan_exit_host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[
                    ScriptedTurn(
                        increments=[
                            ToolCallRequest(
                                call_id="exit-1",
                                tool_name="exit_plan_mode",
                                input={"plan": "approved plan"},
                            )
                        ]
                    ),
                    ScriptedTurn(increments=[TextIncrement(text="done")]),
                ],
                context_capacity=1_000,
            ),
            tool_adapters=(InternalToolAdapter(),),
            browser_permission_modes=("plan",),
        ),
        working_scope=tmp_path,
    )


def test_agent_controls_are_owner_scoped_and_project_only_safe_mode_metadata(
    tmp_path: Path,
) -> None:
    with make_client(create_app(_host(tmp_path), authenticator=_auth())) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]

        owner = client.get(f"/v1/sessions/{session_id}/agent-controls", headers=ALICE)
        other = client.get(f"/v1/sessions/{session_id}/agent-controls", headers=BOB)

    assert owner.status_code == 200
    body = owner.json()
    assert body["permission"]["selection_scope"] == "run"
    assert body["permission"]["selectable_modes"] == [
        {"id": "plan", "kind": "plan", "summary": "permission.mode.plan"}
    ]
    assert body["actions"] == ["select_permission_mode"]
    assert "permission_rules" not in body
    assert "principal_id" not in body
    assert other.status_code == 404


def test_budget_projection_is_authoritative_owner_scoped_and_enum_only(
    tmp_path: Path,
) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="done")])],
                context_capacity=1_000,
            ),
            pricing_table=PricingTable(
                rates={
                    "model-a": PricingRate(
                        input_rate=Decimal("0.001"),
                        output_rate=Decimal("0.002"),
                    )
                }
            ),
            model_id="model-a",
            per_session_usd=Decimal("1"),
        ),
        working_scope=tmp_path,
    )

    with make_client(create_app(host, authenticator=_auth())) as client:
        run = client.post("/v1/runs", json={"prompt": "priced"}, headers=ALICE)
        session_id = run.json()["session_id"]
        owner = client.get(f"/v1/sessions/{session_id}/agent-controls", headers=ALICE)
        other = client.get(f"/v1/sessions/{session_id}/agent-controls", headers=BOB)

    assert owner.status_code == 200
    assert owner.json()["budget"] == {
        "tracking": "available",
        "pricing": "priced",
        "message_guard": "disabled",
        "session_guard": "within",
        "monthly_guard": "disabled",
        "pre_turn_guard": "disabled",
    }
    assert other.status_code == 404
    for private_name in (
        "model-a",
        "principal_id",
        "pricing_table",
        "per_session_usd",
        "ledger",
    ):
        assert private_name not in owner.text


def test_read_upload_action_and_handoff_remain_owner_scoped(tmp_path: Path) -> None:
    store = UploadStore(tmp_path / "uploads")
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="done")])],
                context_capacity=1_000,
            ),
            tools=(make_read_upload_tool(store.read),),
        ),
        working_scope=tmp_path,
    )

    with make_client(create_app(host, authenticator=_auth(), uploads=store)) as client:
        upload = client.post(
            "/v1/uploads",
            params={"name": "notes.txt"},
            content=b"private text",
            headers=ALICE,
        )
        reference = upload.json()["reference"]

        rejected = client.post(
            "/v1/runs",
            json={"prompt": "read", "uploads": [{"reference": reference}]},
            headers=BOB,
        )
        accepted = client.post(
            "/v1/runs",
            json={"prompt": "read", "uploads": [{"reference": reference}]},
            headers=ALICE,
        )
        projection = client.get(
            f"/v1/sessions/{accepted.json()['session_id']}/agent-controls",
            headers=ALICE,
        )

    assert rejected.status_code == 400
    assert reference not in rejected.text
    assert accepted.status_code == 200
    assert "attach_non_image_upload" in projection.json()["actions"]


def test_catalog_host_session_uses_its_own_agent_control_projection(
    tmp_path: Path,
) -> None:
    base = _host(tmp_path / "base")
    routed = _host(tmp_path / "routed")
    app = create_app(
        base,
        authenticator=_auth(),
        models={"alpha": ModelHost(label="Alpha", host=routed)},
    )

    with make_client(app) as client:
        outcome = client.post(
            "/v1/runs",
            json={"prompt": "plan", "model": "alpha", "permission_mode": "plan"},
            headers=ALICE,
        )
        projection = client.get(
            f"/v1/sessions/{outcome.json()['session_id']}/agent-controls",
            headers=ALICE,
        )

    assert outcome.status_code == 200
    assert projection.status_code == 200
    assert projection.json()["permission"]["last_accepted_run"]["mode"] == "plan"


def test_session_turn_rejects_bypass_without_echo_before_model_execution(
    tmp_path: Path,
) -> None:
    with make_client(create_app(_host(tmp_path), authenticator=_auth())) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]

        rejected = client.post(
            f"/v1/sessions/{session_id}/submit",
            json={"prompt": "do it", "permission_mode": "bypassPermissions"},
            headers=ALICE,
        )

    assert rejected.status_code == 400
    assert rejected.json() == {"detail": "permission mode unavailable"}
    assert "bypassPermissions" not in rejected.text


def test_run_and_session_turn_forward_an_accepted_mode_to_live_posture(
    tmp_path: Path,
) -> None:
    with make_client(create_app(_host(tmp_path), authenticator=_auth())) as client:
        standalone = client.post(
            "/v1/runs",
            json={"prompt": "plan", "permission_mode": "plan"},
            headers=ALICE,
        ).json()["session_id"]
        standalone_projection = client.get(
            f"/v1/sessions/{standalone}/agent-controls", headers=ALICE
        ).json()

        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]
        turn = client.post(
            f"/v1/sessions/{session_id}/submit",
            json={"prompt": "plan", "permission_mode": "plan"},
            headers=ALICE,
        )
        session_projection = client.get(
            f"/v1/sessions/{session_id}/agent-controls", headers=ALICE
        ).json()

    assert turn.status_code == 200
    assert standalone_projection["permission"]["last_accepted_run"] == {
        "mode": "plan",
        "state": "settled",
        "plan_active": False,
    }
    assert session_projection["permission"]["last_accepted_run"] == {
        "mode": "plan",
        "state": "settled",
        "plan_active": False,
    }


def test_event_stream_forwards_an_accepted_mode(tmp_path: Path) -> None:
    with make_client(create_app(_host(tmp_path), authenticator=_auth())) as client:
        response = client.post(
            "/v1/runs/events",
            json={"prompt": "plan", "permission_mode": "plan"},
            headers=ALICE,
        )
        outcome = json.loads(
            next(
                line.removeprefix("data: ")
                for line in response.text.splitlines()
                if line.startswith("data: ") and "session_id" in line
            )
        )
        projection = client.get(
            f"/v1/sessions/{outcome['session_id']}/agent-controls", headers=ALICE
        ).json()

    assert response.status_code == 200
    assert projection["permission"]["last_accepted_run"]["mode"] == "plan"


def test_live_plan_exit_uses_the_existing_question_round_trip(tmp_path: Path) -> None:
    with make_client(
        create_app(
            _plan_exit_host(tmp_path),
            authenticator=_auth(),
            sse_replay_buffer=20,
        )
    ) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]
        ticket = client.post(
            f"/v1/sessions/{session_id}/live-ticket", headers=ALICE
        ).json()["ticket"]

        with client.websocket_connect(
            f"/v1/sessions/{session_id}/live?ticket={ticket}"
        ) as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json(
                {
                    "type": "submit",
                    "payload": {"prompt": "plan", "permission_mode": "plan"},
                }
            )
            question_id = None
            for _ in range(20):
                message = websocket.receive_json()
                if (
                    message["type"] == "event"
                    and message["payload"]["type"] == "question-asked"
                ):
                    question_id = message["payload"]["payload"]["request_id"]
                    break
            assert question_id is not None

            websocket.send_json(
                {
                    "type": "question_answer",
                    "payload": {
                        "request_id": question_id,
                        "answers": ["approve"],
                    },
                }
            )
            resolved = False
            terminated = False
            for _ in range(30):
                message = websocket.receive_json()
                if message["type"] == "notice":
                    resolved = resolved or message["payload"].get("resolved") is True
                if (
                    message["type"] == "event"
                    and message["payload"]["type"] == "run-terminated"
                ):
                    terminated = True
                    break

    assert resolved is True
    assert terminated is True


def test_live_submit_rejects_non_image_when_read_upload_is_unavailable(
    tmp_path: Path,
) -> None:
    store = UploadStore(tmp_path / "uploads")
    with make_client(
        create_app(
            _host(tmp_path),
            authenticator=_auth(),
            uploads=store,
            sse_replay_buffer=20,
        )
    ) as client:
        upload = client.post(
            "/v1/uploads",
            params={"name": "notes.txt"},
            content=b"text",
            headers=ALICE,
        ).json()["reference"]
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]
        ticket = client.post(
            f"/v1/sessions/{session_id}/live-ticket", headers=ALICE
        ).json()["ticket"]

        with client.websocket_connect(
            f"/v1/sessions/{session_id}/live?ticket={ticket}"
        ) as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json(
                {
                    "type": "submit",
                    "payload": {
                        "prompt": "read",
                        "uploads": [{"reference": upload}],
                    },
                }
            )
            error = websocket.receive_json()

    assert error == {
        "type": "error",
        "payload": {"detail": "upload handoff unavailable"},
    }
    assert upload not in json.dumps(error)


def test_live_submit_forwards_accepted_mode(tmp_path: Path) -> None:
    with make_client(
        create_app(_host(tmp_path), authenticator=_auth(), sse_replay_buffer=20)
    ) as client:
        session_id = client.post("/v1/sessions", headers=ALICE).json()["session_id"]
        ticket = client.post(
            f"/v1/sessions/{session_id}/live-ticket", headers=ALICE
        ).json()["ticket"]

        with client.websocket_connect(
            f"/v1/sessions/{session_id}/live?ticket={ticket}"
        ) as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json(
                {
                    "type": "submit",
                    "payload": {"prompt": "plan", "permission_mode": "plan"},
                }
            )
            for _ in range(5):
                message = websocket.receive_json()
                if (
                    message["type"] == "event"
                    and message["payload"]["type"] == "run-terminated"
                ):
                    break

        projection = client.get(
            f"/v1/sessions/{session_id}/agent-controls", headers=ALICE
        ).json()

    assert projection["permission"]["last_accepted_run"]["mode"] == "plan"
