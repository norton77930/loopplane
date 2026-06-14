"""US3: conduct an interactive session over the API — open, submit, answer a
pending approval out-of-band, and cancel (FR-007-FR-010). In-process only.
"""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import httpx
import pytest

pytest.importorskip("fastapi")

from loopplane.host import ApprovalPolicy  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    multi_text_model,
    tool_then_text_model,
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


def test_submit_without_approval_returns_outcome(tmp_path: Path) -> None:
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


@pytest.mark.anyio
async def test_interactive_approval_flow(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path,
        model=tool_then_text_model(),
        approval=ApprovalPolicy(ask=frozenset({"echo"})),
    )
    app = create_app(host, authenticator=allow_all)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            session_id = (await client.post("/v1/sessions")).json()["session_id"]
            found = anyio.Event()
            request_id: dict[str, str] = {}
            submit: dict[str, httpx.Response] = {}

            async def read_events() -> None:
                async with client.stream(
                    "GET", f"/v1/sessions/{session_id}/events"
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            event = json.loads(line[len("data:") :].strip())
                            if event.get("type") == "approval-requested":
                                request_id["id"] = event["payload"]["request_id"]
                                found.set()
                                return

            async def do_submit() -> None:
                submit["response"] = await client.post(
                    f"/v1/sessions/{session_id}/submit", json={"prompt": "go"}
                )

            async with anyio.create_task_group() as task_group:
                task_group.start_soon(read_events)
                task_group.start_soon(do_submit)
                await found.wait()
                answer = await client.post(
                    f"/v1/sessions/{session_id}/approvals/{request_id['id']}",
                    json={"allow": True},
                )
                assert answer.status_code == 200
                assert answer.json() == {"resolved": True}

            assert submit["response"].status_code == 200
            assert (
                submit["response"].json()["termination_reason"] == "natural-completion"
            )
            await client.post(f"/v1/sessions/{session_id}/cancel")
