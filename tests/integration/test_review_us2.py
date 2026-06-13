"""US2: pause, inspect, and resume a review out of band (spec US2; SC-004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import run_loop
from loopplane.review import (
    ReviewDecision,
    build_review_resolver,
    inspect_paused,
    resume_review,
)
from tests.review_helpers import const_reviewer, needs_review_definition

pytestmark = pytest.mark.anyio


async def test_no_resolver_pauses_and_inspect_returns_request(tmp_path: Path) -> None:
    outcome = await run_loop(needs_review_definition(working_scope=tmp_path))
    assert outcome.paused

    request = inspect_paused(outcome)
    assert request is not None
    assert request.cause == "validator_status"
    assert request.validation_reason == "please review"


async def test_inspect_paused_on_terminal_returns_none(tmp_path: Path) -> None:
    gate = build_review_resolver(const_reviewer("approve"))
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    assert not outcome.paused
    assert inspect_paused(outcome) is None


async def test_resume_with_approve_completes(tmp_path: Path) -> None:
    outcome = await resume_review(
        needs_review_definition(working_scope=tmp_path),
        ReviewDecision(outcome="approve", reason="ok"),
    )
    assert outcome.terminal_event == "loop_completed"


async def test_resume_with_reject_fails(tmp_path: Path) -> None:
    outcome = await resume_review(
        needs_review_definition(working_scope=tmp_path),
        ReviewDecision(outcome="reject", reason="no"),
    )
    assert outcome.terminal_event == "loop_failed"
    assert outcome.stop_reason == "no"
