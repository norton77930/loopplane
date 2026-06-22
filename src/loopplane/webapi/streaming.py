"""SSE event streaming for the web/API host (011).

Forwards a run's normalized events to a connected client as Server-Sent Events —
each frame the public ``serialize_event`` of the event (Constitution VI: a
streaming **consumer** of the recorded normalized stream, never a re-emitter).
Fail-safe: a slow, failing, or disconnecting client never crashes or hangs the
run; the run is driven on an unbounded channel so a sink send never blocks it
(FR-004-FR-006, NFR-005).
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from contextlib import suppress

import anyio

from loopplane.events import RuntimeEvent, serialize_event
from loopplane.host import LoopPlaneHost, PlatformFairnessRejected, Prompt
from loopplane.webapi.models import ErrorResponse, RunResult

_STREAM_CLOSED = (anyio.BrokenResourceError, anyio.ClosedResourceError)


def _frame(data_json: str, *, event: str | None = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data_json}\n\n"


async def run_event_stream(
    host: LoopPlaneHost,
    prompt: Prompt,
    principal_id: str | None = None,
    output_schema: dict[str, object] | None = None,
) -> AsyncIterator[str]:
    """Drive one run and yield its normalized events as SSE frames in recorded
    order, then a final ``outcome`` frame (or an ``error`` frame on conflict).

    ``prompt`` is the assembled run input — either text, or a block sequence
    carrying image input (036)."""

    send, receive = anyio.create_memory_object_stream[str](math.inf)

    async def sink(event: RuntimeEvent) -> None:
        # A gone/slow client must never crash or hang the run (FR-006).
        with suppress(*_STREAM_CLOSED):
            await send.send(_frame(serialize_event(event)))

    async def drive() -> None:
        try:
            try:
                outcome = await host.run(
                    prompt, sink, principal_id=principal_id, output_schema=output_schema
                )
                final = _frame(
                    RunResult.from_outcome(outcome).model_dump_json(), event="outcome"
                )
            except PlatformFairnessRejected:
                final = _frame(
                    ErrorResponse(detail="capacity exceeded").model_dump_json(),
                    event="error",
                )
            except RuntimeError:
                final = _frame(
                    ErrorResponse(detail="a run is already active").model_dump_json(),
                    event="error",
                )
            with suppress(*_STREAM_CLOSED):
                await send.send(final)
        finally:
            await send.aclose()

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(drive)
        async with receive:
            async for frame in receive:
                yield frame
