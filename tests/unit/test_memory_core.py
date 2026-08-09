"""Direct unit coverage for MemoryStore CRUD branches (T034)."""

from __future__ import annotations

from pathlib import Path

from loopplane.memory import MemoryEntry, MemoryStore


def _entry(name: str) -> MemoryEntry:
    return MemoryEntry(
        type="project",
        name=name,
        description="deployment guidance",
        body="use the verified deployment path",
    )


def test_get_and_delete_cover_present_and_missing_entries(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    entry = _entry("deployment-notes")
    store.write(entry)

    assert store.get("deployment-notes") == entry
    assert store.get("missing") is None
    assert store.delete("deployment-notes") is True
    assert store.get("deployment-notes") is None
    assert store.delete("deployment-notes") is False
