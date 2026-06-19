"""Contract tests for runtime events (contracts/runtime-events.md).

Asserts the envelope shape, the closed vocabulary, lossless serde round-trip
(FR-064), unknown-type tolerance (FR-063), and monotonic gap-free sequencing
(FR-060).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import get_args

from loopplane.errors import ErrorCategory, NormalizedError
from loopplane.events import (
    SCHEMA_VERSION,
    ApprovalRequestedEvent,
    ApprovalResolvedEvent,
    AssistantOutputIncrementEvent,
    AssistantReasoningIncrementEvent,
    DiagnosticEvent,
    EventSequencer,
    QuestionAnsweredEvent,
    QuestionAskedEvent,
    ReplayCompletedEvent,
    ReplayStartedEvent,
    RunTerminatedEvent,
    RuntimeEvent,
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
    TurnCompletedEvent,
    UserInputEvent,
    deserialize_event,
    serialize_event,
)
from loopplane.events.envelope import RUNTIME_EVENT_TYPES
from loopplane.model.boundary import TokenUsage
from loopplane.model.content import ImageBlock, TextBlock

EXPECTED_VOCABULARY = {
    "user-input",
    "assistant-output-increment",
    "assistant-reasoning-increment",
    "turn-completed",
    "tool-call-started",
    "tool-call-completed",
    "approval-requested",
    "approval-resolved",
    "question-asked",
    "question-answered",
    "replay-started",
    "replay-completed",
    "diagnostic",
    "run-terminated",
}

ENVELOPE_FIELDS = {
    "type",
    "schema_version",
    "session_id",
    "sequence",
    "occurred_at",
    "replay",
    "payload",
}


def _envelope(sequence: int) -> dict[str, object]:
    return {
        "session_id": "session-1",
        "sequence": sequence,
        "occurred_at": datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC),
        "replay": False,
    }


def _sample_events() -> list[RuntimeEvent]:
    """One instance of every event type in the vocabulary."""
    usage = TokenUsage(
        input_tokens=10, output_tokens=5, cached_tokens=2, reasoning_tokens=1
    )
    return [
        UserInputEvent(
            **_envelope(1),
            payload={"blocks": [TextBlock(text="hello")]},
        ),
        AssistantOutputIncrementEvent(
            **_envelope(2),
            payload={"text": "hi there", "turn_index": 0},
        ),
        AssistantReasoningIncrementEvent(
            **_envelope(3),
            payload={"text": "thinking...", "turn_index": 0},
        ),
        TurnCompletedEvent(
            **_envelope(4),
            payload={"turn_index": 0, "stop_reason": "end-turn", "usage": usage},
        ),
        ToolCallStartedEvent(
            **_envelope(5),
            payload={"call_id": "call-1", "tool_name": "echo", "input": {"text": "x"}},
        ),
        ToolCallCompletedEvent(
            **_envelope(6),
            payload={
                "call_id": "call-1",
                "outcome": "failure",
                "outputs": [TextBlock(text="partial")],
                "artifact_reference": None,
                "error": NormalizedError(
                    category=ErrorCategory.TIMEOUT, reason="too slow"
                ),
                "duration_seconds": 1.5,
            },
        ),
        ApprovalRequestedEvent(
            **_envelope(7),
            payload={
                "request_id": "req-1",
                "call_id": "call-2",
                "tool_name": "write_file",
                "input_summary": "write to notes.txt",
            },
        ),
        ApprovalResolvedEvent(
            **_envelope(8),
            payload={
                "request_id": "req-1",
                "decision": "deny",
                "scope": "once",
                "resolution_source": "reviewer",
            },
        ),
        QuestionAskedEvent(
            **_envelope(9),
            payload={
                "request_id": "req-2",
                "questions": [{"text": "Which path?", "options": ["a", "b"]}],
            },
        ),
        QuestionAnsweredEvent(
            **_envelope(10),
            payload={"request_id": "req-2", "answers": ["a"]},
        ),
        ReplayStartedEvent(**_envelope(11), payload={"count": 10}),
        ReplayCompletedEvent(**_envelope(12), payload={"count": 10}),
        DiagnosticEvent(
            **_envelope(13),
            payload={
                "severity": "warning",
                "category": "checkpoint",
                "message": "skipped one corrupt record",
            },
        ),
        RunTerminatedEvent(
            **_envelope(14),
            payload={"reason": "natural-completion", "turns_taken": 3},
        ),
    ]


def test_vocabulary_is_closed() -> None:
    assert set(RUNTIME_EVENT_TYPES) == EXPECTED_VOCABULARY
    sample_types = {event.type for event in _sample_events()}
    assert sample_types == EXPECTED_VOCABULARY


def test_every_event_carries_the_envelope() -> None:
    for event in _sample_events():
        dumped = event.model_dump()
        missing = ENVELOPE_FIELDS - dumped.keys()
        assert not missing, f"{event.type} missing envelope fields: {missing}"
        assert dumped["schema_version"] == SCHEMA_VERSION
        assert dumped["session_id"] == "session-1"
        assert isinstance(dumped["sequence"], int)
        assert dumped["replay"] is False


def test_serde_round_trip_is_lossless() -> None:
    for event in _sample_events():
        serialized = serialize_event(event)
        restored = deserialize_event(serialized)
        assert restored == event, f"round trip changed a {event.type} event"


def test_user_input_with_an_image_block_round_trips() -> None:
    # 036: image input reaches the model via the existing UserInputEvent.blocks,
    # with NO schema change. A content-block change MUST be tested (Constitution
    # VI): assert an ImageBlock-bearing user-input event is lossless and that the
    # schema version is unchanged.
    event = UserInputEvent(
        **_envelope(1),
        payload={
            "blocks": [
                ImageBlock(media="aGVsbG8=", format="image/png"),
                TextBlock(text="what is in this image?"),
            ]
        },
    )
    restored = deserialize_event(serialize_event(event))
    assert restored == event
    document = json.loads(serialize_event(event))
    assert document["schema_version"] == SCHEMA_VERSION
    image = document["payload"]["blocks"][0]
    assert image["kind"] == "image"
    assert image["format"] == "image/png"
    assert image["media"] == "aGVsbG8="


def test_serialized_form_is_self_describing() -> None:
    for event in _sample_events():
        document = json.loads(serialize_event(event))
        assert document["type"] == event.type
        assert document["schema_version"] == SCHEMA_VERSION


def test_unknown_event_type_is_skipped() -> None:
    known = serialize_event(_sample_events()[0])
    document = json.loads(known)
    document["type"] = "from-a-future-version"
    assert deserialize_event(json.dumps(document)) is None


def test_corrupt_input_is_skipped_not_raised() -> None:
    assert deserialize_event("this is not json") is None
    assert deserialize_event('{"no_type": true}') is None


def test_sequencer_is_monotonic_and_gap_free() -> None:
    sequencer = EventSequencer()
    sequences = [sequencer.next_sequence() for _ in range(100)]
    assert sequences == list(range(sequences[0], sequences[0] + 100))


def test_vocabulary_constant_matches_union() -> None:
    union_types = {
        get_args(member.model_fields["type"].annotation)[0]
        for member in get_args(get_args(RuntimeEvent)[0])
    }
    assert union_types == EXPECTED_VOCABULARY
