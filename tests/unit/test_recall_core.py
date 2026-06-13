"""Foundational unit tests for the recall layer (007): the recalled-entry value
type, the retrieval budget, source composition, and the injection seam. Host-free.
"""

from __future__ import annotations

from loopplane.engineering import StaticInput
from loopplane.recall import (
    RecalledEntry,
    RetrievalBudget,
    apply_budget,
    assemble_recall,
    build_recall_input,
)
from tests.recall_helpers import artifact_ref, run_ref, scripted_state


def _src(*entries: RecalledEntry) -> object:
    def source(state: object) -> tuple[RecalledEntry, ...]:
        return tuple(entries)

    return source


def _boom(state: object) -> tuple[RecalledEntry, ...]:
    raise RuntimeError("source boom")


class _ListInput:
    def __init__(self, blocks: list[str]) -> None:
        self._blocks = blocks

    def initial(self) -> list[str]:
        return self._blocks


def test_recalled_entry_shape() -> None:
    entry = RecalledEntry("hi", "conversation", "s1")
    assert (entry.text, entry.origin, entry.identifier) == ("hi", "conversation", "s1")
    assert RecalledEntry("x", "origin").identifier is None


def test_apply_budget_caps_entries_with_dropped_count() -> None:
    entries = [RecalledEntry(f"e{i}", "o", str(i)) for i in range(5)]
    result = apply_budget(entries, RetrievalBudget(max_entries=2))
    assert [e.text for e in result.kept] == ["e0", "e1"]
    assert result.dropped == 3


def test_apply_budget_caps_characters_order_stable() -> None:
    entries = [
        RecalledEntry("aaa", "o"),
        RecalledEntry("bbb", "o"),
        RecalledEntry("ccc", "o"),
    ]
    result = apply_budget(entries, RetrievalBudget(max_chars=6))
    assert [e.text for e in result.kept] == ["aaa", "bbb"]
    assert result.dropped == 1


def test_apply_budget_none_is_unbounded() -> None:
    entries = [RecalledEntry("e", "o") for _ in range(4)]
    result = apply_budget(entries, RetrievalBudget())
    assert len(result.kept) == 4
    assert result.dropped == 0


def test_assemble_recall_concatenates_in_source_order() -> None:
    assembly = assemble_recall(
        [_src(RecalledEntry("a", "x", "1")), _src(RecalledEntry("b", "y", "2"))],
        RetrievalBudget(),
        state=scripted_state(),
    )
    assert [e.text for e in assembly.entries] == ["a", "b"]
    assert assembly.skipped == ()


def test_assemble_recall_skips_a_raising_source() -> None:
    assembly = assemble_recall(
        [_boom, _src(RecalledEntry("a", "x", "1"))],
        RetrievalBudget(),
        state=scripted_state(),
    )
    # The raising source contributes nothing; the next source still recalls.
    assert [e.text for e in assembly.entries] == ["a"]
    assert assembly.skipped == ("source[0]",)


def test_build_recall_input_prepends_preamble_to_string_base() -> None:
    recall_input = build_recall_input(
        StaticInput("do the task"),
        [_src(RecalledEntry("recalled-fact", "x", "1"))],
        RetrievalBudget(),
        state=scripted_state(),
    )
    prompt = recall_input.initial()
    assert isinstance(prompt, str)
    assert "[recalled context]" in prompt
    assert "recalled-fact" in prompt
    assert prompt.endswith("do the task")


def test_build_recall_input_empty_recall_returns_base_unchanged() -> None:
    recall_input = build_recall_input(
        StaticInput("base only"), [_src()], RetrievalBudget(), state=scripted_state()
    )
    assert recall_input.initial() == "base only"


def test_build_recall_input_passes_non_string_prompt_through() -> None:
    blocks = ["block-a", "block-b"]
    recall_input = build_recall_input(
        _ListInput(blocks),
        [_src(RecalledEntry("x", "o", "1"))],
        RetrievalBudget(),
        state=scripted_state(),
    )
    # A non-string base prompt is passed through unchanged this phase.
    assert recall_input.initial() == blocks


def test_recall_does_not_mutate_state() -> None:
    state = scripted_state(
        run_refs=[run_ref("s1")], artifacts=[artifact_ref("s1", "a1")]
    )
    before = (state.loop_id, state.run_refs, state.artifacts, state.iteration_index)
    assemble_recall(
        [_src(RecalledEntry("x", "o", "1"))],
        RetrievalBudget(max_entries=1),
        state=state,
    )
    assert (
        state.loop_id,
        state.run_refs,
        state.artifacts,
        state.iteration_index,
    ) == before
