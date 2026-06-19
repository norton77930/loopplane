"""Unit 028: model catalog + per-run routing + file uploads over the web/API host.

Model selection is resolved in the web/API layer (a run is routed to a chosen host);
the runtime gets one model per run. Uploads are auth-gated, per-principal, size-limited.
In-process only (no socket, no network).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig  # noqa: E402
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.app import ModelHost  # noqa: E402
from loopplane.webapi.uploads import UploadStore  # noqa: E402
from tests.webapi_helpers import allow_all, deny_all, make_client  # noqa: E402


def _model(text: str) -> ScriptedModel:
    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
        context_capacity=100_000,
    )


def _host(root: Path, text: str) -> LoopPlaneHost:
    root.mkdir(parents=True, exist_ok=True)
    return LoopPlaneHost(
        RuntimeConfig(model=_model(text), tools=(), storage=StorageConfig(root=root)),
        working_scope=root,
    )


def _catalog(tmp_path: Path) -> dict[str, ModelHost]:
    # Two single-model hosts sharing one checkpoint root (021).
    shared = tmp_path / "store"
    return {
        "alpha": ModelHost(label="Alpha", host=_host(shared, "from-alpha")),
        "beta": ModelHost(label="Beta", host=_host(shared, "from-beta")),
    }


def test_models_catalog_lists_entries(tmp_path: Path) -> None:
    models = _catalog(tmp_path)
    client = make_client(
        create_app(models["alpha"].host, authenticator=allow_all, models=models)
    )
    listing = client.get("/v1/models")
    assert listing.status_code == 200
    assert {m["id"] for m in listing.json()} == {"alpha", "beta"}
    # 036 — image-input capability; 045 — structured-output capability, per model.
    assert all(
        set(m) == {"id", "label", "accepts_media", "supports_structured_output"}
        for m in listing.json()
    )


def test_run_events_routed_to_the_selected_model(tmp_path: Path) -> None:
    models = _catalog(tmp_path)
    client = make_client(
        create_app(models["alpha"].host, authenticator=allow_all, models=models)
    )

    chosen = client.post("/v1/runs/events", json={"prompt": "go", "model": "beta"})
    assert chosen.status_code == 200
    assert "from-beta" in chosen.text

    default = client.post("/v1/runs/events", json={"prompt": "go"})
    assert "from-alpha" in default.text


def test_unknown_model_is_400(tmp_path: Path) -> None:
    models = _catalog(tmp_path)
    client = make_client(
        create_app(models["alpha"].host, authenticator=allow_all, models=models)
    )
    assert (
        client.post("/v1/runs", json={"prompt": "go", "model": "ghost"}).status_code
        == 400
    )


def test_upload_stores_per_principal_and_returns_reference(tmp_path: Path) -> None:
    host = _host(tmp_path / "store", "ok")
    store = UploadStore(tmp_path / "uploads")
    client = make_client(create_app(host, authenticator=allow_all, uploads=store))

    response = client.post(
        "/v1/uploads", params={"name": "notes.txt"}, content=b"hello file"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "notes.txt"
    reference = body["reference"]
    assert store.read(reference) == b"hello file"
    info = store.info(reference)
    assert (
        info is not None and info.owner == "anyone"
    )  # allow_all -> Principal(id="anyone")


def test_upload_too_large_is_413(tmp_path: Path) -> None:
    host = _host(tmp_path / "store", "ok")
    store = UploadStore(tmp_path / "uploads", max_bytes=4)
    client = make_client(create_app(host, authenticator=allow_all, uploads=store))
    assert client.post("/v1/uploads", content=b"12345").status_code == 413


def test_models_and_uploads_are_auth_gated(tmp_path: Path) -> None:
    models = _catalog(tmp_path)
    store = UploadStore(tmp_path / "uploads")
    client = make_client(
        create_app(
            models["alpha"].host, authenticator=deny_all, models=models, uploads=store
        )
    )
    assert client.get("/v1/models").status_code == 401
    assert client.post("/v1/uploads", content=b"x").status_code == 401
