"""US5: knowledge-index contract + in-memory reference (spec US5; SC-005)."""

from __future__ import annotations

from loopplane.recall import InMemoryKnowledgeIndex, KnowledgeEntry, knowledge_recall
from tests.recall_helpers import ScriptedKnowledgeIndex, scripted_state


def test_in_memory_index_lookup_matches_and_bounds() -> None:
    index = InMemoryKnowledgeIndex(
        [
            KnowledgeEntry("k1", "auth tokens and sessions"),
            KnowledgeEntry("k2", "database indexing"),
            KnowledgeEntry("k3", "auth retry policy"),
        ]
    )
    assert [e.identifier for e in index.lookup("auth", limit=5)] == ["k1", "k3"]
    assert len(index.lookup("auth", limit=1)) == 1


def test_knowledge_recall_adapts_results() -> None:
    index = InMemoryKnowledgeIndex([KnowledgeEntry("k1", "auth tokens")])
    entry = knowledge_recall(index)(scripted_state(loop_id="auth"))[0]
    assert entry.origin == "knowledge"
    assert entry.identifier == "k1"
    assert "auth tokens" in entry.text


def test_knowledge_recall_is_deterministic() -> None:
    source = knowledge_recall(InMemoryKnowledgeIndex([KnowledgeEntry("k1", "auth")]))
    state = scripted_state(loop_id="auth")
    assert source(state) == source(state)


def test_knowledge_recall_raising_index_is_fail_safe() -> None:
    index = ScriptedKnowledgeIndex(raising=True)
    assert knowledge_recall(index)(scripted_state(loop_id="x")) == ()


def test_knowledge_recall_empty_index_is_empty() -> None:
    assert knowledge_recall(InMemoryKnowledgeIndex())(scripted_state(loop_id="x")) == ()
