"""The held-open interactive-session registry for the studio host (012).

A session keeps a Phase-2 ``host.session(...)`` open in a background task held by
the ``StudioHost`` task group, so submit / answer / cancel reach the same live
``Session`` across console commands (FR-010-FR-022). Closing it ends the task and
frees the (sequential) host.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import anyio

from loopplane.host import ApprovalDecision, LoopPlaneHost, Session

# An approval handler / run sink, each typed over ``object`` so it is a valid
# host ``OnApproval`` / ``EventSink`` by contravariance — avoiding a
# ``loopplane.events`` import (boundary discipline).
OnApproval = Callable[[object], Awaitable[ApprovalDecision]]
Sink = Callable[[object], Awaitable[None]]


@dataclass
class SessionEntry:
    """A live interactive session: its handle and the event that closes it."""

    session: Session
    close: anyio.Event


async def run_session(
    host: LoopPlaneHost,
    sessions: dict[str, SessionEntry],
    ready: anyio.Event,
    box: dict[str, str],
    sink: Sink,
    on_approval: OnApproval | None,
) -> None:
    """Hold a ``host.session`` open until closed; register its handle by id. On a
    sequential-host conflict, signal the opener via ``box['error']``."""

    close = anyio.Event()
    try:
        async with host.session(sink, on_approval=on_approval) as session:
            box["sid"] = session.session_id
            sessions[session.session_id] = SessionEntry(session, close)
            ready.set()
            await close.wait()
    except RuntimeError:
        box["error"] = "conflict"
        ready.set()
    finally:
        sessions.pop(box.get("sid", ""), None)
