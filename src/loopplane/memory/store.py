"""The memory store: durable knowledge entries independent of any session
(contracts/memory.md; FR-070, FR-071).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError


class MemoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str = "reference"
    name: str
    description: str
    body: str = ""


class MemoryStore:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def scan(self) -> tuple[list[MemoryEntry], list[str]]:
        """Discover entries; a malformed entry is skipped and reported,
        never failing the run (FR-071).
        """
        if not self._base.is_dir():
            return [], []
        entries: list[MemoryEntry] = []
        problems: list[str] = []
        for path in sorted(self._base.glob("*.json")):
            try:
                entries.append(MemoryEntry.model_validate_json(path.read_bytes()))
            except (ValidationError, OSError) as exc:
                problems.append(
                    f"memory entry {path.name} is malformed and was skipped: "
                    f"{type(exc).__name__}"
                )
        return entries, problems

    def list_entries(self) -> list[MemoryEntry]:
        entries, _ = self.scan()
        return entries

    def get(self, name: str) -> MemoryEntry | None:
        for entry in self.list_entries():
            if entry.name == name:
                return entry
        return None

    def write(self, entry: MemoryEntry) -> None:
        """Create or update an entry, idempotent by name; immediately
        visible to subsequent scans.
        """
        self._base.mkdir(parents=True, exist_ok=True)
        path = self._base / self._filename(entry.name)
        path.write_text(entry.model_dump_json(), encoding="utf-8")

    def delete(self, name: str) -> bool:
        path = self._base / self._filename(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    @staticmethod
    def _filename(name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        return f"{safe}-{suffix}.json"
