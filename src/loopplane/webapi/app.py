"""``create_app``: the web/API host application factory (011).

Builds an ASGI app that exposes the embedded :class:`~loopplane.host.LoopPlaneHost`
behind the authentication boundary. Routes are mounted per user story (US1-US5);
malformed requests return the one public-safe ``ErrorResponse`` envelope (FR-016).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from loopplane.events import RuntimeEvent
from loopplane.host import LoopPlaneHost
from loopplane.webapi.auth import DENY_ALL, Authenticator, make_auth_dependency
from loopplane.webapi.models import ErrorResponse, RunRequest, RunResult
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
    app = FastAPI()

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

    @router.post("/runs")
    async def post_run(body: RunRequest) -> RunResult:
        # Drive one run through the public host; a sequential-run conflict
        # becomes an explicit 409 (FR-001-FR-003).
        try:
            outcome = await host.run(body.prompt, _discard)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409, detail="a run is already active"
            ) from exc
        return RunResult.from_outcome(outcome)

    @router.post("/runs/events")
    async def post_run_events(body: RunRequest) -> StreamingResponse:
        # Stream the run's normalized events as SSE in recorded order (US2).
        return StreamingResponse(
            run_event_stream(host, body.prompt), media_type="text/event-stream"
        )

    app.include_router(router)
    return app
