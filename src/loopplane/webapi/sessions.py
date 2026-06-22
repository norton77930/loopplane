"""Interactive session registry for the web/API host (011).

A session keeps a Phase-2 ``host.session(...)`` open in a background task held by
the app lifespan, so submit / answer / cancel requests reach the same live
``Session`` across requests (FR-007-FR-010). The session's normalized events flow
to an unbounded SSE channel the events endpoint drains; closing the session ends
the background task and frees the (sequential) host for the next one.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import AsyncIterator, Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream

from loopplane.events import RuntimeEvent, serialize_event
from loopplane.host import LoopPlaneHost, Session
from loopplane.webapi.replay import EventReplayRecord, EventReplayStore

_STREAM_CLOSED = (anyio.BrokenResourceError, anyio.ClosedResourceError)


@dataclass
class SessionEntry:
    """A live interactive session: its handle, its SSE event channel, the event
    that closes it, the principal id that owns it (022), and whether its model
    accepts image input (036, for the submit endpoint's degradation check)."""

    session: Session
    events: MemoryObjectReceiveStream[str]
    close: anyio.Event
    owner: str
    accepts_media: bool = False
    supports_structured_output: bool = False  # 045 — for the submit degradation check
    replay_buffer: deque[tuple[int, str]] | None = (
        None  # 058 — None = off (byte-identical)
    )


def frame_sequence(frame: str) -> int | None:
    """The event ``sequence`` parsed from an SSE frame's leading ``id:`` line, or
    ``None`` when the frame carries no id line (058 reconnect dedup helper)."""

    if not frame.startswith("id: "):
        return None
    newline = frame.find("\n")
    if newline == -1:
        return None
    try:
        return int(frame[4:newline])
    except ValueError:
        return None


async def reconnect_stream(
    buffer: deque[tuple[int, str]] | None,
    last_event_id: str | None,
    live: AsyncIterator[str],
    *,
    durable_records: Iterable[EventReplayRecord] = (),
) -> AsyncIterator[str]:
    """The session SSE stream with 058 reconnect support.

    With no buffer / no (or malformed) ``Last-Event-ID`` this is the byte-identical
    live pass-through. On a valid reconnect it delivers every frame after
    ``last_event_id`` exactly once, in sequence order: the retained buffer (frames
    after ``last_id``) is **merged** with the frames already queued in the live
    stream (drained non-blocking), keyed by sequence, and emitted in sequence
    order; then new live frames continue (deduped). Merging — rather than
    replay-then-skip against a high-water mark — is what keeps a frame that the
    bounded ring evicted but is still queued in the live stream from being lost,
    and keeps the merged backlog in order.
    """

    durable_records = tuple(durable_records)
    last_id: int | None = None
    if (buffer is not None or durable_records) and last_event_id is not None:
        try:
            last_id = int(last_event_id)
        except ValueError:
            last_id = None

    if last_id is None:
        # No buffer / no (or malformed) Last-Event-ID: byte-identical pass-through.
        async for frame in live:
            yield frame
        return

    # Merge the retained buffer with the live frames already queued (both after
    # last_id), keyed by sequence so each frame is delivered once, in order. The
    # live drain is non-blocking so an idle session still replays its backlog now.
    merged: dict[int, str] = {
        seq: frame for seq, frame in list(buffer or ()) if seq > last_id
    }
    for record in durable_records:
        if record.sequence > last_id:
            merged[record.sequence] = record.frame
    if isinstance(live, MemoryObjectReceiveStream):
        while True:
            try:
                frame = live.receive_nowait()
            except (anyio.WouldBlock, anyio.EndOfStream, *_STREAM_CLOSED):
                break
            seq = frame_sequence(frame)
            if seq is not None and seq > last_id:
                merged[seq] = frame
    max_yielded = last_id
    for seq in sorted(merged):
        yield merged[seq]
        max_yielded = seq
    # Continue with new live frames, skipping any already delivered above.
    async for frame in live:
        seq = frame_sequence(frame)
        if seq is not None and seq <= max_yielded:
            continue
        yield frame
        if seq is not None:
            max_yielded = max(max_yielded, seq)


async def replay_store_stream(
    store: EventReplayStore,
    session_id: str,
    principal_id: str,
    last_event_id: str | None,
    *,
    limit: int,
    poll_interval_seconds: float,
    idle_polls: int | None = None,
) -> AsyncIterator[str]:
    """Replay frames from a durable store and tail until no more frames arrive."""

    try:
        last_seen = int(last_event_id) if last_event_id is not None else -1
    except ValueError:
        last_seen = -1
    idle_count = 0
    while True:
        records, _problems = store.load_after(
            session_id, principal_id, last_seen, limit=limit
        )
        if records:
            idle_count = 0
            for record in records:
                yield record.frame
                last_seen = max(last_seen, record.sequence)
            continue
        if idle_polls is not None:
            idle_count += 1
            if idle_count >= idle_polls:
                return
        await anyio.sleep(poll_interval_seconds)


async def run_session(
    host: LoopPlaneHost,
    sessions: dict[str, SessionEntry],
    ready: anyio.Event,
    box: dict[str, str],
    owner: str,
    accepts_media: bool = False,
    supports_structured_output: bool = False,
    replay_buffer: int = 0,
    replay_store: EventReplayStore | None = None,
) -> None:
    """Hold a ``host.session`` open until closed; register its handle + SSE
    channel under its owning principal. On a sequential-host conflict, signal the
    opener via ``box['error']``.

    When ``replay_buffer`` > 0 (058), each SSE frame carries an ``id:`` line (the
    event sequence) and is retained in a bounded per-session ring buffer for
    ``Last-Event-ID`` reconnect replay; 0 (the default) keeps the byte-identical
    ``data:``-only pass-through.
    """

    send, receive = anyio.create_memory_object_stream[str](math.inf)
    buf: deque[tuple[int, str]] | None = (
        deque(maxlen=replay_buffer) if replay_buffer > 0 else None
    )

    async def sink(event: RuntimeEvent) -> None:
        # A gone client must never crash or hang the session (FR-006 posture).
        if buf is not None or replay_store is not None:
            frame = f"id: {event.sequence}\ndata: {serialize_event(event)}\n\n"
            if replay_store is not None:
                with suppress(Exception):
                    await replay_store.append(
                        EventReplayRecord(
                            session_id=box["sid"],
                            sequence=event.sequence,
                            principal_id=owner,
                            frame=frame,
                            recorded_at=datetime.now(UTC),
                        )
                    )
            if buf is not None:
                buf.append((event.sequence, frame))
        else:
            frame = f"data: {serialize_event(event)}\n\n"
        with suppress(*_STREAM_CLOSED):
            await send.send(frame)

    close = anyio.Event()
    try:
        async with host.session(sink, principal_id=owner) as session:
            box["sid"] = session.session_id
            sessions[session.session_id] = SessionEntry(
                session,
                receive,
                close,
                owner,
                accepts_media,
                supports_structured_output,
                replay_buffer=buf,
            )
            ready.set()
            await close.wait()
    except RuntimeError:
        box["error"] = "conflict"
        ready.set()
    finally:
        sessions.pop(box.get("sid", ""), None)
        with suppress(*_STREAM_CLOSED):
            await send.aclose()
