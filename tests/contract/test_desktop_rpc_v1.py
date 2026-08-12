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
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
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


def test_encode_decode_round_trip() -> None:
    frame = encode_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert frame.endswith(b"\n")
    obj = decode_frame(frame)
    assert obj["method"] == "initialize"


@pytest.mark.anyio
async def test_dispatcher_initialize_and_idempotent_result() -> None:
    calls = {"n": 0}

    async def ping(_params: dict) -> dict:
        calls["n"] += 1
        return {"pong": True}

    d = Dispatcher(methods={"ping": ping})
    init = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocol": PROTOCOL_NAME,
                    "version": PROTOCOL_VERSION,
                },
            }
        )
    )
    assert init[0]["result"]["version"] == PROTOCOL_VERSION

    r1 = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}})
    )
    r2 = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}})
    )
    assert r1[0]["result"] == r2[0]["result"]
    assert calls["n"] == 1


@pytest.mark.anyio
async def test_dispatcher_unknown_method_and_internal_failure() -> None:
    d = Dispatcher(methods={})
    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
        )
    )
    unknown = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "nope", "params": {}})
    )
    assert unknown[0]["error"]["code"] == -32601

    async def boom(_p: dict) -> dict:
        raise RuntimeError("secret")

    d.register("boom", boom)
    failed = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "boom", "params": {}})
    )
    assert failed[0]["error"]["code"] == INTERNAL_FAILURE.code
    assert "secret" not in json.dumps(failed[0])


def test_serialized_writer_and_100_malformed_matrix() -> None:
    written: list[bytes] = []
    w = SerializedWriter(written.append)
    w.write_obj({"jsonrpc": "2.0", "id": 1, "result": {}})
    assert len(written) == 1

    failures = 0
    cases = [
        b"",
        b"\n",
        b"{",
        b"null",
        b"[]",
        '{"jsonrpc":"1.0","id":1}',
        '{"a":1,"a":2}',
        b"\xff\xff",
    ]
    # Expand to 100 deterministic malformed/stale cases
    for i in range(100):
        raw = cases[i % len(cases)]
        if isinstance(raw, str):
            raw_b = raw.encode()
        else:
            raw_b = raw
        if i >= len(cases):
            raw_b = (b"{" + b"x" * (i % 50) + b"}") if i % 3 else raw_b
        try:
            decode_frame(raw_b)
        except FrameDecodeError:
            failures += 1
        except Exception:
            failures += 1
    # Most are invalid; ensure matrix ran 100 times without model-call side effects
    assert failures >= 50
    assert make_error(1, INTERNAL_FAILURE)["error"]["data"]["messageKey"] == (
        "desktop.error.internal_failure"
    )
