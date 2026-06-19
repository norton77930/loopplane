"""The optional cheap-model compaction summarizer (spec 042): a FAIL-SAFE async
overlay on the mechanical digest.

Compaction (``compact_history``) always runs first and produces a complete,
valid ``SummaryMarkerBlock``. When a host supplies a summarizer ``ModelBoundary``,
this overlay *tries* to replace the mechanical excerpts with a model-written
summary of the dropped conversation span. The single non-negotiable property is
**FAIL-SAFE**: ANY failure — an exception (including ``ContextOverflowError``), a
timeout, or empty output — falls back to the unchanged mechanical marker. The
overlay never raises, so a summarizer can never break a run.

The summarizer is a single, plain model turn: it advertises no tools and uses no
assembler, so it cannot recurse into compaction (FR-007).
"""

from __future__ import annotations

import anyio

from loopplane.loop.history import HistoryEntry
from loopplane.model.boundary import (
    Message,
    ModelBoundary,
    ModelRequest,
    TextIncrement,
)
from loopplane.model.content import SummaryDigest, SummaryMarkerBlock, TextBlock

# A small guard so a slow/hung summarizer cannot stall a run; a cheap summarizer
# is meant to be fast. On timeout the mechanical digest is kept (FR-005/FR-006).
DEFAULT_SUMMARIZER_TIMEOUT_SECONDS = 30.0

_INSTRUCTION = (
    "Summarize the following conversation so far, preserving the key facts, "
    "decisions, and context needed to continue the work. Be concise."
)


def _summarize_request(dropped: tuple[HistoryEntry, ...]) -> ModelRequest:
    """Build the summarize turn: a concise instruction followed by the dropped
    span, advertising no tools (so the summarizer cannot call tools)."""
    messages: list[Message] = [
        Message(role="user", blocks=[TextBlock(text=_INSTRUCTION)])
    ]
    messages.extend(
        Message(role=entry.role, blocks=list(entry.blocks)) for entry in dropped
    )
    return ModelRequest(context=messages, tools=[])


async def _collect_summary(summarizer: ModelBoundary, request: ModelRequest) -> str:
    parts: list[str] = []
    async for increment in summarizer.stream_turn(request):
        if isinstance(increment, TextIncrement):
            parts.append(increment.text)
    return "".join(parts)


async def summarize_compaction(
    *,
    summarizer: ModelBoundary,
    dropped: tuple[HistoryEntry, ...],
    marker: SummaryMarkerBlock,
    timeout_seconds: float | None = None,
) -> SummaryMarkerBlock:
    """Return a marker carrying the MODEL's summary in its digest, or the
    unchanged mechanical ``marker`` on ANY failure (FAIL-SAFE).

    The model summary replaces the digest's ``excerpts``; ``turn_count`` and
    ``tool_names`` stay mechanical. The summarizer turn advertises no tools and
    uses no assembler, so it cannot recurse into compaction. ``timeout_seconds``
    defaults to :data:`DEFAULT_SUMMARIZER_TIMEOUT_SECONDS` (resolved at call time).
    """
    if timeout_seconds is None:
        timeout_seconds = DEFAULT_SUMMARIZER_TIMEOUT_SECONDS
    request = _summarize_request(dropped)
    try:
        with anyio.fail_after(timeout_seconds):
            summary = await _collect_summary(summarizer, request)
    except Exception:
        # Any failure — exception, ContextOverflowError, or TimeoutError — keeps
        # the mechanical digest. The overlay must never break a run.
        return marker
    if not summary.strip():
        # Empty / whitespace-only output is not a valid summary.
        return marker
    return SummaryMarkerBlock(
        digest=SummaryDigest(
            turn_count=marker.digest.turn_count,
            tool_names=marker.digest.tool_names,
            excerpts=[summary],
        )
    )
