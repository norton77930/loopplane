"""``create_app``: the web/API host application factory (011).

Builds an ASGI app that exposes the embedded :class:`~loopplane.host.LoopPlaneHost`
behind the authentication boundary: run, event stream, interactive session, and
read-only inspection. Malformed requests return the one public-safe
``ErrorResponse`` envelope (FR-016). Interactive sessions live in a lifespan-held
task group (see :mod:`loopplane.webapi.sessions`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from loopplane.events import RuntimeEvent
from loopplane.host import LoopPlaneHost
from loopplane.webapi.auth import DENY_ALL, Authenticator, make_auth_dependency
from loopplane.webapi.models import (
    ErrorResponse,
    OpenedSession,
    QuestionAnswer,
    Resolved,
    RunRequest,
    RunResult,
    SessionAnswer,
)
from loopplane.webapi.sessions import SessionEntry, run_session
from loopplane.webapi.streaming import run_event_stream


async def _discard(event: RuntimeEvent) -> None:
    """A run sink that drops events — used when only the outcome is returned."""

    return None


def create_app(
    host: LoopPlaneHost,
    *,
    authenticator: Authenticator | None = None,
    api_prefix: str = "/v1",
) -> FastAPI:
    """Build the web/API host app embedding ``host`` behind the auth boundary.

    ``authenticator`` is the embedder's verifier; absent one, every request is
    denied (default-deny, FR-014).
    """

    auth = authenticator or DENY_ALL
    sessions: dict[str, SessionEntry] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # A task group that outlives individual requests holds open interactive
        # sessions until they are closed (US3).
        async with anyio.create_task_group() as task_group:
            app.state.session_tg = task_group
            try:
                yield
            finally:
                task_group.cancel_scope.cancel()

    app = FastAPI(lifespan=lifespan)

    async def on_validation_error(request: Request, exc: Exception) -> JSONResponse:
        # A malformed request → a fixed public-safe envelope, never the
        # field-level internals (FR-016).
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(detail="invalid request").model_dump(),
        )

    app.add_exception_handler(RequestValidationError, on_validation_error)

    router = APIRouter(
        prefix=api_prefix, dependencies=[Depends(make_auth_dependency(auth))]
    )

    def _require(session_id: str) -> SessionEntry:
        entry = sessions.get(session_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="not found")
        return entry

    # --- US1: run -----------------------------------------------------------

    @router.post("/runs")
    async def post_run(body: RunRequest) -> RunResult:
        try:
            outcome = await host.run(body.prompt, _discard)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409, detail="a run is already active"
            ) from exc
        return RunResult.from_outcome(outcome)

    # --- US2: event stream --------------------------------------------------

    @router.post("/runs/events")
    async def post_run_events(body: RunRequest) -> StreamingResponse:
        return StreamingResponse(
            run_event_stream(host, body.prompt), media_type="text/event-stream"
        )

    # --- US3: interactive session -------------------------------------------

    @router.post("/sessions")
    async def open_session() -> OpenedSession:
        ready = anyio.Event()
        box: dict[str, str] = {}
        app.state.session_tg.start_soon(run_session, host, sessions, ready, box)
        await ready.wait()
        if box.get("error"):
            raise HTTPException(status_code=409, detail="a run is already active")
        return OpenedSession(session_id=box["sid"])

    @router.get("/sessions/{session_id}/events")
    async def session_events(session_id: str) -> StreamingResponse:
        entry = _require(session_id)

        async def stream() -> AsyncIterator[str]:
            async for frame in entry.events:
                yield frame

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.post("/sessions/{session_id}/submit")
    async def submit_to_session(session_id: str, body: RunRequest) -> RunResult:
        entry = _require(session_id)
        outcome = await entry.session.submit(body.prompt)
        return RunResult.from_outcome(outcome)

    @router.post("/sessions/{session_id}/approvals/{request_id}")
    async def answer_approval(
        session_id: str, request_id: str, body: SessionAnswer
    ) -> Resolved:
        entry = _require(session_id)
        resolved = entry.session.answer_approval(
            request_id, allow=body.allow, scope=body.scope, reason=body.reason
        )
        return Resolved(resolved=resolved)

    @router.post("/sessions/{session_id}/questions/{request_id}")
    async def answer_question(
        session_id: str, request_id: str, body: QuestionAnswer
    ) -> Resolved:
        entry = _require(session_id)
        resolved = entry.session.answer_question(request_id, body.answers)
        return Resolved(resolved=resolved)

    @router.post("/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str) -> Resolved:
        entry = _require(session_id)
        entry.session.cancel()
        entry.close.set()
        return Resolved(resolved=True)

    app.include_router(router)
    return app
