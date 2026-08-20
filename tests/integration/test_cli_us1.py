"""US1: hold an interactive chat from the terminal (T009; FR-002, SC-001)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from loopplane.cli import chat_loop, run_once
from tests.cli_helpers import scripted_host

pytestmark = pytest.mark.anyio


async def test_chat_renders_each_turn_and_quits() -> None:
    host = scripted_host("first reply", "second reply")
    out = io.StringIO()
    await chat_loop(host, ["hello", "again", "quit"], out)
    text = out.getvalue()
    assert "first reply" in text
    assert "second reply" in text


async def test_chat_ends_cleanly_on_eof() -> None:
    host = scripted_host("only reply")
    out = io.StringIO()
    await chat_loop(host, ["hi"], out)  # the iterable ends -> EOF
    assert "only reply" in out.getvalue()


async def test_run_once_still_performs_exactly_one_run(tmp_path: Path) -> None:
    """079 T007: the one-shot path is pinned, so the interactive rewrite cannot
    silently change what `loopplane run` does."""

    host = scripted_host("a one-shot reply")
    out = io.StringIO()
    outcome = await run_once(host, "hello", out)
    text = out.getvalue()
    assert "a one-shot reply" in text
    assert text.count("[run ") == 1
    assert outcome.turns_taken == 1
    assert len(host.list_sessions()) == 1
