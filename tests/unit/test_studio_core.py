"""Unit tests for the desktop/studio host foundations (012): metadata-only view
projections + the ``StudioHost`` async-context-manager core.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.host import RunOutcome
from loopplane.loop.history import HistoryEntry
from loopplane.model import TextBlock
from loopplane.studio import ErrorView, HistoryEntryView, RunResultView, StudioHost
from tests.studio_helpers import build_test_host, multi_text_model


def test_run_result_view_drops_block_content() -> None:
    entry = HistoryEntry(
        role="assistant",
        blocks=(TextBlock(text="alpha"), TextBlock(text="beta")),
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    outcome = RunOutcome(
        session_id="s1",
        termination_reason="natural-completion",
        turns_taken=2,
        history=(entry,),
        consumer_failures=(),
    )

    view = RunResultView.from_outcome(outcome)

    assert view.session_id == "s1"
    assert view.termination_reason == "natural-completion"
    assert view.turns_taken == 2
    assert view.history == (HistoryEntryView(role="assistant", block_count=2),)
    # The block text must never appear in the view (FR-030).
    assert "alpha" not in repr(view)
    assert "beta" not in repr(view)


def test_error_view_is_a_kind_and_detail() -> None:
    error = ErrorView(kind="not-found", detail="not found")
    assert error.kind == "not-found"
    assert error.detail == "not found"


@pytest.mark.anyio
async def test_studio_host_enters_and_exits(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    async with StudioHost(host) as studio:
        assert isinstance(studio, StudioHost)
