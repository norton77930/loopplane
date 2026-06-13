"""US3: recall durable memory entries via the existing selection (spec US3; SC-002)."""

from __future__ import annotations

from loopplane.memory import select_entries
from loopplane.recall import default_query, memory_entry_recall
from tests.recall_helpers import memory_entry, scripted_state


def test_memory_entry_recall_matches_phase1_selection() -> None:
    entries = [
        memory_entry("auth", "authentication helper"),
        memory_entry("db", "database layer"),
        memory_entry("cache", "caching"),
    ]
    state = scripted_state(loop_id="auth", validation_reason="fix auth bug")
    recalled = memory_entry_recall(entries, limit=2)(state)
    expected = select_entries(entries, default_query(state), limit=2)
    assert [e.identifier for e in recalled] == [m.name for m in expected]
    assert all(e.origin == "memory" for e in recalled)


def test_memory_entry_recall_is_deterministic() -> None:
    entries = [memory_entry("a", "alpha"), memory_entry("b", "beta")]
    source = memory_entry_recall(entries)
    state = scripted_state()
    assert source(state) == source(state)


def test_memory_entry_recall_empty_entries_is_empty() -> None:
    assert memory_entry_recall([])(scripted_state()) == ()


def test_memory_entry_recall_text_includes_entry_content() -> None:
    entries = [memory_entry("auth", "authentication", body="use tokens")]
    text = memory_entry_recall(entries)(scripted_state(loop_id="auth"))[0].text
    assert "auth" in text and "authentication" in text and "use tokens" in text


def test_memory_entry_recall_does_not_mutate_entries() -> None:
    entries = [memory_entry("a", "alpha")]
    before = list(entries)
    memory_entry_recall(entries)(scripted_state())
    assert entries == before
