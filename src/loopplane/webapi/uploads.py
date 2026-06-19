"""Per-principal upload storage for the web/API host (unit 028).

A file-backed blob store keyed by an unguessable reference (the capability); the owner
is recorded in a sidecar. Reads are by reference; the store is never listed. The agent
reads an upload on demand via the ``read_upload`` Tool Gateway tool
(``loopplane.host.upload_tool``) — files are transient input by id, never embedded into
the content model. This module is pure storage (no runtime imports — webapi boundary).
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_MAX_BYTES = 5 * 1024 * 1024


class UploadTooLarge(ValueError):
    """An upload exceeds the configured size limit."""


@dataclass(frozen=True)
class StoredUpload:
    reference: str
    name: str
    owner: str
    size: int


def _safe_name(name: str) -> str:
    # Keep only the basename; drop anything path-like (public-safe).
    base = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return base or "upload"


# Image media types this host recognizes for embedding (spec 036). The set is
# intentionally the ones the provider image mappings accept; anything else is a
# non-image attachment (read_upload-readable, 028), never guessed into an image.
_EXTENSION_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def image_media_type(name: str, data: bytes) -> str | None:
    """The image media type of an upload, or ``None`` if it is not an image.

    Sniffs the leading magic bytes first (authoritative); falls back to the stored
    name's extension when the bytes are inconclusive. A non-image upload always
    returns ``None`` so it is never embedded as an ``ImageBlock`` (spec 036; it
    stays a ``read_upload``-readable attachment, 028). Standard library only.
    """

    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _EXTENSION_TYPES.get(extension)


class UploadStore:
    """A blob store keyed by an unguessable reference; the owner is recorded in a
    sidecar. Reads are by reference (the capability); the store is never listed."""

    def __init__(self, root: Path, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        self._root = root
        self._max_bytes = max_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, owner: str, name: str, data: bytes) -> StoredUpload:
        if len(data) > self._max_bytes:
            raise UploadTooLarge("upload exceeds the size limit")
        reference = secrets.token_urlsafe(16)
        record = StoredUpload(
            reference=reference, name=_safe_name(name), owner=owner, size=len(data)
        )
        (self._root / reference).write_bytes(data)
        (self._root / f"{reference}.meta.json").write_text(
            json.dumps({"name": record.name, "owner": owner, "size": record.size}),
            encoding="utf-8",
        )
        return record

    def info(self, reference: str) -> StoredUpload | None:
        meta_path = self._root / f"{reference}.meta.json"
        if not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return StoredUpload(
            reference=reference,
            name=str(meta.get("name", "upload")),
            owner=str(meta.get("owner", "")),
            size=int(meta.get("size", 0)),
        )

    def read(self, reference: str) -> bytes | None:
        # Reject anything that is not a bare reference token (no path traversal).
        if (
            not reference
            or "/" in reference
            or "\\" in reference
            or reference.startswith(".")
        ):
            return None
        blob = self._root / reference
        if not blob.is_file():
            return None
        return blob.read_bytes()
