"""Misc routes for the WebAPI app factory."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from loopplane.commands import CommandContext
from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.models import (
    ArtifactContent,
    CommandRequest,
    CommandResultView,
    Resolved,
)
from loopplane.webapi.routers.context import RouterState


def build_router(state: RouterState) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    host = state.host
    require = state.require
    catalog = state.catalog
    command_registry = state.command_registry
    # 079: which commands read one conversation, declared by the registry itself
    # so this gate cannot drift from the command set (see POST /commands).
    session_scoped_commands = command_registry.session_scoped_names()
    _owned_or_404 = state.owned_or_404

    @router.post("/commands")
    async def run_command(
        body: CommandRequest, principal: Principal = Depends(require)
    ) -> CommandResultView:
        # 065: dispatch a backend slash command against EXISTING host seams (never
        # the gateway/event bus). Session-scoped commands require ownership; the
        # result is public-safe (the caller's own data only).
        #
        # 079: this used to be a hardcoded ("cost", "compact") list, and adding a
        # session-scoped command to the shared registry silently made it reachable
        # here WITHOUT a gate — a cross-principal disclosure. The registry now
        # declares which commands are session-scoped, so the gate cannot fall out
        # of step with the command set. The handlers filter by principal as well,
        # so a host that skips this gate degrades to "not found" rather than
        # leaking; this remains the authoritative check.
        line = body.command if body.command.startswith("/") else f"/{body.command}"
        name = line[1:].strip().split(" ", 1)[0].lower()
        if name in session_scoped_commands:
            if body.session_id is None:
                raise HTTPException(status_code=400, detail="session_id required")
            _owned_or_404(body.session_id, principal)
        ctx = CommandContext(
            host=host,
            principal_id=principal.id,
            session_id=body.session_id,
            models=tuple(catalog),
        )
        result = command_registry.dispatch(line, ctx)
        return CommandResultView(kind=result.kind, text=result.text)

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

    return router
