"""Interactive session registry for the web/API host (011).

A session keeps a Phase-2 ``host.session(...)`` open in a background task held by
the app lifespan, so submit / answer / cancel requests reach the same live
``Session`` across requests (FR-007-FR-010). The session's normalized events flow
to an unbounded SSE channel the events endpoint drains; closing the session ends
the background task and frees the (sequential) host for the next one.
"""

from __future__ import annotations

import math
from contextlib import suppress
from dataclasses import dataclass

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream

from loopplane.events import RuntimeEvent, serialize_event
from loopplane.host import LoopPlaneHost, Session

_STREAM_CLOSED = (anyio.BrokenResourceError, anyio.ClosedResourceError)


@dataclass
class SessionEntry:
    """A live interactive session: its handle, its SSE event channel, and the
    event that closes it."""

    session: Session
    events: MemoryObjectReceiveStream[str]
    close: anyio.Event


async def run_session(
    host: LoopPlaneHost,
    sessions: dict[str, SessionEntry],
    ready: anyio.Event,
    box: dict[str, str],
) -> None:
    """Hold a ``host.session`` open until closed; register its handle + SSE
    channel. On a sequential-host conflict, signal the opener via ``box['error']``.
    """

    send, receive = anyio.create_memory_object_stream[str](math.inf)

    async def sink(event: RuntimeEvent) -> None:
        # A gone client must never crash or hang the session (FR-006 posture).
        with suppress(*_STREAM_CLOSED):
            await send.send(f"data: {serialize_event(event)}\n\n")

    close = anyio.Event()
    try:
        async with host.session(sink) as session:
            box["sid"] = session.session_id
            sessions[session.session_id] = SessionEntry(session, receive, close)
            ready.set()
            await close.wait()
    except RuntimeError:
        box["error"] = "conflict"
        ready.set()
    finally:
        sessions.pop(box.get("sid", ""), None)
        with suppress(*_STREAM_CLOSED):
            await send.aclose()
