"""Unit tests for lifecycle points and payloads (T002; FR-002, FR-015)."""

from __future__ import annotations

import dataclasses

import pytest

from loopplane.hooks import (
    BeforeToolUsePayload,
    LifecyclePoint,
    ModelStopPayload,
    UserPromptSubmitPayload,
    is_gating,
)


def test_there_are_eleven_points() -> None:
    assert len(list(LifecyclePoint)) == 11


def test_gating_classification() -> None:
    assert is_gating(LifecyclePoint.before_tool_use)
    assert is_gating(LifecyclePoint.user_prompt_submit)
    for point in LifecyclePoint:
        if point not in (
            LifecyclePoint.before_tool_use,
            LifecyclePoint.user_prompt_submit,
        ):
            assert not is_gating(point)


def test_payload_carries_its_fields() -> None:
    payload = BeforeToolUsePayload(
        session_id="s", call_id="c", tool_name="t", input={"a": 1}
    )
    assert payload.tool_name == "t"
    assert payload.input == {"a": 1}
    assert ModelStopPayload(session_id="s", turns_taken=3).turns_taken == 3


def test_payloads_are_frozen() -> None:
    payload = UserPromptSubmitPayload(session_id="s", text="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        payload.text = "changed"  # type: ignore[misc]
