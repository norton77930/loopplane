"""Memory: durable knowledge entries reaching the model only through prompt
assembly (contracts/memory.md).
"""

from loopplane.memory.provider import MemoryAugmentation, MemorySnapshotAugmentation
from loopplane.memory.selection import select_entries
from loopplane.memory.store import MemoryEntry, MemoryStore

__all__ = [
    "MemoryAugmentation",
    "MemoryEntry",
    "MemorySnapshotAugmentation",
    "MemoryStore",
    "select_entries",
]
