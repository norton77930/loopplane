"""US1: begin each run with the loop's prior conversation (spec US1; SC-001/002/003)."""

from __future__ import annotations

from loopplane.engineering import StaticInput
from loopplane.recall import RetrievalBudget, build_recall_input, conversation_recall
from tests.recall_helpers import run_ref, scripted_state


def test_conversation_recall_is_most_recent_first() -> None:
    state = scripted_state(run_refs=[run_ref("s1", "done-1"), run_ref("s2", "done-2")])
    entries = conversation_recall()(state)
    assert [e.identifier for e in entries] == ["s2", "s1"]
    assert all(e.origin == "conversation" for e in entries)
    assert "s2" in entries[0].text and "done-2" in entries[0].text


def test_conversation_recall_injected_ahead_of_base_input() -> None:
    state = scripted_state(run_refs=[run_ref("s1"), run_ref("s2")])
    recall_input = build_recall_input(
        StaticInput("continue the task"),
        [conversation_recall()],
        RetrievalBudget(),
        state=state,
    )
    prompt = recall_input.initial()
    assert isinstance(prompt, str)
    assert "s1" in prompt and "s2" in prompt
    assert prompt.endswith("continue the task")


def test_conversation_recall_empty_runs_leaves_base_unchanged() -> None:
    recall_input = build_recall_input(
        StaticInput("fresh start"),
        [conversation_recall()],
        RetrievalBudget(),
        state=scripted_state(run_refs=[]),
    )
    assert recall_input.initial() == "fresh start"


def test_conversation_recall_is_deterministic() -> None:
    state = scripted_state(run_refs=[run_ref("s1"), run_ref("s2")])
    recall_input = build_recall_input(
        StaticInput("X"), [conversation_recall()], RetrievalBudget(), state=state
    )
    assert recall_input.initial() == recall_input.initial()


def test_conversation_recall_is_loop_scoped() -> None:
    state = scripted_state(loop_id="A", run_refs=[run_ref("a1"), run_ref("a2")])
    entries = conversation_recall()(state)
    # Only this state's runs are recalled; no other loop's runs can appear.
    assert {e.identifier for e in entries} == {"a1", "a2"}


def test_conversation_recall_respects_limit() -> None:
    state = scripted_state(run_refs=[run_ref(f"s{i}") for i in range(5)])
    entries = conversation_recall(limit=2)(state)
    assert [e.identifier for e in entries] == ["s4", "s3"]


def test_conversation_recall_does_not_mutate_state() -> None:
    state = scripted_state(run_refs=[run_ref("s1")])
    before = state.run_refs
    conversation_recall()(state)
    assert state.run_refs == before
