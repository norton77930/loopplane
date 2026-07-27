"""Image input at the web edge (spec 036; ADR 0001 D1/D5/D6).

The conversation content model already supports images end to end — ``ImageBlock``
is part of ``ContentBlock``/``OutputBlock``, the model-facing seam carries it, the
event schema round-trips it, and the provider mappings emit it (OpenRouter/Ollama
inherit via the OpenAI mapping). The only missing piece for image *input* is at
the web edge: turning an uploaded image (028, a per-principal blob) into a leading
``ImageBlock`` on the user message the model receives.

``assemble_blocks`` is that pure seam. It resolves each owned upload reference,
embeds image uploads as leading ``ImageBlock``s, and emits bounded opaque metadata
for non-image uploads only when ``read_upload`` is available. A non-owned/missing
reference, unsupported image, oversized image, or unavailable handoff raises a
public-safe error *before* any run starts. Image and handoff blocks retain reference
order within their groups and precede the trailing text prompt. No content-model or
event-schema change (ADR D1).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence

from loopplane.host import ContentBlock, ImageBlock, TextBlock
from loopplane.webapi.uploads import UploadStore, image_media_type

# A media size cap at the conversion point (ADR D6), mirroring the upload store's
# default; bounds the base64 payload that enters the context and the event stream.
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_NON_IMAGE_HANDOFFS = 8
MAX_UPLOAD_HANDOFF_BYTES = 256


class UnknownUpload(ValueError):
    """A referenced upload is missing or not owned by the caller (no existence
    leak across principals — 022/028)."""


class MediaNotAccepted(ValueError):
    """An image upload was sent to a model that does not accept media (ADR D5)."""


class MediaTooLarge(ValueError):
    """An image upload exceeds the media size cap (ADR D6)."""


class UploadHandoffRejected(ValueError):
    """A non-image reference cannot be handed to ``read_upload`` safely."""


def assemble_blocks(
    prompt: str,
    references: Sequence[str],
    store: UploadStore,
    owner: str,
    *,
    accepts_media: bool,
    accepts_read_upload: bool = False,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> list[ContentBlock]:
    """Build owned image and bounded non-image handoff blocks for one turn.

    All references are resolved and ownership-checked before blocks are returned.
    Images become leading ``ImageBlock`` values. Each non-image becomes one compact
    metadata-only ``TextBlock`` that names the existing ``read_upload`` tool; the
    web edge never invokes that tool. The original prompt remains the trailing block.
    """

    resolved: list[tuple[str, bytes, str | None]] = []
    for reference in references:
        info = store.info(reference)
        if info is None or info.owner != owner:
            raise UnknownUpload("unknown upload reference")
        data = store.read(reference)
        if data is None:
            raise UnknownUpload("unknown upload reference")
        resolved.append((reference, data, image_media_type(info.name, data)))

    images: list[ImageBlock] = []
    handoffs: list[TextBlock] = []
    for reference, data, media_type in resolved:
        if media_type is None:
            if not accepts_read_upload or len(handoffs) >= MAX_NON_IMAGE_HANDOFFS:
                raise UploadHandoffRejected("upload handoff unavailable")
            encoded = json.dumps(
                {
                    "type": "loopplane_upload_reference",
                    "reference": reference,
                    "reader": "read_upload",
                },
                separators=(",", ":"),
            )
            if len(encoded.encode("utf-8")) > MAX_UPLOAD_HANDOFF_BYTES:
                raise UploadHandoffRejected("upload handoff unavailable")
            handoffs.append(TextBlock(text=encoded))
            continue
        if not accepts_media:
            raise MediaNotAccepted("selected model does not accept image input")
        if len(data) > max_image_bytes:
            raise MediaTooLarge("image upload exceeds the media size limit")
        images.append(
            ImageBlock(media=base64.b64encode(data).decode("ascii"), format=media_type)
        )

    blocks: list[ContentBlock] = [*images, *handoffs]
    blocks.append(TextBlock(text=prompt))
    return blocks
