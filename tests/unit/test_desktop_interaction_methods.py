"""Desktop Host-only interaction RPC methods (078 T026)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from dispatcher import Dispatcher  # noqa: E402
from interaction import InteractionLease  # noqa: E402
from methods.interaction import InteractionMethods  # noqa: E402
from protocol import (  # noqa: E402
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
    PROTOCOL_NAME,
    RUNTIME_EVENT_SCHEMA,
    RpcError,
)

pytestmark = pytest.mark.anyio


def _host(tmp_path: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / "store",
            ),
        ),
        working_scope=tmp_path,
    )


async def _init(d: Dispatcher) -> None:
    await d.handle_frame(
        __import__("json").dumps(
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocol": {
                        "name": PROTOCOL_NAME,
                        "major": PROTOCOL_MAJOR,
                        "minor": PROTOCOL_MINOR,
                    },
                    "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
                    "client": {"name": "test-client", "version": "0"},
                    "requested_capabilities": [],
                },
            }
        )
    )


async def test_create_submit_release_round_trip(tmp_path: Path) -> None:
    import json

    host = _host(tmp_path)
    lease = InteractionLease()
    notifications: list[dict] = []
    d: Dispatcher

    async def emit_event(payload: dict) -> None:
        notifications.append(d.next_notification("runtime.event", payload))

    async def emit_outcome(payload: dict) -> None:
        notifications.append(d.next_notification("runtime.outcome", payload))

    async def emit_state(payload: dict) -> None:
        notifications.append(d.next_notification("runtime.state", payload))

    async def emit_closed(payload: dict) -> None:
        notifications.append(d.next_notification("runtime.subscriptionClosed", payload))

    lease.set_emitters(
        emit_event=emit_event,
        emit_outcome=emit_outcome,
        emit_state=emit_state,
        emit_closed=emit_closed,
    )
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    d = Dispatcher(methods=methods.handlers())
    await _init(d)

    created = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "session.createInteractive",
                "params": {"mutation_id": "m1", "pane_id": "p1"},
            }
        )
    )
    assert "result" in created[0]
    sub_id = created[0]["result"]["subscription_id"]
    session_id = created[0]["result"]["session_id"]
    assert notifications[-1]["method"] == "runtime.state"
    assert notifications[-1]["params"] == {
        "notification_seq": 1,
        "state": "opened",
    }

    submitted = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-2",
                "method": "interaction.submit",
                "params": {
                    "mutation_id": "m2",
                    "subscription_id": sub_id,
                    "prompt": "hello",
                },
            }
        )
    )
    assert submitted[0]["result"]["accepted"] is True
    assert submitted[0]["result"]["session_id"] == session_id
    assert notifications[-1]["method"] == "runtime.outcome"
    assert all(frame["method"] == "runtime.event" for frame in notifications[1:-1])
    assert [frame["params"]["notification_seq"] for frame in notifications] == list(
        range(1, len(notifications) + 1)
    )
    for frame in notifications:
        if frame["method"] == "runtime.event":
            assert isinstance(frame["params"]["event"], dict)

    released = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-3",
                "method": "session.releaseInteractive",
                "params": {"mutation_id": "m3", "subscription_id": sub_id},
            }
        )
    )
    assert released[0]["result"]["released"] is True
    assert notifications[-1]["method"] == "runtime.subscriptionClosed"
    assert notifications[-1]["params"] == {
        "notification_seq": len(notifications),
        "subscription_id": sub_id,
        "session_id": session_id,
        "reason": "released",
        "history_readable": True,
    }


async def test_shutdown_emits_draining_then_final_close(tmp_path: Path) -> None:
    host = _host(tmp_path)
    lease = InteractionLease()
    notifications: list[tuple[str, dict]] = []

    async def emit_state(payload: dict) -> None:
        notifications.append(("runtime.state", payload))

    async def emit_closed(payload: dict) -> None:
        notifications.append(("runtime.subscriptionClosed", payload))

    lease.set_emitters(emit_state=emit_state, emit_closed=emit_closed)
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    created = await methods.create_interactive({"mutation_id": "m1"})

    notifications.clear()
    await lease.shutdown()

    assert notifications == [
        ("runtime.state", {"state": "draining"}),
        (
            "runtime.subscriptionClosed",
            {
                "subscription_id": created["subscription_id"],
                "session_id": created["session_id"],
                "reason": "shutdown",
                "history_readable": True,
            },
        ),
    ]


async def test_second_create_is_busy(tmp_path: Path) -> None:
    import json

    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    d = Dispatcher(methods=methods.handlers())
    await _init(d)

    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "session.createInteractive",
                "params": {"mutation_id": "m1"},
            }
        )
    )
    second = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-2",
                "method": "session.createInteractive",
                "params": {"mutation_id": "m2"},
            }
        )
    )
    assert second[0]["error"]["code"] == -32004
    assert second[0]["error"]["data"]["category"] == "busy"


async def test_missing_mutation_id_rejected(tmp_path: Path) -> None:
    import json

    host = _host(tmp_path)
    methods = InteractionMethods(host, InteractionLease(), working_scope=tmp_path)
    d = Dispatcher(methods=methods.handlers())
    await _init(d)
    bad = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "session.createInteractive",
                "params": {},
            }
        )
    )
    assert bad[0]["error"]["code"] == -32602


async def test_resume_after_release(tmp_path: Path) -> None:
    import json

    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    d = Dispatcher(methods=methods.handlers())
    await _init(d)

    created = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "session.createInteractive",
                "params": {"mutation_id": "m1"},
            }
        )
    )
    session_id = created[0]["result"]["session_id"]
    sub_id = created[0]["result"]["subscription_id"]
    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-2",
                "method": "interaction.submit",
                "params": {
                    "mutation_id": "m2",
                    "subscription_id": sub_id,
                    "prompt": "first",
                },
            }
        )
    )
    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-3",
                "method": "session.releaseInteractive",
                "params": {"mutation_id": "m3", "subscription_id": sub_id},
            }
        )
    )

    resumed = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "request-4",
                "method": "session.resumeInteractive",
                "params": {
                    "mutation_id": "m4",
                    "session_id": session_id,
                },
            }
        )
    )
    assert "result" in resumed[0]
    assert resumed[0]["result"]["session_id"] == session_id
    await lease.shutdown()


async def test_handlers_do_not_import_controller() -> None:
    import methods.interaction as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "loopplane.controller" not in source
    assert "loopplane.gateway" not in source
    assert "ArtifactStore" not in source
    # Ensure RpcError is raiseable for boundary coverage
    with pytest.raises(RpcError):
        raise RpcError(
            code=-32004,
            message="Busy",
            category="busy",
            retryable=False,
            message_key="desktop.error.busy",
        )
