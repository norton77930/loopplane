"""``create_app``: the web/API host application factory (011; per-principal
ownership added in 022).

Builds an ASGI app that exposes the embedded :class:`~loopplane.host.LoopPlaneHost`
behind the authentication boundary: run, event stream, interactive session, and
read-only inspection. The boundary now identifies the caller (a ``Principal``) and
every session is scoped to the principal that opened it — the listing returns only
the caller's sessions, and a per-session route returns ``404`` (never another
principal's data or its existence) for a session the caller does not own. Malformed
requests return the one public-safe ``ErrorResponse`` envelope (FR-016). Interactive
sessions live in a lifespan-held task group (see :mod:`loopplane.webapi.sessions`).
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
from loopplane.webapi.auth import (
    DENY_ALL,
    Authenticator,
    Principal,
    make_auth_dependency,
)
from loopplane.webapi.models import (
    ArtifactContent,
    ErrorResponse,
    HistoryEntryView,
    OpenedSession,
    QuestionAnswer,
    Resolved,
    RunRequest,
    RunResult,
    SessionAnswer,
    SessionSummaryView,
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
    denied (default-deny, FR-014). Each route resolves the caller's ``Principal``
    and scopes sessions to it (022).
    """

    auth = authenticator or DENY_ALL
    require = make_auth_dependency(auth)
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

    # Auth is enforced per route by resolving the caller's principal; this also
    # hands each route the identity it scopes ownership against.
    router = APIRouter(prefix=api_prefix)

    def _require(session_id: str, principal: Principal) -> SessionEntry:
        # A live interactive session the caller owns — otherwise 404 (never reveal
        # another principal's session or its existence).
        entry = sessions.get(session_id)
        if entry is None or entry.owner != principal.id:
            raise HTTPException(status_code=404, detail="not found")
        return entry

    def _owned_or_404(session_id: str, principal: Principal) -> None:
        # Ownership for the durable/inspection routes: a live session by its
        # registry owner, else the durable owner from the checkpoint metadata.
        entry = sessions.get(session_id)
        if entry is not None:
            if entry.owner != principal.id:
                raise HTTPException(status_code=404, detail="not found")
            return
        for summary in host.list_sessions():
            if summary.session_id == session_id:
                if summary.principal_id != principal.id:
                    raise HTTPException(status_code=404, detail="not found")
                return
        raise HTTPException(status_code=404, detail="not found")

    # --- US1: run -----------------------------------------------------------

    @router.post("/runs")
    async def post_run(
        body: RunRequest, principal: Principal = Depends(require)
    ) -> RunResult:
        try:
            outcome = await host.run(body.prompt, _discard, principal_id=principal.id)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409, detail="a run is already active"
            ) from exc
        return RunResult.from_outcome(outcome)

    # --- US2: event stream --------------------------------------------------

    @router.post("/runs/events")
    async def post_run_events(
        body: RunRequest, principal: Principal = Depends(require)
    ) -> StreamingResponse:
        return StreamingResponse(
            run_event_stream(host, body.prompt, principal.id),
            media_type="text/event-stream",
        )

    # --- US3: interactive session -------------------------------------------

    @router.post("/sessions")
    async def open_session(
        principal: Principal = Depends(require),
    ) -> OpenedSession:
        ready = anyio.Event()
        box: dict[str, str] = {}
        app.state.session_tg.start_soon(
            run_session, host, sessions, ready, box, principal.id
        )
        await ready.wait()
        if box.get("error"):
            raise HTTPException(status_code=409, detail="a run is already active")
        return OpenedSession(session_id=box["sid"])

    @router.get("/sessions/{session_id}/events")
    async def session_events(
        session_id: str, principal: Principal = Depends(require)
    ) -> StreamingResponse:
        entry = _require(session_id, principal)

        async def stream() -> AsyncIterator[str]:
            async for frame in entry.events:
                yield frame

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.post("/sessions/{session_id}/submit")
    async def submit_to_session(
        session_id: str, body: RunRequest, principal: Principal = Depends(require)
    ) -> RunResult:
        # Drive the live session to its outcome. A pending approval/question is
        # answered out-of-band by a concurrent request; a client that prefers to
        # observe progress incrementally reads the session events stream (FR-007).
        entry = _require(session_id, principal)
        outcome = await entry.session.submit(body.prompt)
        return RunResult.from_outcome(outcome)

    @router.post("/sessions/{session_id}/approvals/{request_id}")
    async def answer_approval(
        session_id: str,
        request_id: str,
        body: SessionAnswer,
        principal: Principal = Depends(require),
    ) -> Resolved:
        entry = _require(session_id, principal)
        resolved = entry.session.answer_approval(
            request_id, allow=body.allow, scope=body.scope, reason=body.reason
        )
        return Resolved(resolved=resolved)

    @router.post("/sessions/{session_id}/questions/{request_id}")
    async def answer_question(
        session_id: str,
        request_id: str,
        body: QuestionAnswer,
        principal: Principal = Depends(require),
    ) -> Resolved:
        entry = _require(session_id, principal)
        resolved = entry.session.answer_question(request_id, body.answers)
        return Resolved(resolved=resolved)

    @router.post("/sessions/{session_id}/cancel")
    async def cancel_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        entry = _require(session_id, principal)
        entry.session.cancel()
        entry.close.set()
        return Resolved(resolved=True)

    # --- US4: inspection (read-only, metadata-only) -------------------------

    @router.get("/sessions")
    async def list_sessions(
        principal: Principal = Depends(require),
    ) -> list[SessionSummaryView]:
        return [
            SessionSummaryView.from_summary(summary)
            for summary in host.list_sessions()
            if summary.principal_id == principal.id
        ]

    @router.get("/sessions/{session_id}/history")
    async def session_history(
        session_id: str, principal: Principal = Depends(require)
    ) -> list[HistoryEntryView]:
        _owned_or_404(session_id, principal)
        try:
            entries = host.history_snapshot(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return [
            HistoryEntryView(role=entry.role, block_count=len(entry.blocks))
            for entry in entries
        ]

    @router.post("/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        _owned_or_404(session_id, principal)
        try:
            await host.resume(session_id)
        except (KeyError, RuntimeError):
            raise HTTPException(status_code=404, detail="not found") from None
        return Resolved(resolved=True)

    @router.get("/sessions/{session_id}/artifacts/{reference}")
    async def get_artifact(
        session_id: str, reference: str, principal: Principal = Depends(require)
    ) -> ArtifactContent:
        _owned_or_404(session_id, principal)
        content = host.retrieve_artifact(session_id, reference)
        if content is None:
            raise HTTPException(status_code=404, detail="not found")
        return ArtifactContent(reference=reference, content=content)

    app.include_router(router)
    return app
