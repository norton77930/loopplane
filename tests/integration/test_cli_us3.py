"""US3: list and resume sessions (T011; FR-007)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from loopplane.cli import dispatch, run_once
from tests.cli_helpers import scripted_host


def test_sessions_without_a_store_shows_a_message() -> None:
    out = io.StringIO()
    code = dispatch(["sessions"], out)
    assert code == 0
    assert "no durable sessions" in out.getvalue()


@pytest.mark.anyio
async def test_list_and_resume_with_a_durable_store(tmp_path: Path) -> None:
    host = scripted_host("hi there", store=tmp_path)
    outcome = await run_once(host, "hello", io.StringIO())

    summaries = host.list_sessions()
    assert any(s.session_id == outcome.session_id for s in summaries)

    # A fresh host over the same store reconstructs the session (FR-007).
    fresh = scripted_host("more", store=tmp_path)
    await fresh.resume(outcome.session_id)
    assert fresh.history_snapshot(outcome.session_id)
