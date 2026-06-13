"""The Agent Loop: turn cycle, partitioning, assembly, compaction, and
session history.
"""

from loopplane.loop.assembly import AugmentationProvider, PromptAssembler
from loopplane.loop.compaction import DEFAULT_KEEP_LAST, compact_history
from loopplane.loop.history import HistoryEntry, SessionHistory
from loopplane.loop.loop import AgentLoop, partition_calls

__all__ = [
    "DEFAULT_KEEP_LAST",
    "AgentLoop",
    "AugmentationProvider",
    "HistoryEntry",
    "PromptAssembler",
    "SessionHistory",
    "compact_history",
    "partition_calls",
]
