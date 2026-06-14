"""US4: inspect a session locally — metadata-only history / sessions views
(SC-003, FR-030). In-process only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.studio import ErrorView, HistoryEntryView, RunResultView, StudioHost
from tests.studio_helpers import build_test_host, multi_text_model, tool_then_text_model


@pytest.mark.anyio
async def test_history_and_sessions_views_are_metadata_only(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=tool_then_text_model(), storage=True)
    async with StudioHost(host) as studio:
        result = await studio.run("go")
        assert isinstance(result, RunResultView)
        session_id = result.session_id

        history = studio.history_view(session_id)
        assert isinstance(history, tuple)
        assert len(history) >= 2
        assert all(isinstance(entry, HistoryEntryView) for entry in history)
        # No conversation content leaks into the metadata view (FR-030).
        assert "hello" not in repr(history)
        assert "done" not in repr(history)

        summaries = studio.list_sessions()
        assert session_id in [summary.session_id for summary in summaries]
        assert all(
            set(vars(summary)) == {"session_id", "label"} for summary in summaries
        )


@pytest.mark.anyio
async def test_history_unknown_session_is_not_found(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a"), tools=(), storage=True
    )
    async with StudioHost(host) as studio:
        result = studio.history_view("ghost")
        assert isinstance(result, ErrorView)
        assert result.kind == "not-found"
