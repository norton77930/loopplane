"""Session history with immutable point-in-time snapshots (FR-006, FR-007).

Appends may be observed by a recording hook installed by the Controller (the
recording boundary, FR-094): the append completes only after the hook —
including its durable flush — has completed.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

from loopplane.model.content import ContentBlock, ToolResultBlock


class HistoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    blocks: tuple[ContentBlock, ...]
    recorded_at: AwareDatetime


HistoryHook = Callable[[HistoryEntry], Awaitable[None]]


def is_tool_results_entry(entry: HistoryEntry) -> bool:
    """A user entry carrying only tool-result blocks (a turn's tool outputs),
    as distinct from a verbatim user message. The single source of truth for
    this classification across compaction, recording, and resume.
    """
    return (
        entry.role == "user"
        and len(entry.blocks) > 0
        and all(isinstance(block, ToolResultBlock) for block in entry.blocks)
    )


class SessionHistory:
    def __init__(self, *, on_append: HistoryHook | None = None) -> None:
        self._entries: list[HistoryEntry] = []
        self._on_append = on_append

    def __len__(self) -> int:
        return len(self._entries)

    async def append(
        self, role: Literal["user", "assistant"], blocks: Sequence[ContentBlock]
    ) -> None:
        entry = HistoryEntry(
            role=role, blocks=tuple(blocks), recorded_at=datetime.now(UTC)
        )
        self._entries.append(entry)
        if self._on_append is not None:
            await self._on_append(entry)

    def restore(self, entries: Iterable[HistoryEntry]) -> None:
        """Adopt rebuilt entries on resume without re-recording them."""
        self._entries = list(entries)

    def replace_prefix(self, count: int, entry: HistoryEntry) -> None:
        """Compaction support (FR-008): replace the first `count` in-memory
        entries with one summary entry. The durable stream is append-only
        and keeps the originals; the recording hook is deliberately not
        invoked.
        """
        self._entries[:count] = [entry]

    def replace_entry(self, index: int, entry: HistoryEntry) -> None:
        """Compaction-summarizer support (spec 042): swap one in-memory entry
        in place — used to augment a just-produced mechanical summary marker
        with a model-written summary. Like :meth:`replace_prefix`, the durable
        stream is append-only and keeps the originals, and the recording hook
        is deliberately not invoked.
        """
        self._entries[index] = entry

    def snapshot(self) -> tuple[HistoryEntry, ...]:
        """A point-in-time view that cannot mutate internal state (FR-006)."""
        return tuple(self._entries)

    def rollback_to(self, length: int) -> None:
        """Drop in-memory entries appended after the given length (FR-007);
        the durable stream is append-only, and resume applies the same
        pruning rule when it rebuilds.
        """
        del self._entries[length:]

    def has_assistant_entry_since(self, length: int) -> bool:
        return any(entry.role == "assistant" for entry in self._entries[length:])
