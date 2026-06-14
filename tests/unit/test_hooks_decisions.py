"""Unit tests for the gating decision types (T003; FR-006, FR-007)."""

from __future__ import annotations

import dataclasses

import pytest

from loopplane.hooks import (
    PromptAnnotate,
    PromptBlock,
    ToolGateDeny,
    ToolGateModify,
)


def test_tool_decisions_carry_their_fields() -> None:
    assert ToolGateDeny(reason="blocked").reason == "blocked"
    assert ToolGateModify(input={"a": 1}).input == {"a": 1}


def test_prompt_decisions_carry_their_fields() -> None:
    assert PromptBlock(reason="no").reason == "no"
    assert PromptAnnotate(text="context").text == "context"


def test_decisions_are_frozen() -> None:
    deny = ToolGateDeny(reason="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        deny.reason = "y"  # type: ignore[misc]
