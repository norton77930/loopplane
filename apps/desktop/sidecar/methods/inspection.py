"""Host-only inspection / agent-controls / capabilities RPC (078 T064).

Reads public LoopPlaneHost facades only — never gateway invoke or private config.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from loopplane.host import LoopPlaneHost

try:
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..protocol import RpcError
except ImportError:  # pragma: no cover
    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )
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
_UNAVAILABLE = RpcError(
    code=-32008,
    message="Unavailable",
    category="unavailable",
    retryable=False,
    message_key="desktop.error.unavailable",
)
_BUSY = RpcError(
    code=-32004,
    message="Busy",
    category="busy",
    retryable=False,
    message_key="desktop.error.busy",
)


def _public(obj: Any) -> Any:
    if obj is None:
        return None
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _public(v) for k, v in asdict(obj).items()}
    if isinstance(obj, tuple):
        return [_public(x) for x in obj]
    if isinstance(obj, list):
        return [_public(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _public(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


class InspectionMethods:
    def __init__(
        self,
        host: LoopPlaneHost,
        *,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
        mutation_lease: ProfileMutationLease | None = None,
        configured_model_id: str | None = None,
    ) -> None:
        self._host = host
        self._principal_id = principal_id
        self._principal_provider = principal_provider
        self._mutation_lease = mutation_lease
        self._configured_model_id = configured_model_id

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
        return {
            "inspection.get": self.inspection_get,
            "agentControls.get": self.agent_controls_get,
            "capabilities.list": self.capabilities_list,
            "capabilities.invokeAction": self.capabilities_invoke,
        }

    async def inspection_get(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise _INVALID
        if isinstance(session_id, str) and not self._is_owned_session(session_id):
            raise _NOT_FOUND
        try:
            skills = self._host.inspect_skills()
            tools = self._host.inspect_tools()
            mcp = self._host.inspect_mcp()
            memory = self._host.inspect_memory()
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {
            "session_id": session_id,
            "skills": [
                {"name": getattr(s, "name", str(s)), "available": True} for s in skills
            ],
            "tools": [
                {"name": getattr(t, "name", str(t)), "available": True} for t in tools
            ],
            "mcp": [
                {"name": getattr(m, "name", str(m)), "available": True} for m in mcp
            ],
            "memory": [
                {
                    "source": str(getattr(e, "source", "") or ""),
                    "snippet": str(getattr(e, "snippet", "") or "")[:512],
                }
                for e in memory
            ],
            "unavailable": False,
        }

    async def agent_controls_get(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise _INVALID
        if not self._is_owned_session(session_id):
            raise _NOT_FOUND
        try:
            proj = self._host.agent_controls(session_id)
        except Exception as exc:
            raise _NOT_FOUND from exc
        public = _public(proj)
        # Normalize to presentation-friendly shape
        permission = public.get("permission") if isinstance(public, dict) else {}
        budget = public.get("budget") if isinstance(public, dict) else {}
        if not isinstance(permission, dict):
            permission = {}
        if not isinstance(budget, dict):
            budget = {}
        return {
            "session_id": session_id,
            "default_mode": permission.get("default_mode"),
            "selectable_modes": permission.get("selectable_modes") or [],
            "active_run": permission.get("active_run"),
            "last_accepted_run": permission.get("last_accepted_run"),
            "budget": {
                "tracking": budget.get("tracking", "unknown"),
                "pricing": budget.get("pricing", "unknown"),
                "session_guard": budget.get("session_guard", "unknown"),
                "monthly_guard": budget.get("monthly_guard", "unknown"),
            },
            "actions": public.get("actions") if isinstance(public, dict) else [],
            "unavailable": False,
        }

    async def capabilities_list(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        try:
            status = self._host.capability_settings_status(
                principal_id=self._principal()
            )
            status_pub = _public(status)
        except Exception:
            status_pub = {}
        # 083: the durable cost domain (monthly ledger) is host configuration;
        # session spend is reported in-band by cost.get regardless of this card.
        ledger_available = False
        principal_id = self._principal()
        if principal_id is not None:
            try:
                ledger_available = self._host.monthly_spend(principal_id) is not None
            except Exception:
                ledger_available = False
        # Map Host settings status into safe capability cards. MCP management
        # needs the host's endpoint policy (CapabilitySettingsStatus has no
        # "mcp_available" field — reading one made this card permanently off).
        mcp_available = bool(
            isinstance(status_pub, dict)
            and status_pub.get("mcp_endpoint_policy_available", False)
        )
        schedule_runner = bool(
            isinstance(status_pub, dict)
            and status_pub.get("schedule_runner_available", False)
        )
        storage_available = bool(
            isinstance(status_pub, dict) and status_pub.get("storage_available", False)
        )
        model_default_available = bool(self._configured_model_id)
        capabilities = [
            {
                "id": "memory",
                "label": "Memory",
                "available": True,
                "actions": ["refresh"],
                "status": "available",
                "reason": None,
            },
            {
                "id": "skills",
                "label": "Skills",
                "available": True,
                "actions": ["refresh"],
                "status": "available",
                "reason": None,
            },
            {
                "id": "mcp",
                "label": "MCP",
                "available": mcp_available,
                "actions": [],
                "status": "available" if mcp_available else "unavailable",
                "reason": None if mcp_available else "capability.unavailable",
            },
            {
                "id": "agent_controls",
                "label": "Agent controls",
                "available": True,
                "actions": [],
                "status": "available",
                "reason": None,
            },
            {
                "id": "inspection",
                "label": "Inspection",
                "available": True,
                "actions": ["refresh"],
                "status": "available",
                "reason": None,
            },
            {
                "id": "schedules",
                "label": "Schedules",
                "available": schedule_runner,
                "actions": [],
                "status": "available" if schedule_runner else "unavailable",
                "reason": None if schedule_runner else "capability.unavailable",
            },
            {
                "id": "contexts",
                "label": "Workspace contexts",
                "available": storage_available,
                "actions": [],
                "status": "available" if storage_available else "unavailable",
                "reason": None if storage_available else "capability.unavailable",
            },
            {
                "id": "model_default",
                "label": "Model default",
                "available": model_default_available,
                "actions": [],
                "status": "available" if model_default_available else "unavailable",
                "reason": None if model_default_available else "capability.unavailable",
            },
            {
                "id": "cost",
                "label": "Cost",
                "available": ledger_available,
                "actions": [],
                "status": "available" if ledger_available else "unavailable",
                "reason": None if ledger_available else "cost.monthly_unavailable",
            },
        ]
        return {"capabilities": capabilities}

    async def capabilities_invoke(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = params.get("mutation_id")
        capability_id = params.get("capability_id") or params.get("capabilityId")
        action = params.get("action")
        if (
            not isinstance(mutation_id, str)
            or not mutation_id.strip()
            or not isinstance(capability_id, str)
            or not isinstance(action, str)
        ):
            raise _INVALID
        # Strict allowlist — no generic tool/MCP dispatch from presentation.
        allowed = {
            ("memory", "refresh"),
            ("skills", "refresh"),
            ("inspection", "refresh"),
        }
        if (capability_id, action) not in allowed:
            raise RpcError(
                code=-32008,
                message="Capability action unavailable",
                category="unavailable",
                retryable=False,
                message_key="desktop.error.capability_action_unavailable",
            )
        # Refresh is still a Host dispatch; protect it with the runtime-owned
        # mutation lease rather than trusting renderer-side policy.
        if self._mutation_lease is None:
            return await self.capabilities_list({})
        try:
            self._mutation_lease.require_free_or_owner("capability", mutation_id)
            self._mutation_lease.acquire("capability", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        try:
            return await self.capabilities_list({})
        finally:
            self._mutation_lease.release("capability", mutation_id)
