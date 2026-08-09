"""Sessions routes for the WebAPI app factory."""

from __future__ import annotations

from contextlib import suppress

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.models import (
    BulkDeleteRequest,
    BulkDeleteResult,
    ForkSessionRequest,
    HistoryEntryView,
    OpenedSession,
    RenameRequest,
    Resolved,
    SessionContextBindRequest,
    SessionContextView,
    SessionSummaryView,
)
from loopplane.webapi.routers.context import RouterState


def build_router(state: RouterState) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    host = state.host
    require = state.require
    sessions = state.sessions
    event_replay_store = state.event_replay_store
    _owned_or_404 = state.owned_or_404

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

    @router.get("/sessions/search")
    async def search_sessions(
        q: str, principal: Principal = Depends(require)
    ) -> list[SessionSummaryView]:
        return [
            SessionSummaryView.from_summary(summary)
            for summary in host.search_sessions(q, principal.id)
        ]

    @router.post("/sessions/bulk-delete")
    async def bulk_delete_sessions(
        body: BulkDeleteRequest, principal: Principal = Depends(require)
    ) -> BulkDeleteResult:
        deleted = host.bulk_delete_sessions(body.session_ids, principal_id=principal.id)
        for session_id in deleted:
            entry = sessions.get(session_id)
            if entry is not None:
                entry.session.cancel()
                entry.close.set()
            if event_replay_store is not None:
                with suppress(Exception):
                    event_replay_store.delete_session(session_id)
        return BulkDeleteResult(deleted=deleted)

    @router.post("/sessions/{session_id}/star")
    async def star_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        _owned_or_404(session_id, principal)
        await host.set_session_starred(session_id, True)
        return Resolved(resolved=True)

    @router.delete("/sessions/{session_id}/star")
    async def unstar_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        _owned_or_404(session_id, principal)
        await host.set_session_starred(session_id, False)
        return Resolved(resolved=True)

    @router.post("/sessions/{session_id}/context")
    async def bind_session_context(
        session_id: str,
        body: SessionContextBindRequest,
        principal: Principal = Depends(require),
    ) -> SessionContextView:
        _owned_or_404(session_id, principal)
        try:
            binding = await host.bind_session_context(
                session_id, body.context_id, principal_id=principal.id
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return SessionContextView.from_binding(binding)

    @router.post("/sessions/{session_id}/fork")
    async def fork_session(
        session_id: str,
        body: ForkSessionRequest,
        principal: Principal = Depends(require),
    ) -> OpenedSession:
        _owned_or_404(session_id, principal)
        try:
            fork_id = await host.fork_session(
                session_id,
                principal_id=principal.id,
                source_sequence=body.sequence,
                title=body.title,
                model=body.model,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return OpenedSession(session_id=fork_id)

    @router.patch("/sessions/{session_id}")
    async def rename_session(
        session_id: str,
        body: RenameRequest,
        principal: Principal = Depends(require),
    ) -> Resolved:
        # Rename a session the caller owns (030); non-owner / unknown -> 404.
        _owned_or_404(session_id, principal)
        try:
            await host.set_session_title(session_id, body.title)
        except (KeyError, RuntimeError):
            raise HTTPException(status_code=404, detail="not found") from None
        return Resolved(resolved=True)

    @router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str, principal: Principal = Depends(require)
    ) -> Resolved:
        # Delete a session the caller owns (030): cancel a live entry first, then
        # remove the durable records. Non-owner / unknown -> 404.
        _owned_or_404(session_id, principal)
        entry = sessions.get(session_id)
        if entry is not None:
            entry.session.cancel()
            entry.close.set()
        host.delete_session(session_id)
        if event_replay_store is not None:
            with suppress(Exception):
                event_replay_store.delete_session(session_id)
        return Resolved(resolved=True)

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

    return router
