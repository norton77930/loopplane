"""``create_app``: the web/API host application factory (011).

Builds an ASGI app that exposes the embedded :class:`~loopplane.host.LoopPlaneHost`
behind the authentication boundary. Routes are mounted per user story (US1-US5);
malformed requests return the one public-safe ``ErrorResponse`` envelope (FR-016).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from loopplane.host import LoopPlaneHost
from loopplane.webapi.auth import DENY_ALL, Authenticator, make_auth_dependency
from loopplane.webapi.models import ErrorResponse


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
    # Routes are mounted onto `router` per user story (US1-US5).
    app.include_router(router)
    return app
