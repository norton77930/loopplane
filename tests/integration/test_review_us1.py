"""US1: gate a loop on a human reviewer (spec US1; SC-001/002/003/007).

A review gate built from a reviewer drives a loop at needs_human_review: approve
=> loop_completed, reject/request_changes => loop_failed, reading only the public
Loop State and driving only through run_loop.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import run_loop
from loopplane.review import build_review_resolver
from tests.loop_helpers import RaisingValidator
from tests.review_helpers import (
    RecordingReviewer,
    const_reviewer,
    needs_review_definition,
    raising_reviewer,
    unknown_outcome_reviewer,
)

pytestmark = pytest.mark.anyio


async def test_approve_completes_the_loop(tmp_path: Path) -> None:
    gate = build_review_resolver(const_reviewer("approve", reason="looks good"))
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    assert outcome.terminal_event == "loop_completed"


async def test_reject_fails_the_loop(tmp_path: Path) -> None:
    gate = build_review_resolver(const_reviewer("reject", reason="not acceptable"))
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    assert outcome.terminal_event == "loop_failed"
    assert outcome.stop_reason == "not acceptable"


async def test_request_changes_is_non_approval(tmp_path: Path) -> None:
    gate = build_review_resolver(const_reviewer("request_changes"))
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    assert outcome.terminal_event == "loop_failed"


async def test_review_request_carries_the_state(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("approve")
    gate = build_review_resolver(reviewer)
    await run_loop(
        needs_review_definition(loop_id="myloop", working_scope=tmp_path),
        review_resolver=gate,
    )
    assert reviewer.seen is not None
    assert reviewer.seen.loop_id == "myloop"
    assert reviewer.seen.cause == "validator_status"
    assert reviewer.seen.validation_reason == "please review"
    assert reviewer.seen.session_id is not None


async def test_raising_reviewer_fails_safe_not_silent_approve(tmp_path: Path) -> None:
    gate = build_review_resolver(raising_reviewer())
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    assert outcome.terminal_event == "loop_failed"


async def test_unknown_outcome_fails_safe(tmp_path: Path) -> None:
    gate = build_review_resolver(unknown_outcome_reviewer())
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    assert outcome.terminal_event == "loop_failed"


async def test_fail_safe_cause_review_is_auditable(tmp_path: Path) -> None:
    # A raising validator routes to review with cause=fail_safe and no validation
    # status; a human may still approve, and the request records the cause.
    reviewer = RecordingReviewer("approve")
    gate = build_review_resolver(reviewer)
    outcome = await run_loop(
        needs_review_definition(validator=RaisingValidator(), working_scope=tmp_path),
        review_resolver=gate,
    )
    assert reviewer.seen is not None
    assert reviewer.seen.cause == "fail_safe"
    assert reviewer.seen.validation_status is None
    assert outcome.terminal_event == "loop_completed"


async def test_run_goes_through_run_loop(tmp_path: Path) -> None:
    gate = build_review_resolver(const_reviewer("approve"))
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    # A real Agent Run drove through run_loop -> host: Loop State references it.
    assert len(outcome.state.run_refs) >= 1


async def test_gated_review_is_deterministic(tmp_path: Path) -> None:
    first = await run_loop(
        needs_review_definition(working_scope=tmp_path),
        review_resolver=build_review_resolver(const_reviewer("approve", reason="ok")),
    )
    second = await run_loop(
        needs_review_definition(working_scope=tmp_path),
        review_resolver=build_review_resolver(const_reviewer("approve", reason="ok")),
    )
    assert first.terminal_event == second.terminal_event == "loop_completed"
    assert first.stop_reason == second.stop_reason
