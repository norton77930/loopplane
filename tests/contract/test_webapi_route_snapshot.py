"""Pre-split outward-contract baseline for the WebAPI router decomposition (T029)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("fastapi")

from fastapi.routing import APIRoute, APIWebSocketRoute  # noqa: E402

from loopplane.host import LoopPlaneHost  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402

SNAPSHOT_PATH = Path(__file__).with_name("fixtures") / "webapi_route_snapshot.json"


def _app():
    # Route construction only closes over the host.  The default-deny configuration
    # means this representative app performs no network or host call during capture.
    return create_app(cast(LoopPlaneHost, object()))


def _http_routes(app: object) -> list[dict[str, object]]:
    return sorted(
        [
            {
                "methods": sorted(route.methods or []),
                "path": route.path,
                "endpoint_name": route.endpoint.__name__,
                "response_model": (
                    route.response_model.__name__
                    if route.response_model is not None
                    else None
                ),
                "status_code": route.status_code,
            }
            for route in app.routes
            if isinstance(route, APIRoute)
        ],
        key=lambda entry: (
            entry["path"],
            entry["methods"],
            entry["endpoint_name"],
        ),
    )


def _websocket_routes(app: object) -> list[dict[str, str]]:
    return sorted(
        [
            {
                "path": route.path,
                "endpoint_name": route.endpoint.__name__,
            }
            for route in app.routes
            if isinstance(route, APIWebSocketRoute)
        ],
        key=lambda entry: (entry["path"], entry["endpoint_name"]),
    )


def _canonical_openapi(app: object) -> str:
    return json.dumps(app.openapi(), sort_keys=True, separators=(",", ":"))


def _baseline() -> dict[str, object]:
    assert SNAPSHOT_PATH.is_file(), (
        f"T029 pre-split route baseline is not checked in: {SNAPSHOT_PATH}"
    )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_pre_split_baseline_fixture_is_checked_in() -> None:
    assert SNAPSHOT_PATH.is_file(), (
        f"T029 pre-split route baseline is not checked in: {SNAPSHOT_PATH}"
    )


def test_http_route_inventory_matches_pre_split_baseline() -> None:
    baseline = _baseline()
    routes = _http_routes(_app())

    assert len(routes) == baseline["http_route_count"]
    assert routes == baseline["http_routes"]


def test_websocket_route_inventory_matches_pre_split_baseline() -> None:
    baseline = _baseline()
    routes = _websocket_routes(_app())

    assert len(routes) == baseline["websocket_route_count"]
    assert routes == baseline["websocket_routes"]


def test_canonical_openapi_matches_pre_split_baseline() -> None:
    baseline = _baseline()

    assert _canonical_openapi(_app()) == baseline["canonical_openapi"]


def test_create_app_signature_matches_pre_split_baseline() -> None:
    baseline = _baseline()

    assert str(inspect.signature(create_app)) == baseline["create_app_signature"]
