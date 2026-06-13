"""US4: ask the human review questions before deciding (spec US4; SC-006/009)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import run_loop
from loopplane.review import build_review_resolver
from tests.review_helpers import (
    AskingReviewer,
    ReviewEventRecorder,
    needs_review_definition,
    raising_asker,
    scripted_asker,
)

pytestmark = pytest.mark.anyio


async def test_reviewer_asks_and_decides_on_the_answer(tmp_path: Path) -> None:
    reviewer = AskingReviewer("approve?", approve_if="yes")
    gate = build_review_resolver(reviewer, asker=scripted_asker("yes"))

    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )

    assert reviewer.answer == "yes"
    assert outcome.terminal_event == "loop_completed"


async def test_question_events_in_order(tmp_path: Path) -> None:
    recorder = ReviewEventRecorder()
    reviewer = AskingReviewer("approve?", approve_if="yes")
    gate = build_review_resolver(
        reviewer, asker=scripted_asker("yes"), on_event=recorder
    )

    await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )

    types = recorder.types
    assert types.index("review_question_asked") < types.index(
        "review_question_answered"
    )


async def test_no_asker_fails_safe(tmp_path: Path) -> None:
    # The reviewer asks but no asker is configured: ask raises ReviewError, which
    # the gate fail-safes to a non-approval — never a silent hang.
    reviewer = AskingReviewer("approve?", approve_if="yes")
    gate = build_review_resolver(reviewer)

    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )

    assert outcome.terminal_event == "loop_failed"


async def test_raising_asker_is_non_fatal(tmp_path: Path) -> None:
    reviewer = AskingReviewer("approve?", approve_if="yes")
    gate = build_review_resolver(reviewer, asker=raising_asker())

    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )

    # asker raised -> ask returned [] -> answer None -> reject (no crash)
    assert reviewer.answer is None
    assert outcome.terminal_event == "loop_failed"
