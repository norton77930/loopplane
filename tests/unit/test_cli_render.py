"""Unit tests for the CLI event renderer (T002; FR-004, FR-009)."""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest

from loopplane.cli import EventRenderer
from loopplane.events.envelope import (
    AssistantOutputIncrementEvent,
    AssistantOutputIncrementPayload,
    RunTerminatedEvent,
    RunTerminatedPayload,
    ToolCallCompletedEvent,
    ToolCallCompletedPayload,
    ToolCallStartedEvent,
    ToolCallStartedPayload,
)

pytestmark = pytest.mark.anyio

_T = datetime(2026, 1, 1, tzinfo=UTC)


async def test_renders_assistant_output_and_termination() -> None:
    out = io.StringIO()
    render = EventRenderer(out)
    await render(
        AssistantOutputIncrementEvent(
            session_id="s",
            sequence=1,
            occurred_at=_T,
            payload=AssistantOutputIncrementPayload(text="hello", turn_index=0),
        )
    )
    await render(
        RunTerminatedEvent(
            session_id="s",
            sequence=2,
            occurred_at=_T,
            payload=RunTerminatedPayload(reason="natural-completion", turns_taken=1),
        )
    )
    text = out.getvalue()
    assert "hello" in text
    assert "[run natural-completion, 1 turn(s)]" in text


async def test_renders_tool_metadata_not_raw_input() -> None:
    out = io.StringIO()
    render = EventRenderer(out)
    await render(
        ToolCallStartedEvent(
            session_id="s",
            sequence=1,
            occurred_at=_T,
            payload=ToolCallStartedPayload(
                call_id="c1", tool_name="echo", input={"secret": "xyz"}
            ),
        )
    )
    await render(
        ToolCallCompletedEvent(
            session_id="s",
            sequence=2,
            occurred_at=_T,
            payload=ToolCallCompletedPayload(
                call_id="c1", outcome="success", duration_seconds=0.0
            ),
        )
    )
    text = out.getvalue()
    assert "echo" in text
    assert "success" in text
    assert "xyz" not in text  # raw tool input is never rendered


# --- 079: approval and question rendering (T016) -----------------------------


async def test_renders_an_approval_request_with_only_what_is_needed() -> None:
    from loopplane.events.envelope import (
        ApprovalRequestedEvent,
        ApprovalRequestedPayload,
    )

    out = io.StringIO()
    render = EventRenderer(out)
    await render(
        ApprovalRequestedEvent(
            session_id="s",
            sequence=1,
            occurred_at=_T,
            payload=ApprovalRequestedPayload(
                request_id="r1",
                call_id="c1",
                tool_name="write_file",
                input_summary="1 field",
            ),
        )
    )
    text = out.getvalue()
    assert "[approve] write_file" in text
    assert "1 field" in text
    assert "y/n/a/never" in text  # the answer legend is shown
    assert "r1" not in text  # the request id is machinery, not operator detail
    assert "c1" not in text


async def test_renders_a_question_with_its_options() -> None:
    from loopplane.events.envelope import (
        Question,
        QuestionAskedEvent,
        QuestionAskedPayload,
    )

    out = io.StringIO()
    render = EventRenderer(out)
    await render(
        QuestionAskedEvent(
            session_id="s",
            sequence=1,
            occurred_at=_T,
            payload=QuestionAskedPayload(
                request_id="r2",
                questions=[Question(text="which one?", options=["left", "right"])],
            ),
        )
    )
    text = out.getvalue()
    assert "[question] which one?" in text
    assert "- left" in text and "- right" in text
    assert "r2" not in text
