"""Foundational unit tests for the packs layer (feature 005): the outcome reader.

Host-free and synchronous. Pure-unit coverage of the validators/evaluators/
combinators lives in their own story phases.
"""

from __future__ import annotations

from loopplane.packs import OutcomeView, read_outcome, rule_validator
from tests.packs_helpers import scripted_outcome


def test_read_outcome_extracts_the_public_view() -> None:
    outcome, state = scripted_outcome(
        text="hello world", terminal="natural-completion", artifacts=("a/1", "a/2")
    )

    view = read_outcome(outcome, state)

    assert isinstance(view, OutcomeView)
    assert view.terminal_reason == "natural-completion"
    assert view.final_text == "hello world"
    assert view.artifact_references == ("a/1", "a/2")


def test_read_outcome_empty_text_when_no_assistant_entry() -> None:
    outcome, state = scripted_outcome(text="", terminal="cancelled")

    view = read_outcome(outcome, state)

    assert view.final_text == ""
    assert view.terminal_reason == "cancelled"
    assert view.artifact_references == ()


def test_read_outcome_uses_the_last_assistant_text() -> None:
    # Two assistant entries: the reader takes the last one (deterministic).
    from datetime import UTC, datetime

    from loopplane.host import RunOutcome
    from loopplane.loop.history import HistoryEntry
    from loopplane.model import TextBlock

    dt = datetime(2026, 1, 1, tzinfo=UTC)
    outcome = RunOutcome(
        session_id="s1",
        termination_reason="natural-completion",
        turns_taken=2,
        history=(
            HistoryEntry(
                role="assistant", blocks=(TextBlock(text="first"),), recorded_at=dt
            ),
            HistoryEntry(role="user", blocks=(TextBlock(text="mid"),), recorded_at=dt),
            HistoryEntry(
                role="assistant", blocks=(TextBlock(text="final"),), recorded_at=dt
            ),
        ),
    )
    _, state = scripted_outcome()

    assert read_outcome(outcome, state).final_text == "final"


def test_raising_rule_omits_exception_text_from_the_reason() -> None:
    material = "credential-" + "material-not-for-reason"

    def boom(view: OutcomeView) -> bool:
        raise RuntimeError(material)

    result = rule_validator(boom)(*scripted_outcome(text="x"))
    assert result.status == "fail"
    assert result.reason is not None
    assert material not in result.reason
    assert repr(RuntimeError(material)) not in result.reason
