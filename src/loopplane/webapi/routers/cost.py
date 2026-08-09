"""Cost routes for the WebAPI app factory."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.models import (
    MonthlyCostView,
    SessionCostView,
)
from loopplane.webapi.routers.context import RouterState


def build_router(state: RouterState) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    host = state.host
    require = state.require
    _owned_or_404 = state.owned_or_404

    @router.get("/sessions/{session_id}/cost")
    async def session_cost(
        session_id: str, principal: Principal = Depends(require)
    ) -> SessionCostView:
        # 064: a session's accumulated USD (owner-only; 404 otherwise). null when no
        # budget is configured ("not tracked"). Read-only; mirrors inspection routes.
        _owned_or_404(session_id, principal)
        try:
            spent = host.session_cost(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return SessionCostView.of(session_id, spent)

    @router.get("/cost/monthly")
    async def monthly_cost(
        principal: Principal = Depends(require),
    ) -> MonthlyCostView:
        # 064: the CALLER's own current-month USD (never another principal's). null
        # when no durable ledger is configured. Read-only.
        month = datetime.now(UTC).strftime("%Y-%m")
        spent = host.monthly_spend(principal.id)
        return MonthlyCostView.of(principal.id, month, spent)

    return router
