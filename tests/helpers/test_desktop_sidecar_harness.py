"""Self-tests for the desktop sidecar harness (T011 / T015)."""

from __future__ import annotations

import pytest
from tests.helpers.desktop_sidecar import ByteSplitStdio, SidecarHarness


def test_byte_split_utf8_readline() -> None:
    io = ByteSplitStdio(read_chunk_size=1)
    io.feed_input("你好\n")
    chunks: list[bytes] = []
    while True:
        c = io.readline()
        if not c:
            break
        chunks.append(c)
    assert b"".join(chunks).decode("utf-8") == "你好\n"
    assert all(len(c) == 1 for c in chunks)


def test_child_crash_and_kill() -> None:
    h = SidecarHarness()
    h.force_child_failure(7)
    assert h.child.poll() == 7
    h.child.kill()
    assert h.child.killed is True
    assert h.child.returncode == -9


def test_write_fault_raises() -> None:
    h = SidecarHarness()
    h.force_write_fault()
    with pytest.raises(OSError, match="synthetic write failure"):
        h.child.stdin.write("x")


def test_clock_advances() -> None:
    h = SidecarHarness()
    assert h.clock.time() == 0.0
    h.clock.advance(1.5)
    assert h.clock.time() == 1.5
