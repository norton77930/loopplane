"""``create_app``: the WebAPI composition root.

The factory owns application lifespan, shared route state, and the helper closures that
preserve host selection, ownership, upload, and output-schema semantics.  Domain route
handlers are mounted from :mod:`loopplane.webapi.routers` in their original order.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from loopplane.commands import default_registry
from loopplane.host import ContentBlock, LoopPlaneHost, TextBlock
from loopplane.webapi.auth import (
    DENY_ALL,
    Authenticator,
    Principal,
    make_auth_dependency,
)
from loopplane.webapi.live import LiveTicketStore
from loopplane.webapi.models import ErrorResponse, RunRequest
from loopplane.webapi.multimodal import (
    MediaNotAccepted,
    MediaTooLarge,
    UnknownUpload,
    UploadHandoffRejected,
    assemble_blocks,
)
from loopplane.webapi.pool import TenantHostPool
from loopplane.webapi.replay import EventReplayStore
from loopplane.webapi.routers.capabilities import build_router as capabilities_router
from loopplane.webapi.routers.context import ModelHost, RouterState
from loopplane.webapi.routers.cost import build_router as cost_router
from loopplane.webapi.routers.inspection import build_router as inspection_router
from loopplane.webapi.routers.interaction import build_router as interaction_router
from loopplane.webapi.routers.misc import build_router as misc_router
from loopplane.webapi.routers.model_files import build_router as model_files_router
from loopplane.webapi.routers.sessions import build_router as sessions_router
from loopplane.webapi.sessions import SessionEntry
from loopplane.webapi.uploads import UploadStore


def create_app(
    host: LoopPlaneHost,
    *,
    authenticator: Authenticator | None = None,
    api_prefix: str = "/v1",
    models: Mapping[str, ModelHost] | None = None,
    uploads: UploadStore | None = None,
    default_accepts_media: bool = False,
    default_supports_structured_output: bool = False,
    max_image_bytes: int = 5 * 1024 * 1024,
    sse_replay_buffer: int = 0,
    event_replay_store: EventReplayStore | None = None,
    event_replay_limit: int = 1000,
    event_replay_poll_interval_seconds: float = 0.25,
    event_replay_idle_polls: int | None = None,
    host_pool: TenantHostPool | None = None,
) -> FastAPI:
    """Build the WebAPI host over ``host`` behind the auth boundary.

    Every helper here remains singly owned by the factory and is passed by reference to
    all routers through one immutable :class:`RouterState` instance.
    """

    auth = authenticator or DENY_ALL
    require = make_auth_dependency(auth)
    sessions: dict[str, SessionEntry] = {}
    session_hosts: dict[str, tuple[str, LoopPlaneHost]] = {}
    live_tickets = LiveTicketStore()
    catalog = dict(models or {})
    command_registry = default_registry()

    def _select(model: str | None) -> tuple[LoopPlaneHost, bool, bool]:
        if not model:
            return host, default_accepts_media, default_supports_structured_output
        entry = catalog.get(model)
        if entry is None:
            raise HTTPException(status_code=400, detail="unknown model")
        return entry.host, entry.accepts_media, entry.supports_structured_output

    def _resolve(
        model: str | None, principal: Principal
    ) -> tuple[LoopPlaneHost, bool, bool]:
        effective_model = model
        resolve_default = getattr(host, "model_default", None)
        if effective_model is None and callable(resolve_default):
            available = {model_id: entry.label for model_id, entry in catalog.items()}
            default = resolve_default(
                principal.id,
                available_models=available,
            )
            if default.status == "available":
                effective_model = default.model_id
        chosen, accepts_media, supports_so = _select(effective_model)
        if host_pool is not None:
            try:
                chosen = host_pool.host_for(principal.id, effective_model)
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=429, detail="capacity exceeded"
                ) from exc
        return chosen, accepts_media, supports_so

    def _read_upload_available(selected: LoopPlaneHost) -> bool:
        if not hasattr(selected, "inspect_tools"):
            return False
        return any(tool.name == "read_upload" for tool in selected.inspect_tools())

    def _build_blocks(
        body: RunRequest,
        owner: str,
        accepts_media: bool,
        read_upload_available: bool,
    ) -> list[ContentBlock]:
        if not body.uploads:
            return [TextBlock(text=body.prompt)]
        if uploads is None:
            raise HTTPException(status_code=400, detail="uploads not configured")
        try:
            return assemble_blocks(
                body.prompt,
                [ref.reference for ref in body.uploads],
                uploads,
                owner,
                accepts_media=accepts_media,
                accepts_read_upload=read_upload_available,
                max_image_bytes=max_image_bytes,
            )
        except MediaTooLarge as exc:
            raise HTTPException(status_code=413, detail="image too large") from exc
        except UploadHandoffRejected as exc:
            raise HTTPException(
                status_code=400, detail="upload handoff unavailable"
            ) from exc
        except (UnknownUpload, MediaNotAccepted) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _check_output_schema(
        output_schema: dict[str, object] | None, supports: bool
    ) -> None:
        if output_schema is None:
            return
        if not output_schema:
            raise HTTPException(status_code=400, detail="malformed output_schema")
        if not supports:
            raise HTTPException(
                status_code=400,
                detail="model does not support structured output",
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with anyio.create_task_group() as task_group:
            app.state.session_tg = task_group
            try:
                yield
            finally:
                task_group.cancel_scope.cancel()

    app = FastAPI(lifespan=lifespan)

    async def on_validation_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(detail="invalid request").model_dump(),
        )

    app.add_exception_handler(RequestValidationError, on_validation_error)

    def _require(session_id: str, principal: Principal) -> SessionEntry:
        entry = sessions.get(session_id)
        if entry is None or entry.owner != principal.id:
            raise HTTPException(status_code=404, detail="not found")
        return entry

    def _owned_or_404(session_id: str, principal: Principal) -> None:
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

    def _agent_control_host_or_404(
        session_id: str, principal: Principal
    ) -> LoopPlaneHost:
        entry = sessions.get(session_id)
        if entry is not None:
            if entry.owner != principal.id:
                raise HTTPException(status_code=404, detail="not found")
            return entry.host or host
        routed = session_hosts.get(session_id)
        if routed is not None:
            owner, owning_host = routed
            if owner != principal.id:
                raise HTTPException(status_code=404, detail="not found")
            return owning_host
        _owned_or_404(session_id, principal)
        return host

    state = RouterState(
        api_prefix=api_prefix,
        host=host,
        require=require,
        sessions=sessions,
        session_hosts=session_hosts,
        live_tickets=live_tickets,
        catalog=catalog,
        command_registry=command_registry,
        uploads=uploads,
        max_image_bytes=max_image_bytes,
        sse_replay_buffer=sse_replay_buffer,
        event_replay_store=event_replay_store,
        event_replay_limit=event_replay_limit,
        event_replay_poll_interval_seconds=event_replay_poll_interval_seconds,
        event_replay_idle_polls=event_replay_idle_polls,
        host_pool=host_pool,
        select=_select,
        resolve=_resolve,
        read_upload_available=_read_upload_available,
        build_blocks=_build_blocks,
        check_output_schema=_check_output_schema,
        require_session=_require,
        owned_or_404=_owned_or_404,
        agent_control_host_or_404=_agent_control_host_or_404,
    )

    app.include_router(interaction_router(state, app))
    app.include_router(sessions_router(state))
    app.include_router(cost_router(state))
    app.include_router(misc_router(state))
    app.include_router(inspection_router(state))
    app.include_router(capabilities_router(state))
    app.include_router(model_files_router(state))
    return app
