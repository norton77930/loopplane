"""Unit 036: image input end-to-end over the web/API host + graceful degradation.

A run carrying an uploaded image reaches the model as a leading `ImageBlock`
(verified by a recording model that captures the `ModelRequest`); a non-image
upload is not embedded; a missing/non-owned ref → 400; an oversized image → 413;
and an image sent to a text-only model is rejected (400) with the catalog
advertising `accepts_media` per model. In-process only (no socket, no network).
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig  # noqa: E402
from loopplane.model.boundary import (  # noqa: E402
    ModelIncrement,
    ModelRequest,
    TextIncrement,
    TokenUsage,
    TurnEnd,
)
from loopplane.model.content import ImageBlock, TextBlock  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.app import ModelHost  # noqa: E402
from loopplane.webapi.uploads import UploadStore  # noqa: E402
from tests.webapi_helpers import allow_all, make_client  # noqa: E402

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9"
    "awAAAABJRU5ErkJggg=="
)


class RecordingModel:
    """A model boundary that records the last `ModelRequest` it streamed and
    emits one closing text turn — enough to drive a run and inspect its input."""

    def __init__(self, *, accepts_media: bool = True) -> None:
        self.last_request: ModelRequest | None = None
        self._accepts = accepts_media

    def context_capacity(self) -> int:
        return 100_000

    def accepts_media(self) -> bool:
        return self._accepts

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.last_request = request
        yield TextIncrement(text="ok")
        yield TurnEnd(stop_reason="end-turn", usage=TokenUsage())


def _host(root: Path, model: RecordingModel) -> LoopPlaneHost:
    root.mkdir(parents=True, exist_ok=True)
    return LoopPlaneHost(
        RuntimeConfig(model=model, tools=(), storage=StorageConfig(root=root)),
        working_scope=root,
    )


def _last_user_blocks(model: RecordingModel) -> list:
    assert model.last_request is not None
    user_messages = [m for m in model.last_request.context if m.role == "user"]
    assert user_messages, "expected a user message in the model request"
    return list(user_messages[-1].blocks)


def test_uploaded_image_reaches_the_model_as_leading_image_block(
    tmp_path: Path,
) -> None:
    model = RecordingModel(accepts_media=True)
    store = UploadStore(tmp_path / "uploads")
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            uploads=store,
            default_accepts_media=True,
        )
    )

    up = client.post("/v1/uploads", params={"name": "pic.png"}, content=_PNG)
    assert up.status_code == 200
    reference = up.json()["reference"]

    run = client.post(
        "/v1/runs",
        json={"prompt": "what is this?", "uploads": [{"reference": reference}]},
    )
    assert run.status_code == 200

    blocks = _last_user_blocks(model)
    assert len(blocks) == 2
    assert isinstance(blocks[0], ImageBlock)
    assert blocks[0].format == "image/png"
    assert base64.b64decode(blocks[0].media) == _PNG
    assert isinstance(blocks[1], TextBlock)
    assert blocks[1].text == "what is this?"


def test_non_image_upload_is_not_embedded(tmp_path: Path) -> None:
    model = RecordingModel(accepts_media=True)
    store = UploadStore(tmp_path / "uploads")
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            uploads=store,
            default_accepts_media=True,
        )
    )
    up = client.post("/v1/uploads", params={"name": "notes.txt"}, content=b"plain text")
    reference = up.json()["reference"]

    run = client.post(
        "/v1/runs", json={"prompt": "read it", "uploads": [{"reference": reference}]}
    )
    assert run.status_code == 200
    blocks = _last_user_blocks(model)
    assert [type(b) for b in blocks] == [TextBlock]


def test_no_uploads_is_identical_text_only_path(tmp_path: Path) -> None:
    model = RecordingModel(accepts_media=True)
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            default_accepts_media=True,
        )
    )
    run = client.post("/v1/runs", json={"prompt": "hello"})
    assert run.status_code == 200
    blocks = _last_user_blocks(model)
    assert blocks == [TextBlock(text="hello")]


def test_missing_reference_is_400(tmp_path: Path) -> None:
    model = RecordingModel(accepts_media=True)
    store = UploadStore(tmp_path / "uploads")
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            uploads=store,
            default_accepts_media=True,
        )
    )
    run = client.post(
        "/v1/runs", json={"prompt": "x", "uploads": [{"reference": "nope"}]}
    )
    assert run.status_code == 400
    assert model.last_request is None  # no run started with a missing attachment


def test_oversized_image_is_413(tmp_path: Path) -> None:
    model = RecordingModel(accepts_media=True)
    store = UploadStore(tmp_path / "uploads")
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            uploads=store,
            default_accepts_media=True,
            max_image_bytes=4,
        )
    )
    up = client.post("/v1/uploads", params={"name": "big.png"}, content=_PNG)
    reference = up.json()["reference"]
    run = client.post(
        "/v1/runs", json={"prompt": "x", "uploads": [{"reference": reference}]}
    )
    assert run.status_code == 413
    assert model.last_request is None


# --- US2: graceful degradation -----------------------------------------------


def _catalog(tmp_path: Path) -> dict[str, ModelHost]:
    shared = tmp_path / "store"
    vision = _host(shared, RecordingModel(accepts_media=True))
    text = _host(shared, RecordingModel(accepts_media=False))
    return {
        "vision": ModelHost(label="Vision", host=vision, accepts_media=True),
        "text": ModelHost(label="Text", host=text, accepts_media=False),
    }


def test_catalog_advertises_accepts_media(tmp_path: Path) -> None:
    models = _catalog(tmp_path)
    client = make_client(
        create_app(models["vision"].host, authenticator=allow_all, models=models)
    )
    listing = client.get("/v1/models")
    assert listing.status_code == 200
    by_id = {m["id"]: m for m in listing.json()}
    assert by_id["vision"]["accepts_media"] is True
    assert by_id["text"]["accepts_media"] is False
    assert all({"id", "label", "accepts_media"} == set(m) for m in listing.json())


def test_image_to_text_only_model_is_rejected(tmp_path: Path) -> None:
    models = _catalog(tmp_path)
    store = UploadStore(tmp_path / "uploads")
    client = make_client(
        create_app(
            models["vision"].host,
            authenticator=allow_all,
            models=models,
            uploads=store,
        )
    )
    up = client.post("/v1/uploads", params={"name": "pic.png"}, content=_PNG)
    reference = up.json()["reference"]

    rejected = client.post(
        "/v1/runs",
        json={
            "prompt": "see this",
            "model": "text",
            "uploads": [{"reference": reference}],
        },
    )
    assert rejected.status_code == 400

    # The same image to the vision model is accepted.
    ok = client.post(
        "/v1/runs",
        json={
            "prompt": "see this",
            "model": "vision",
            "uploads": [{"reference": reference}],
        },
    )
    assert ok.status_code == 200
