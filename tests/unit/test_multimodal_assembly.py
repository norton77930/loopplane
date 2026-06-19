"""Unit 036: the web-edge image-assembly helper + image media-type detection.

`assemble_blocks` turns owned upload references into the user message's leading
`ImageBlock`s (images only, in order, ahead of the text prompt), enforcing
ownership, the media size cap, and graceful degradation for a text-only model.
Non-image uploads produce no block (they stay `read_upload`-readable, 028). Pure;
offline.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from loopplane.model.content import ImageBlock, TextBlock
from loopplane.webapi.multimodal import (
    MediaNotAccepted,
    MediaTooLarge,
    UnknownUpload,
    assemble_blocks,
)
from loopplane.webapi.uploads import UploadStore, image_media_type

# A minimal but valid 1x1 PNG (magic bytes + IHDR + IDAT + IEND).
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9"
    "awAAAABJRU5ErkJggg=="
)
_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8
_GIF = b"GIF89a" + b"\x00" * 8
_WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


# --- image_media_type detection ----------------------------------------------


def test_detects_png_by_magic_bytes() -> None:
    assert image_media_type("whatever", _PNG) == "image/png"


def test_detects_jpeg_gif_webp() -> None:
    assert image_media_type("x", _JPEG) == "image/jpeg"
    assert image_media_type("x", _GIF) == "image/gif"
    assert image_media_type("x", _WEBP) == "image/webp"


def test_detects_by_extension_when_magic_absent() -> None:
    # A name hint still resolves a type when the bytes are inconclusive.
    assert image_media_type("photo.jpg", b"not-real-bytes") == "image/jpeg"
    assert image_media_type("photo.PNG", b"xxxx") == "image/png"


def test_non_image_is_none() -> None:
    assert image_media_type("notes.txt", b"just some text") is None
    assert image_media_type("doc.pdf", b"%PDF-1.7 ...") is None


# --- assemble_blocks ----------------------------------------------------------


def test_no_uploads_is_text_only(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    blocks = assemble_blocks(
        "hello", [], store, "alice", accepts_media=True, max_image_bytes=1_000_000
    )
    assert blocks == [TextBlock(text="hello")]


def test_image_becomes_leading_image_block(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("alice", "pic.png", _PNG)

    blocks = assemble_blocks(
        "what is this?",
        [stored.reference],
        store,
        "alice",
        accepts_media=True,
        max_image_bytes=1_000_000,
    )

    assert len(blocks) == 2
    image, text = blocks
    assert isinstance(image, ImageBlock)
    assert image.format == "image/png"
    assert base64.b64decode(image.media) == _PNG
    assert isinstance(text, TextBlock)
    assert text.text == "what is this?"


def test_non_image_upload_yields_no_block(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("alice", "notes.txt", b"plain text body")

    blocks = assemble_blocks(
        "read it",
        [stored.reference],
        store,
        "alice",
        accepts_media=True,
        max_image_bytes=1_000_000,
    )

    # Only the text prompt — the non-image upload stays read_upload-readable (028).
    assert blocks == [TextBlock(text="read it")]


def test_multiple_images_keep_order_ahead_of_text(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    a = store.save("alice", "a.png", _PNG)
    b = store.save("alice", "b.jpg", _JPEG)
    txt = store.save("alice", "n.txt", b"ignored as a block")

    blocks = assemble_blocks(
        "compare",
        [a.reference, txt.reference, b.reference],
        store,
        "alice",
        accepts_media=True,
        max_image_bytes=1_000_000,
    )

    assert [type(b_) for b_ in blocks] == [ImageBlock, ImageBlock, TextBlock]
    assert isinstance(blocks[0], ImageBlock) and blocks[0].format == "image/png"
    assert isinstance(blocks[1], ImageBlock) and blocks[1].format == "image/jpeg"


def test_unknown_reference_raises(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    with pytest.raises(UnknownUpload):
        assemble_blocks(
            "x", ["nope"], store, "alice", accepts_media=True, max_image_bytes=1_000
        )


def test_non_owned_reference_raises(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("bob", "secret.png", _PNG)
    # Alice may not read Bob's upload — treated as not-found (no existence leak).
    with pytest.raises(UnknownUpload):
        assemble_blocks(
            "x",
            [stored.reference],
            store,
            "alice",
            accepts_media=True,
            max_image_bytes=1_000_000,
        )


def test_image_to_text_only_model_raises(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("alice", "pic.png", _PNG)
    with pytest.raises(MediaNotAccepted):
        assemble_blocks(
            "x",
            [stored.reference],
            store,
            "alice",
            accepts_media=False,
            max_image_bytes=1_000_000,
        )


def test_non_image_to_text_only_model_is_fine(tmp_path: Path) -> None:
    # A non-image upload does not trip capability negotiation.
    store = UploadStore(tmp_path)
    stored = store.save("alice", "notes.txt", b"text")
    blocks = assemble_blocks(
        "x",
        [stored.reference],
        store,
        "alice",
        accepts_media=False,
        max_image_bytes=1_000_000,
    )
    assert blocks == [TextBlock(text="x")]


def test_oversized_image_raises(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("alice", "big.png", _PNG)
    with pytest.raises(MediaTooLarge):
        assemble_blocks(
            "x",
            [stored.reference],
            store,
            "alice",
            accepts_media=True,
            max_image_bytes=4,
        )
