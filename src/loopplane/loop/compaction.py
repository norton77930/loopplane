"""History compaction (FR-008; research A6): older history compacts into a
mechanically produced summary marker — turn counts, tool names used, bounded
excerpts of the earliest user intents — without ever separating a tool call
from its result.
"""

from __future__ import annotations

from datetime import UTC, datetime

from loopplane.loop.history import HistoryEntry, SessionHistory, is_tool_results_entry
from loopplane.model.content import (
    SummaryDigest,
    SummaryMarkerBlock,
    TextBlock,
    ToolCallBlock,
)

_EXCERPT_CHARS = 80
_EXCERPT_COUNT = 3
DEFAULT_KEEP_LAST = 4


def _digest(entries: tuple[HistoryEntry, ...]) -> SummaryDigest:
    tool_names = sorted(
        {
            block.tool_name
            for entry in entries
            for block in entry.blocks
            if isinstance(block, ToolCallBlock)
        }
    )
    excerpts: list[str] = []
    for entry in entries:
        if len(excerpts) >= _EXCERPT_COUNT:
            break
        if entry.role != "user" or is_tool_results_entry(entry):
            continue
        text = "".join(
            block.text for block in entry.blocks if isinstance(block, TextBlock)
        )
        if text:
            excerpts.append(text[:_EXCERPT_CHARS])
    return SummaryDigest(
        turn_count=sum(1 for entry in entries if entry.role == "assistant"),
        tool_names=tool_names,
        excerpts=excerpts,
    )


def compact_history(
    history: SessionHistory, *, keep_last: int = DEFAULT_KEEP_LAST
) -> bool:
    """Compact everything but the most recent entries into one summary
    marker. The cut point moves earlier as needed so a tool call and its
    result always stay on the same side. Returns False when there is nothing
    worth compacting.
    """
    entries = history.snapshot()
    if len(entries) < 2:
        return False
    # Keep at most `keep_last` entries, but always compact at least the first
    # entry when there is more than one — so a short history of few but large
    # entries can still free space on the overflow retry (FR-008).
    keep_from = max(1, min(len(entries) - keep_last, len(entries) - 1))
    # Never cut between a tool call and its result.
    while keep_from > 0 and is_tool_results_entry(entries[keep_from]):
        keep_from -= 1
    if keep_from <= 0:
        return False
    marker = HistoryEntry(
        role="user",
        blocks=(SummaryMarkerBlock(digest=_digest(entries[:keep_from])),),
        recorded_at=datetime.now(UTC),
    )
    history.replace_prefix(keep_from, marker)
    return True
