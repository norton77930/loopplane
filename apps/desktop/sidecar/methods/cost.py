"""Host-only cost projection RPC (083 Wave 1, T002).

Reads public LoopPlaneHost methods only. ``session_cost`` and ``monthly_spend``
carry exact ``Decimal`` figures or ``None``; the unpriced / partially-priced /
unknown distinction comes from the ``budget.pricing`` literal on the host's
agent-controls projection, because ``session_cost`` alone cannot express it.
Host failures degrade to explicit absence — never an error, never a marker.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

from loopplane.host import LoopPlaneHost

try:
    from ..protocol import RpcError
except ImportError:  # pragma: no cover
    from protocol import RpcError  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]

_INVALID = RpcError(
    code=-32602,
    message="Invalid params",
    category="invalid_params",
    retryable=False,
    message_key="desktop.error.invalid_params",
)
_NOT_FOUND = RpcError(
    code=-32002,
    message="Not found",
    category="not_found",
    retryable=False,
    message_key="desktop.error.not_found",
)

_PRICING_STATES = frozenset({"priced", "partially_unpriced", "unpriced", "unknown"})


class CostMethods:
    """Public-safe session and month-to-date spend projections (read-only)."""

    def __init__(
        self,
        host: LoopPlaneHost,
        *,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._host = host
        self._principal_id = principal_id
        self._principal_provider = principal_provider

    def _principal(self) -> str | None:
        if self._principal_provider is not None:
            return self._principal_provider()
        return self._principal_id

    def _is_owned_session(self, session_id: str) -> bool:
        principal_id = self._principal()
        return any(
            summary.session_id == session_id
            and (principal_id is None or summary.principal_id in (None, principal_id))
            for summary in self._host.list_sessions()
        )

    def handlers(self) -> dict[str, MethodHandler]:
        return {"cost.get": self.cost_get}

    def _session_view(self, session_id: str) -> dict[str, Any]:
        try:
            cost = self._host.session_cost(session_id)
        except Exception:
            cost = None
        if not isinstance(cost, Decimal):
            return {"status": "unavailable", "usd": None}
        try:
            budget = getattr(self._host.agent_controls(session_id), "budget", None)
            pricing = getattr(budget, "pricing", "unknown")
        except Exception:
            pricing = "unknown"
        if pricing not in _PRICING_STATES:
            pricing = "unknown"
        return {"status": pricing, "usd": str(cost)}

    def _monthly_view(self) -> dict[str, Any]:
        principal_id = self._principal()
        if principal_id is None:
            return {"status": "unavailable", "usd": None}
        try:
            spend = self._host.monthly_spend(principal_id)
        except Exception:
            spend = None
        if not isinstance(spend, Decimal):
            return {"status": "unavailable", "usd": None}
        return {"status": "available", "usd": str(spend)}

    async def cost_get(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise _INVALID
        session_view: dict[str, Any] = {"status": "unavailable", "usd": None}
        if isinstance(session_id, str) and session_id.strip():
            if not self._is_owned_session(session_id):
                raise _NOT_FOUND
            session_view = self._session_view(session_id)
        return {"session": session_view, "monthly": self._monthly_view()}
