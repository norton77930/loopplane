"""US4: compose sources and inject within a retrieval budget (spec US4; SC-004/009)."""

from __future__ import annotations

from loopplane.engineering import StaticInput
from loopplane.recall import (
    RecalledEntry,
    RetrievalBudget,
    artifact_recall,
    assemble_recall,
    build_recall_input,
    conversation_recall,
    memory_entry_recall,
)
from tests.recall_helpers import (
    ScriptedArtifactReader,
    artifact_meta,
    artifact_ref,
    memory_entry,
    run_ref,
    scripted_state,
)


def _src(*entries: RecalledEntry) -> object:
    def source(state: object) -> tuple[RecalledEntry, ...]:
        return tuple(entries)

    return source


def test_compose_dedupes_by_source_precedence() -> None:
    source_a = _src(RecalledEntry("from-A", "o", "x"))
    source_b = _src(
        RecalledEntry("from-B", "o", "x"), RecalledEntry("only-B", "o", "y")
    )
    assembly = assemble_recall(
        [source_a, source_b], RetrievalBudget(), state=scripted_state()
    )
    # A's "x" wins (highest precedence); B's duplicate "x" is dropped; "y" kept.
    assert [e.text for e in assembly.entries] == ["from-A", "only-B"]


def test_compose_keeps_all_none_identifier_entries() -> None:
    assembly = assemble_recall(
        [_src(RecalledEntry("a1", "o", None)), _src(RecalledEntry("b1", "o", None))],
        RetrievalBudget(),
        state=scripted_state(),
    )
    assert [e.text for e in assembly.entries] == ["a1", "b1"]


def test_compose_budget_truncates_with_dropped_count() -> None:
    source = _src(*[RecalledEntry(f"e{i}", "o", str(i)) for i in range(5)])
    assembly = assemble_recall(
        [source], RetrievalBudget(max_entries=2), state=scripted_state()
    )
    assert len(assembly.entries) == 2
    assert assembly.dropped == 3


def test_compose_real_sources_follow_source_order() -> None:
    state = scripted_state(
        loop_id="auth",
        run_refs=[run_ref("s1")],
        artifacts=[artifact_ref("s1", "a1")],
    )
    reader = ScriptedArtifactReader([artifact_meta("s1", "a1", day=1)])
    sources = [
        conversation_recall(),
        artifact_recall(reader),
        memory_entry_recall([memory_entry("auth", "authentication")]),
    ]
    origins = [
        e.origin
        for e in assemble_recall(sources, RetrievalBudget(), state=state).entries
    ]
    assert {"conversation", "artifact", "memory"} <= set(origins)
    assert (
        origins.index("conversation")
        < origins.index("artifact")
        < origins.index("memory")
    )


def test_compose_budget_bounds_entry_text_and_surfaces_dropped() -> None:
    state = scripted_state(run_refs=[run_ref(f"sess{i}") for i in range(10)])
    assembly = assemble_recall(
        [conversation_recall()], RetrievalBudget(max_chars=80), state=state
    )
    assert sum(len(e.text) for e in assembly.entries) <= 80
    assert assembly.dropped >= 1


def test_empty_union_leaves_base_unchanged() -> None:
    recall_input = build_recall_input(
        StaticInput("base only"),
        [conversation_recall(), artifact_recall(ScriptedArtifactReader())],
        RetrievalBudget(),
        state=scripted_state(),
    )
    assert recall_input.initial() == "base only"
