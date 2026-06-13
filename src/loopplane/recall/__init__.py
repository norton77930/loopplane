"""LoopPlane Memory Recall & Knowledge layer (feature
007-loopplane-memory-recall-knowledge).

Deterministic, public-safe, loop-aware recalled context composed over the public
Phase-1 (``loopplane.memory``, ``loopplane.artifacts``) and Phase-3
(``loopplane.engineering``) surfaces and injected through a Phase-3
``InputSource``. The layer reads only those public surfaces, mutates nothing,
and starts no Loop Run (contracts/injection-boundary.md).
"""

from loopplane.recall.budget import BudgetResult, RetrievalBudget, apply_budget
from loopplane.recall.entry import (
    QueryFn,
    RecalledEntry,
    RecallSource,
    default_query,
)
from loopplane.recall.injection import (
    RecallAssembly,
    assemble_recall,
    build_recall_input,
)

__all__ = [
    "BudgetResult",
    "QueryFn",
    "RecallAssembly",
    "RecallSource",
    "RecalledEntry",
    "RetrievalBudget",
    "apply_budget",
    "assemble_recall",
    "build_recall_input",
    "default_query",
]
