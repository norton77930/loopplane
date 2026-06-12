"""Session history with immutable point-in-time snapshots (FR-006, FR-007)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

from loopplane.model.content import ContentBlock


class HistoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    blocks: tuple[ContentBlock, ...]
    recorded_at: AwareDatetime


class SessionHistory:
    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    def append(
        self, role: Literal["user", "assistant"], blocks: Sequence[ContentBlock]
    ) -> None:
        self._entries.append(
            HistoryEntry(role=role, blocks=tuple(blocks), recorded_at=datetime.now(UTC))
        )

    def snapshot(self) -> tuple[HistoryEntry, ...]:
        """A point-in-time view that cannot mutate internal state (FR-006)."""
        return tuple(self._entries)

    def rollback_to(self, length: int) -> None:
        """Drop entries appended after the given length (FR-007)."""
        del self._entries[length:]

    def has_assistant_entry_since(self, length: int) -> bool:
        return any(entry.role == "assistant" for entry in self._entries[length:])
