"""Deterministic relevance selection (FR-072; research A5): normalized token
overlap between the prompt and an entry's name/description, with stable
tie-breaking by type priority then name; no signal falls back to
deterministic type-priority ordering.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from loopplane.memory.store import MemoryEntry

_TYPE_PRIORITY = {"user": 0, "project": 1, "reference": 2, "feedback": 3}
_UNLISTED_PRIORITY = len(_TYPE_PRIORITY)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _priority(entry: MemoryEntry) -> int:
    return _TYPE_PRIORITY.get(entry.type, _UNLISTED_PRIORITY)


def select_entries(
    entries: Sequence[MemoryEntry], prompt: str, *, limit: int = 5
) -> list[MemoryEntry]:
    prompt_tokens = _tokens(prompt)

    def relevance(entry: MemoryEntry) -> int:
        return len(prompt_tokens & _tokens(f"{entry.name} {entry.description}"))

    scored = [(relevance(entry), entry) for entry in entries]
    if all(score == 0 for score, _ in scored):
        ordered = sorted(entries, key=lambda entry: (_priority(entry), entry.name))
    else:
        ordered = [
            entry
            for _, entry in sorted(
                scored,
                key=lambda pair: (-pair[0], _priority(pair[1]), pair[1].name),
            )
        ]
    return ordered[:limit]
