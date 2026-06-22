"""Unit 071: durable replay store integration with the session stream."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

pytest.importorskip("fastapi")

from loopplane.model import TextBlock  # noqa: E402
from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from loopplane.webapi.sessions import run_session  # noqa: E402
from tests.replay_helpers import file_replay_store, replay_record  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    multi_text_model,
)

ALICE = {"Authorization": "Bearer tok-alice"}
BOB = {"Authorization": "Bearer tok-bob"}


def _tokens() -> object:
    return token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})


@pytest.mark.anyio
async def test_run_session_appends_frames_to_replay_store(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("alpha"), tools=())
    store = file_replay_store(tmp_path / "replay")
    sessions: dict = {}
    ready = anyio.Event()
    box: dict[str, str] = {}

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            run_session,
            host,
            sessions,
            ready,
            box,
            "owner-1",
            False,
            False,
            0,
            store,
        )
        await ready.wait()
        entry = sessions[box["sid"]]
        await entry.session.submit([TextBlock(text="go")])
        entry.close.set()

    records, problems = store.load_after(box["sid"], "owner-1", 0, limit=100)

    assert problems == []
    assert records
    assert [record.sequence for record in records] == sorted(
        record.sequence for record in records
    )
    assert all(
        record.frame.startswith(f"id: {record.sequence}\n") for record in records
    )


def test_app_replays_stored_frames_for_owned_session(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path / "host", model=multi_text_model("seed"), storage=True, tools=()
    )
    store = file_replay_store(tmp_path / "replay")

    async def seed_session() -> str:
        outcome = await host.run(
            [TextBlock(text="seed")],
            lambda event: None,
            principal_id="anyone",
        )
        for sequence in range(1, 4):
            await store.append(
                replay_record(
                    sequence,
                    session_id=outcome.session_id,
                    principal_id="anyone",
                )
            )
        return outcome.session_id

    session_id = anyio.run(seed_session)

    with make_client(
        create_app(
            host,
            authenticator=allow_all,
            event_replay_store=store,
            event_replay_poll_interval_seconds=0,
            event_replay_idle_polls=1,
        )
    ) as client:
        response = client.get(
            f"/v1/sessions/{session_id}/events",
            headers={"Last-Event-ID": "1"},
        )

    assert response.status_code == 200
    assert response.text == "id: 2\ndata: e2\n\nid: 3\ndata: e3\n\n"


def test_app_without_replay_store_keeps_non_live_events_not_found(
    tmp_path: Path,
) -> None:
    host = build_test_host(
        tmp_path / "host", model=multi_text_model("seed"), storage=True, tools=()
    )

    async def seed_session() -> str:
        outcome = await host.run(
            [TextBlock(text="seed")],
            lambda event: None,
            principal_id="anyone",
        )
        return outcome.session_id

    session_id = anyio.run(seed_session)

    with make_client(create_app(host, authenticator=allow_all)) as client:
        response = client.get(
            f"/v1/sessions/{session_id}/events",
            headers={"Last-Event-ID": "1"},
        )

    assert response.status_code == 404


def test_replay_events_are_owner_scoped(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path / "host", model=multi_text_model("seed"), storage=True, tools=()
    )
    store = file_replay_store(tmp_path / "replay")

    with make_client(
        create_app(
            host,
            authenticator=_tokens(),
            event_replay_store=store,
            event_replay_poll_interval_seconds=0,
            event_replay_idle_polls=1,
        )
    ) as client:
        session_id = client.post(
            "/v1/runs", json={"prompt": "go"}, headers=ALICE
        ).json()["session_id"]
        anyio.run(
            store.append,
            replay_record(1, session_id=session_id, principal_id="alice"),
        )

        denied = client.get(
            f"/v1/sessions/{session_id}/events",
            headers={**BOB, "Last-Event-ID": "0"},
        )
        allowed = client.get(
            f"/v1/sessions/{session_id}/events",
            headers={**ALICE, "Last-Event-ID": "0"},
        )

    assert denied.status_code == 404
    assert denied.json() == {"detail": "not found"}
    assert "alice" not in denied.text
    assert allowed.status_code == 200
    assert allowed.text == "id: 1\ndata: e1\n\n"


def test_delete_session_removes_replay_records(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path / "host", model=multi_text_model("seed"), storage=True, tools=()
    )
    store = file_replay_store(tmp_path / "replay")

    with make_client(
        create_app(host, authenticator=_tokens(), event_replay_store=store)
    ) as client:
        session_id = client.post(
            "/v1/runs", json={"prompt": "go"}, headers=ALICE
        ).json()["session_id"]
        anyio.run(
            store.append,
            replay_record(1, session_id=session_id, principal_id="alice"),
        )

        assert (
            client.delete(f"/v1/sessions/{session_id}", headers=ALICE).status_code
            == 200
        )

    assert store.load_after(session_id, "alice", 0, limit=10) == ([], [])
