"""Unit 058: resumable SSE (reconnect).

Covers the additive, default-off reconnect support on the session SSE stream:
- ``frame_sequence`` parses the SSE ``id:`` line (the dedup helper);
- ``reconnect_stream`` is the real endpoint logic — replay buffered frames after
  ``Last-Event-ID`` then continue live, deduped by sequence (no loss, no dup), and
  a byte-identical pass-through when off / no (or malformed) id;
- the real ``run_session`` sink prefixes ``id:`` + fills the bounded buffer when on,
  and is byte-identical (``data:`` only, no buffer) when disabled.

Offline / in-process. The live session SSE stream is infinite, so the reconnect
logic is exercised through the pure ``reconnect_stream`` helper — the merge-path
tests feed a real (pre-filled, closed) anyio memory stream (so the non-blocking
``receive_nowait`` backlog drain runs); the pass-through tests feed a plain async
iterator — rather than an infinite ``TestClient`` read.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

pytest.importorskip("fastapi")

from loopplane.model import TextBlock  # noqa: E402
from loopplane.webapi.sessions import (  # noqa: E402
    frame_sequence,
    reconnect_stream,
    run_session,
)
from tests.webapi_helpers import build_test_host, multi_text_model  # noqa: E402


async def _agen(items: list[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


def _live_stream(items: list[str]) -> MemoryObjectReceiveStream[str]:
    """A real anyio receive stream pre-filled with ``items`` then closed — models
    frames already queued undrained in the live channel (so ``receive_nowait``
    drains the whole backlog, then the stream ends)."""

    send, receive = anyio.create_memory_object_stream[str](max(len(items), 1))
    for item in items:
        send.send_nowait(item)
    send.close()
    return receive


# --- frame_sequence (FR-001 dedup helper) ----------------------------------


def test_frame_sequence_parses_id() -> None:
    assert frame_sequence("id: 7\ndata: x\n\n") == 7


def test_frame_sequence_none_without_id_line() -> None:
    assert frame_sequence("data: x\n\n") is None


def test_frame_sequence_none_on_non_int() -> None:
    assert frame_sequence("id: abc\ndata: x\n\n") is None


def test_frame_sequence_none_without_newline() -> None:
    assert frame_sequence("id: 7") is None


# --- reconnect_stream (FR-003/004/005: replay + dedup + fail-safe) ----------


@pytest.mark.anyio
async def test_replay_after_last_event_id_dedupes_live() -> None:
    frames = {i: f"id: {i}\ndata: e{i}\n\n" for i in (1, 2, 3)}
    buf = deque((i, frames[i]) for i in (1, 2, 3))
    live = _live_stream([frames[1], frames[2], frames[3]])
    out = [f async for f in reconnect_stream(buf, "1", live)]
    # Merge buffer (2,3 > 1) with the live backlog (1 skipped; 2,3 deduped by
    # sequence) -> each frame delivered exactly once, in order.
    assert out == [frames[2], frames[3]]


@pytest.mark.anyio
async def test_replay_then_new_live_no_loss_no_dup() -> None:
    frames = {i: f"id: {i}\ndata: e{i}\n\n" for i in (1, 2, 3)}
    buf = deque([(1, frames[1]), (2, frames[2])])
    # client saw up to 1; live channel still holds 2 (already buffered) then 3
    live = _live_stream([frames[2], frames[3]])
    out = [f async for f in reconnect_stream(buf, "1", live)]
    # merge: 2 (buffer+live, deduped once) + 3 (new, delivered). No loss, no dup.
    assert out == [frames[2], frames[3]]


@pytest.mark.anyio
async def test_rollover_does_not_lose_frames_queued_in_live() -> None:
    # The bounded ring (maxlen=2) evicted 2,3 so the buffer holds only (4,5), but
    # 2,3 are STILL queued undrained in the live stream (a slow client that
    # disconnected after seeing only 1). A reconnect from id=1 must deliver
    # 2,3,4,5 once each, IN ORDER — no loss (the 058 dedup fix), no duplicate.
    frames = {i: f"id: {i}\ndata: e{i}\n\n" for i in (1, 2, 3, 4, 5)}
    buf: deque[tuple[int, str]] = deque(maxlen=2)
    for i in (1, 2, 3, 4, 5):
        buf.append((i, frames[i]))  # -> holds (4, 5)
    live = _live_stream([frames[i] for i in (2, 3, 4, 5)])
    out = [f async for f in reconnect_stream(buf, "1", live)]
    assert out == [frames[2], frames[3], frames[4], frames[5]]


@pytest.mark.anyio
async def test_no_buffer_is_passthrough() -> None:
    live = _agen(["data: a\n\n", "data: b\n\n"])
    out = [f async for f in reconnect_stream(None, "1", live)]
    assert out == ["data: a\n\n", "data: b\n\n"]


@pytest.mark.anyio
async def test_no_last_event_id_streams_live() -> None:
    frames = {i: f"id: {i}\ndata: e{i}\n\n" for i in (1, 2)}
    buf = deque([(1, frames[1])])
    live = _agen([frames[1], frames[2]])
    out = [f async for f in reconnect_stream(buf, None, live)]
    assert out == [frames[1], frames[2]]  # no replay; live pass-through


@pytest.mark.anyio
async def test_garbage_last_event_id_is_fail_safe() -> None:
    frames = {i: f"id: {i}\ndata: e{i}\n\n" for i in (1, 2)}
    buf = deque([(1, frames[1]), (2, frames[2])])
    live = _agen([frames[1], frames[2]])
    out = [f async for f in reconnect_stream(buf, "not-an-int", live)]
    assert out == [frames[1], frames[2]]  # garbage -> live, no crash


@pytest.mark.anyio
async def test_bounded_buffer_retains_last_n_only() -> None:
    buf: deque[tuple[int, str]] = deque(maxlen=2)
    for i in (1, 2, 3):
        buf.append((i, f"id: {i}\ndata: e{i}\n\n"))
    out = [f async for f in reconnect_stream(buf, "0", _live_stream([]))]
    # 1 was evicted (maxlen=2); only 2,3 retained + replayed (empty live backlog).
    assert out == ["id: 2\ndata: e2\n\n", "id: 3\ndata: e3\n\n"]


# --- run_session sink: buffer fill vs default-off byte-identity -------------


@pytest.mark.anyio
async def test_run_session_buffer_records_id_frames(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("alpha"), tools=())
    sessions: dict = {}
    ready = anyio.Event()
    box: dict[str, str] = {}
    snapshot: list[tuple[int, str]] = []
    async with anyio.create_task_group() as tg:
        tg.start_soon(
            run_session, host, sessions, ready, box, "owner", False, False, 50
        )
        await ready.wait()
        entry = sessions[box["sid"]]
        await entry.session.submit([TextBlock(text="go")])
        assert entry.replay_buffer is not None
        snapshot = list(entry.replay_buffer)
        entry.close.set()
    assert snapshot, "the run should have emitted buffered events"
    seqs = [seq for seq, _ in snapshot]
    assert seqs == sorted(seqs), "sequences are monotonic"
    for seq, frame in snapshot:
        assert frame.startswith(f"id: {seq}\n")
        assert "\ndata: " in frame


@pytest.mark.anyio
async def test_run_session_default_off_is_byte_identical(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("alpha"), tools=())
    sessions: dict = {}
    ready = anyio.Event()
    box: dict[str, str] = {}
    frames: list[str] = []
    async with anyio.create_task_group() as tg:
        tg.start_soon(run_session, host, sessions, ready, box, "owner", False, False, 0)
        await ready.wait()
        entry = sessions[box["sid"]]
        await entry.session.submit([TextBlock(text="go")])
        assert entry.replay_buffer is None
        while True:
            try:
                frames.append(entry.events.receive_nowait())
            except anyio.WouldBlock:
                break
        entry.close.set()
    assert frames, "the run should have emitted frames"
    for frame in frames:
        assert frame.startswith("data: ")
        assert not frame.startswith("id: ")
