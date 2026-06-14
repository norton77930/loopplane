"""US1: run a prompt from the local console -> a metadata-only result view
(SC-001). In-process only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.studio import ErrorView, HistoryEntryView, RunResultView, StudioHost
from tests.studio_helpers import build_test_host, multi_text_model, tool_then_text_model


@pytest.mark.anyio
async def test_run_returns_metadata_only_view(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=tool_then_text_model())
    async with StudioHost(host) as studio:
        result = await studio.run("please run")

    assert isinstance(result, RunResultView)
    assert result.session_id
    assert result.termination_reason == "natural-completion"
    assert result.turns_taken >= 1
    assert len(result.history) >= 2
    assert all(isinstance(entry, HistoryEntryView) for entry in result.history)
    # The run's own content (the echoed tool text, the closing "done") must not
    # leak into the view (FR-030).
    assert "hello" not in repr(result)
    assert "done" not in repr(result)


@pytest.mark.anyio
async def test_run_rejects_empty_prompt(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    async with StudioHost(host) as studio:
        result = await studio.run("")

    assert isinstance(result, ErrorView)
    assert result.kind == "invalid"


@pytest.mark.anyio
async def test_concurrent_run_returns_conflict(tmp_path: Path) -> None:
    # The console maps the host's sequential-run RuntimeError to a conflict view;
    # the host's sequential guarantee itself is covered by the Phase-2 host suite.
    class _ConflictHost:
        async def run(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("a run is already active")

    async with StudioHost(_ConflictHost()) as studio:  # type: ignore[arg-type]
        result = await studio.run("x")

    assert isinstance(result, ErrorView)
    assert result.kind == "conflict"
