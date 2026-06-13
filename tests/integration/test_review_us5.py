"""US5: observe review events and keep the edges honest (spec US5; SC-007/008)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import run_loop
from loopplane.review import build_review_resolver
from tests.review_helpers import (
    AskingReviewer,
    ReviewEventRecorder,
    const_reviewer,
    needs_review_definition,
    scripted_asker,
)

pytestmark = pytest.mark.anyio


async def test_review_event_stream_order(tmp_path: Path) -> None:
    recorder = ReviewEventRecorder()
    reviewer = AskingReviewer("ok?", approve_if="yes")
    gate = build_review_resolver(
        reviewer, asker=scripted_asker("yes"), on_event=recorder
    )

    await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )

    assert recorder.types == [
        "review_requested",
        "review_question_asked",
        "review_question_answered",
        "review_decided",
    ]


async def test_observation_off_matches_observation_on(tmp_path: Path) -> None:
    off = await run_loop(
        needs_review_definition(working_scope=tmp_path),
        review_resolver=build_review_resolver(const_reviewer("approve", reason="ok")),
    )

    recorder = ReviewEventRecorder()
    on = await run_loop(
        needs_review_definition(working_scope=tmp_path),
        review_resolver=build_review_resolver(
            const_reviewer("approve", reason="ok"), on_event=recorder
        ),
    )

    # Decision and loop outcome identical; only emission differs.
    assert off.terminal_event == on.terminal_event == "loop_completed"
    assert off.stop_reason == on.stop_reason
    assert len(recorder.events) > 0
