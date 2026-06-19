"""Optional model capabilities, probed additively (spec 036; ADR 0001 D5).

Image input reuses the existing ``ImageBlock`` content model, so the only new
model-facing concern is *capability negotiation*: does the selected model accept
media (images) as input? This is exposed as an **optional, duck-typed** signal so
the core :class:`~loopplane.model.boundary.ModelBoundary` Protocol stays unchanged
(still ``stream_turn`` + ``context_capacity``) and every existing implementation
keeps working. A model opts in by defining ``accepts_media() -> bool``; a model
that does not is treated as text-only.

Capability *negotiation* (rejecting an image sent to a text-only model) lives at
the model-selecting boundary — the web/API layer (028) — not in the Agent Loop,
so the runtime boundary is not blurred (Constitution IV; ADR D5).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MediaCapableModel(Protocol):
    """A model that advertises whether it accepts media (image) input."""

    def accepts_media(self) -> bool: ...


def accepts_media(model: object) -> bool:
    """Whether ``model`` accepts media (image) input.

    Returns ``model.accepts_media()`` when the model advertises the capability;
    otherwise a conservative ``False`` (a non-advertising model is text-only until
    it opts in). Pure; no I/O.
    """

    if isinstance(model, MediaCapableModel):
        return bool(model.accepts_media())
    return False
