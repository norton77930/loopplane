"""Image input at the web edge (spec 036; ADR 0001 D1/D5/D6).

The conversation content model already supports images end to end — ``ImageBlock``
is part of ``ContentBlock``/``OutputBlock``, the model-facing seam carries it, the
event schema round-trips it, and the provider mappings emit it (OpenRouter/Ollama
inherit via the OpenAI mapping). The only missing piece for image *input* is at
the web edge: turning an uploaded image (028, a per-principal blob) into a leading
``ImageBlock`` on the user message the model receives.

``assemble_blocks`` is that pure seam. It resolves each owned upload reference,
embeds image uploads as leading ``ImageBlock``s (in reference order, ahead of the
trailing text prompt), and degrades gracefully — a non-owned/missing reference, an
image sent to a text-only model, or an oversized image each raise a clear,
public-safe error the route maps to a normalized ``ErrorResponse`` *before* any
run starts. Non-image uploads produce no block (they remain ``read_upload``-
readable, 028). No content-model or event-schema change (ADR D1).
"""

from __future__ import annotations

import base64
from collections.abc import Sequence

from loopplane.host import ContentBlock, ImageBlock, TextBlock
from loopplane.webapi.uploads import UploadStore, image_media_type

# A media size cap at the conversion point (ADR D6), mirroring the upload store's
# default; bounds the base64 payload that enters the context and the event stream.
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class UnknownUpload(ValueError):
    """A referenced upload is missing or not owned by the caller (no existence
    leak across principals — 022/028)."""


class MediaNotAccepted(ValueError):
    """An image upload was sent to a model that does not accept media (ADR D5)."""


class MediaTooLarge(ValueError):
    """An image upload exceeds the media size cap (ADR D6)."""


def assemble_blocks(
    prompt: str,
    references: Sequence[str],
    store: UploadStore,
    owner: str,
    *,
    accepts_media: bool,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> list[ContentBlock]:
    """Build the user message blocks for a turn that carries upload references.

    Each owned upload that is an image becomes an ``ImageBlock``, in ``references``
    order, ahead of the trailing ``TextBlock(prompt)``. Non-image uploads produce
    no block. Raises :class:`UnknownUpload` for a missing/non-owned reference,
    :class:`MediaNotAccepted` when an image is present but ``accepts_media`` is
    ``False``, and :class:`MediaTooLarge` when an image exceeds ``max_image_bytes``.
    Pure (store reads only); starts no run, emits no event.
    """

    images: list[ImageBlock] = []
    for reference in references:
        info = store.info(reference)
        if info is None or info.owner != owner:
            raise UnknownUpload("unknown upload reference")
        data = store.read(reference)
        if data is None:
            raise UnknownUpload("unknown upload reference")
        media_type = image_media_type(info.name, data)
        if media_type is None:
            # A non-image upload stays a read_upload-readable attachment (028);
            # it is never fabricated into an ImageBlock.
            continue
        if not accepts_media:
            raise MediaNotAccepted("selected model does not accept image input")
        if len(data) > max_image_bytes:
            raise MediaTooLarge("image upload exceeds the media size limit")
        images.append(
            ImageBlock(media=base64.b64encode(data).decode("ascii"), format=media_type)
        )

    blocks: list[ContentBlock] = list(images)
    blocks.append(TextBlock(text=prompt))
    return blocks
