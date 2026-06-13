"""US3: remember review decisions with review memory (spec US3; SC-005)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.engineering import run_loop
from loopplane.review import ReviewMemory, ReviewRequest, build_review_resolver
from tests.review_helpers import (
    RecordingReviewer,
    ReviewEventRecorder,
    const_reviewer,
    needs_review_definition,
)

pytestmark = pytest.mark.anyio


async def test_same_key_resolves_from_memory(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("approve")
    gate = build_review_resolver(reviewer, memory=ReviewMemory())

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert reviewer.calls == 1  # second review resolved from memory


async def test_approvals_only_mode_does_not_remember_rejections(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("reject")
    gate = build_review_resolver(reviewer, memory=ReviewMemory(remember="approvals"))

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert reviewer.calls == 2  # rejection not remembered; reviewer re-invoked


async def test_memory_hit_emits_event(tmp_path: Path) -> None:
    recorder = ReviewEventRecorder()
    gate = build_review_resolver(
        const_reviewer("approve"), memory=ReviewMemory(), on_event=recorder
    )

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert "review_resolved_from_memory" in recorder.types


async def test_different_keys_are_isolated(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("approve")
    gate = build_review_resolver(reviewer, memory=ReviewMemory())

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k2", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert reviewer.calls == 2  # different keys; each invokes the reviewer


def _shared_key(request: ReviewRequest) -> str:
    return "shared"


async def test_rejections_mode_remembers_rejections(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("reject")
    gate = build_review_resolver(reviewer, memory=ReviewMemory(remember="rejections"))

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert reviewer.calls == 1  # rejection remembered; reviewer not re-invoked


async def test_rejections_mode_does_not_remember_approvals(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("approve")
    gate = build_review_resolver(reviewer, memory=ReviewMemory(remember="rejections"))

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert reviewer.calls == 2  # approval not remembered; reviewer re-invoked


async def test_custom_review_key_collapses_unrelated_loops(tmp_path: Path) -> None:
    reviewer = RecordingReviewer("approve")
    gate = build_review_resolver(reviewer, memory=ReviewMemory(key=_shared_key))

    await run_loop(
        needs_review_definition(loop_id="k1", working_scope=tmp_path),
        review_resolver=gate,
    )
    await run_loop(
        needs_review_definition(loop_id="k2", working_scope=tmp_path),
        review_resolver=gate,
    )

    assert reviewer.calls == 1  # one shared key; second resolves from memory
