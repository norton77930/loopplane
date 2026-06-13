"""LoopPlane Memory Recall & Knowledge layer (feature
007-loopplane-memory-recall-knowledge).

Deterministic, public-safe, loop-aware recalled context composed over the public
Phase-1 (``loopplane.memory``, ``loopplane.artifacts``) and Phase-3
(``loopplane.engineering``) surfaces and injected through a Phase-3
``InputSource``. The layer reads only those public surfaces, mutates nothing,
and starts no Loop Run (contracts/injection-boundary.md).
"""

from loopplane.recall.artifacts import ArtifactReader, artifact_recall
from loopplane.recall.budget import BudgetResult, RetrievalBudget, apply_budget
from loopplane.recall.conversation import conversation_recall
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
from loopplane.recall.knowledge import (
    InMemoryKnowledgeIndex,
    KnowledgeEntry,
    KnowledgeIndex,
    knowledge_recall,
)
from loopplane.recall.memory import memory_entry_recall

__all__ = [
    "ArtifactReader",
    "BudgetResult",
    "InMemoryKnowledgeIndex",
    "KnowledgeEntry",
    "KnowledgeIndex",
    "QueryFn",
    "RecallAssembly",
    "RecallSource",
    "RecalledEntry",
    "RetrievalBudget",
    "apply_budget",
    "artifact_recall",
    "assemble_recall",
    "build_recall_input",
    "conversation_recall",
    "default_query",
    "knowledge_recall",
    "memory_entry_recall",
]
