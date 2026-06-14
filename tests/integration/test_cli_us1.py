"""US1: hold an interactive chat from the terminal (T009; FR-002, SC-001)."""

from __future__ import annotations

import io

import pytest

from loopplane.cli import chat_loop
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
