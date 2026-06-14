"""US2: stream a run's normalized events as SSE, fail-safe on disconnect
(SC-002/005). All in-process via ``TestClient`` — no real socket.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    multi_text_model,
    tool_then_text_model,
)


def _collect(client, prompt: str = "go") -> tuple[list[dict], list[str]]:
    """Drive the SSE endpoint and return (event-frame payloads, frame labels)."""

    payloads: list[dict] = []
    labels: list[str] = []
    with client.stream("POST", "/v1/runs/events", json={"prompt": prompt}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        pending_label: str | None = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                pending_label = line[len("event:") :].strip()
            elif line.startswith("data:"):
                payloads.append(json.loads(line[len("data:") :].strip()))
                labels.append(pending_label or "message")
                pending_label = None
    return payloads, labels


def test_stream_yields_events_in_recorded_order(tmp_path: Path) -> None:
    client = make_client(
        create_app(
            build_test_host(tmp_path, model=tool_then_text_model()),
            authenticator=allow_all,
        )
    )

    payloads, labels = _collect(client)

    # The final frame is the outcome; everything before it is a normalized event.
    assert labels[-1] == "outcome"
    events = payloads[:-1]
    outcome = payloads[-1]
    assert len(events) >= 2
    # Each event frame is a serialize_event document (carries type + sequence),
    # delivered in recorded (monotonic sequence) order.
    sequences = [event["sequence"] for event in events]
    assert sequences == sorted(sequences)
    assert events[0]["type"] == "user-input"
    assert events[-1]["type"] == "run-terminated"
    # The outcome frame is the metadata-only RunResult.
    assert outcome["termination_reason"] == "natural-completion"
    assert "session_id" in outcome


def test_stream_order_is_deterministic(tmp_path: Path) -> None:
    first = make_client(
        create_app(
            build_test_host(tmp_path / "a", model=tool_then_text_model()),
            authenticator=allow_all,
        )
    )
    second = make_client(
        create_app(
            build_test_host(tmp_path / "b", model=tool_then_text_model()),
            authenticator=allow_all,
        )
    )

    payloads_a, _ = _collect(first)
    payloads_b, _ = _collect(second)

    # Session ids differ, but the type sequence is identical every run (SC-002).
    types_a = [p.get("type") for p in payloads_a[:-1]]
    types_b = [p.get("type") for p in payloads_b[:-1]]
    assert types_a == types_b


def test_disconnect_mid_stream_never_hangs_or_crashes(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("first", "second"))
    client = make_client(create_app(host, authenticator=allow_all))

    # Open the stream and disconnect early without draining it.
    with client.stream("POST", "/v1/runs/events", json={"prompt": "a"}) as response:
        assert response.status_code == 200
        for _ in response.iter_lines():
            break

    # The host recovered (the run did not hang): a fresh run still succeeds.
    follow_up = client.post("/v1/runs", json={"prompt": "b"})
    assert follow_up.status_code == 200
