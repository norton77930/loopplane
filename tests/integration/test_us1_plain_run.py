"""US1 acceptance 1.1: plain-text run golden event sequence and recorded
history (FR-001, FR-002).
"""

from __future__ import annotations

import pytest

from loopplane.model import ScriptedTurn, TextBlock, TextIncrement, TokenUsage

from .conftest import EventCollector, HarnessFactory

pytestmark = pytest.mark.anyio


async def test_plain_text_run_golden_event_sequence(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(
            increments=[TextIncrement(text="Hello"), TextIncrement(text=" world")],
            stop_reason="end-turn",
            usage=TokenUsage(input_tokens=3, output_tokens=2),
        )
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="hi there")])

    assert collector.types == [
        "user-input",
        "assistant-output-increment",
        "assistant-output-increment",
        "turn-completed",
        "run-terminated",
    ]


async def test_plain_text_run_event_payloads(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(
            increments=[TextIncrement(text="Hello"), TextIncrement(text=" world")],
            stop_reason="end-turn",
            usage=TokenUsage(input_tokens=3, output_tokens=2),
        )
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="hi there")])

    user_input, first, second, turn_completed, terminated = collector.events
    assert user_input.type == "user-input"
    assert list(user_input.payload.blocks) == [TextBlock(text="hi there")]
    assert first.type == "assistant-output-increment"
    assert (first.payload.text, first.payload.turn_index) == ("Hello", 0)
    assert second.type == "assistant-output-increment"
    assert (second.payload.text, second.payload.turn_index) == (" world", 0)
    assert turn_completed.type == "turn-completed"
    assert turn_completed.payload.turn_index == 0
    assert turn_completed.payload.stop_reason == "end-turn"
    assert turn_completed.payload.usage == TokenUsage(input_tokens=3, output_tokens=2)
    assert terminated.type == "run-terminated"
    assert terminated.payload.reason == "natural-completion"
    assert terminated.payload.turns_taken == 1


async def test_event_envelopes_share_the_session_and_increase_gap_free(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(increments=[TextIncrement(text="Hello")]),
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="hi")])

    sequences = [event.sequence for event in collector.events]
    assert sequences == list(range(sequences[0], sequences[0] + len(sequences)))
    assert {event.session_id for event in collector.events} == {session_id}
    assert all(event.replay is False for event in collector.events)


async def test_recorded_history_contains_user_and_assistant_messages(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(
            increments=[TextIncrement(text="Hello"), TextIncrement(text=" world")],
        )
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="hi there")])

    history = controller.history_snapshot(session_id)
    assert [entry.role for entry in history] == ["user", "assistant"]
    assert history[0].blocks == (TextBlock(text="hi there"),)
    assert history[1].blocks == (TextBlock(text="Hello world"),)


async def test_history_persists_across_runs_in_one_session(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(increments=[TextIncrement(text="first answer")]),
        ScriptedTurn(increments=[TextIncrement(text="second answer")]),
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="one")])
    await controller.drive(session_id, [TextBlock(text="two")])

    history = controller.history_snapshot(session_id)
    assert [entry.role for entry in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert history[2].blocks == (TextBlock(text="two"),)
    terminal_count = sum(
        1 for event in collector.events if event.type == "run-terminated"
    )
    assert terminal_count == 2
