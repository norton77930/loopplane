"""Desktop JSON-RPC V1 framing/dispatcher contract (078 T017 subset)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from dispatcher import Dispatcher  # noqa: E402
from protocol import (  # noqa: E402
    INTERNAL_FAILURE,
    MAX_FRAME_BYTES,
    MAX_KEYS,
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
    PROTOCOL_NAME,
    RUNTIME_EVENT_SCHEMA,
    FrameDecodeError,
    SerializedWriter,
    decode_frame,
    encode_frame,
    make_error,
)


def test_decode_rejects_invalid_utf8() -> None:
    with pytest.raises(FrameDecodeError):
        decode_frame(b"\xff\xfe{")


def test_decode_rejects_duplicate_keys() -> None:
    with pytest.raises(FrameDecodeError, match="duplicate"):
        decode_frame('{"a":1,"a":2}')


def test_decode_enforces_128_keys_per_object() -> None:
    assert MAX_KEYS == 128
    accepted = {f"k{i}": i for i in range(128)}
    assert decode_frame(json.dumps(accepted)) == accepted
    rejected = {f"k{i}": i for i in range(129)}
    with pytest.raises(FrameDecodeError, match="too many keys"):
        decode_frame(json.dumps(rejected))


def test_encode_decode_round_trip() -> None:
    frame = encode_frame({"jsonrpc": "2.0", "id": "init", "method": "initialize"})
    assert frame.endswith(b"\n")
    obj = decode_frame(frame)
    assert obj["method"] == "initialize"


@pytest.mark.anyio
async def test_dispatcher_initialize_and_idempotent_result() -> None:
    calls = {"n": 0}

    async def ping(_params: dict[str, object]) -> dict[str, object]:
        calls["n"] += 1
        return {"pong": True}

    d = Dispatcher(methods={"ping": ping})
    init = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "init-1",
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
    assert init[0]["result"]["protocol"] == {
        "name": PROTOCOL_NAME,
        "major": PROTOCOL_MAJOR,
        "minor": PROTOCOL_MINOR,
    }
    assert init[0]["result"]["runtime_event_schema"] == RUNTIME_EVENT_SCHEMA

    r1 = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": "ping-2", "method": "ping", "params": {}})
    )
    r2 = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": "ping-2", "method": "ping", "params": {}})
    )
    assert r1[0]["result"] == r2[0]["result"]
    assert calls["n"] == 1

    changed = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "ping-2",
                "method": "ping",
                "params": {"x": 1},
            }
        )
    )
    assert changed[0]["error"]["code"] == -32003
    assert changed[0]["error"]["data"]["category"] == "conflict"
    assert calls["n"] == 1


@pytest.mark.anyio
async def test_dispatcher_rejects_malformed_notifications_and_params_exactly() -> None:
    d = Dispatcher(methods={})
    parse_error = await d.handle_frame(b"{")
    assert parse_error[0]["error"]["code"] == -32700
    assert parse_error[0]["error"]["data"]["category"] == "parse_error"

    notification = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "method": "system.status", "params": {}})
    )
    assert notification[0]["error"]["code"] == -32600

    invalid_id = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    )
    assert invalid_id[0]["error"]["code"] == -32600

    invalid_params = await d.handle_frame(
        json.dumps(
            {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": []}
        )
    )
    assert invalid_params[0]["error"]["code"] == -32602
    assert invalid_params[0]["error"]["data"]["category"] == "invalid_params"


@pytest.mark.anyio
async def test_dispatcher_caps_cached_request_identities() -> None:
    calls = {"n": 0}

    async def ping(_params: dict[str, object]) -> dict[str, object]:
        calls["n"] += 1
        return {"pong": True}

    d = Dispatcher(methods={"ping": ping})
    await d.handle_frame(
        json.dumps(
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
    for index in range(64):
        response = await d.handle_frame(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": f"ping-{index}",
                    "method": "ping",
                    "params": {},
                }
            )
        )
        assert "result" in response[0]
    busy = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": "ping-64", "method": "ping", "params": {}})
    )
    assert busy[0]["error"]["code"] == -32004
    assert calls["n"] == 64


@pytest.mark.anyio
async def test_dispatcher_unknown_method_and_internal_failure() -> None:
    d = Dispatcher(methods={})
    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "init-1",
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
    unknown = await d.handle_frame(
        json.dumps(
            {"jsonrpc": "2.0", "id": "unknown-2", "method": "nope", "params": {}}
        )
    )
    assert unknown[0]["error"]["code"] == -32601

    async def boom(_p: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("secret")

    d.register("boom", boom)
    failed = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": "boom-3", "method": "boom", "params": {}})
    )
    assert failed[0]["error"]["code"] == INTERNAL_FAILURE.code
    assert "secret" not in json.dumps(failed[0])


def test_serialized_writer_allows_runtime_event_frames_up_to_8_mib() -> None:
    written: list[bytes] = []
    writer = SerializedWriter(written.append)
    payload = "x" * (MAX_FRAME_BYTES + 1)

    writer.write_obj(
        {
            "jsonrpc": "2.0",
            "method": "runtime.event",
            "params": {
                "notification_seq": 1,
                "subscription_id": "sub-1",
                "session_id": "session-1",
                "event": {"chunk": payload},
            },
        }
    )

    assert len(written) == 1
    assert len(written[0]) > MAX_FRAME_BYTES
    assert len(written[0]) <= 8_388_609


def test_serialized_writer_keeps_control_frames_at_1_mib() -> None:
    writer = SerializedWriter(lambda _frame: None)
    with pytest.raises(FrameDecodeError, match="frame too large"):
        writer.write_obj(
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "result": {"padding": "x" * MAX_FRAME_BYTES},
            }
        )


def test_serialized_writer_bounds_pending_notification_queue() -> None:
    written: list[bytes] = []
    holder: dict[str, SerializedWriter] = {}

    def reenter_once(frame: bytes) -> None:
        written.append(frame)
        if len(written) != 1:
            return
        for _ in range(3):
            holder["writer"].write_obj(
                {"jsonrpc": "2.0", "method": "runtime.event", "params": {}}
            )

    writer = SerializedWriter(reenter_once, max_notification_frames=2)
    holder["writer"] = writer

    with pytest.raises(RuntimeError, match="notification queue overflow"):
        writer.write_obj({"jsonrpc": "2.0", "id": "request-1", "result": {}})
    assert writer.failed is True
    with pytest.raises(RuntimeError, match="writer failed"):
        writer.write_obj({"jsonrpc": "2.0", "id": "request-2", "result": {}})


def test_serialized_writer_fails_closed_when_stdout_write_fails() -> None:
    def fail_write(_frame: bytes) -> None:
        raise OSError("stdout unavailable")

    writer = SerializedWriter(fail_write)
    with pytest.raises(OSError, match="stdout unavailable"):
        writer.write_obj({"jsonrpc": "2.0", "id": "request-1", "result": {}})

    assert writer.failed is True
    with pytest.raises(RuntimeError, match="writer failed"):
        writer.write_obj({"jsonrpc": "2.0", "id": "request-2", "result": {}})


def test_serialized_writer_and_100_malformed_matrix() -> None:
    written: list[bytes] = []
    w = SerializedWriter(written.append)
    w.write_obj({"jsonrpc": "2.0", "id": "request-1", "result": {}})
    assert len(written) == 1

    base_cases: tuple[bytes, ...] = (
        b"",
        b"\n",
        b"{",
        b"null",
        b"[]",
        b'{"jsonrpc":"1.0","id":1',
        b'{"a":1,"a":2}',
        b"\xff\xff",
        b'{"value":NaN}',
        b'{"value":"\\ud800"}',
    )
    cases: list[bytes] = []
    for index in range(10):
        for raw in base_cases:
            if raw.startswith(b"{") and raw not in {
                b"{",
                b'{"jsonrpc":"1.0","id":1',
                b'{"a":1,"a":2}',
                b'{"value":NaN}',
                b'{"value":"\\ud800"}',
            }:
                raw = raw[:-1] + f',"case":{index}'.encode() + b"}"
            cases.append(raw)

    assert len(cases) == 100
    for raw in cases:
        with pytest.raises(FrameDecodeError):
            decode_frame(raw)
    assert make_error(1, INTERNAL_FAILURE)["error"]["data"]["messageKey"] == (
        "desktop.error.internal_failure"
    )
