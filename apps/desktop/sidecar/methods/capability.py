"""Host-only capability management RPC (083 Wave 4, T020/T021/T022).

MCP / skills / memory over public ``LoopPlaneHost`` methods only. Every
response is a field-by-field allowlist projection: no endpoint URL, header,
token, credential, owner id, raw problem text, or path ever reaches the
renderer (FR-006–FR-008, FR-016, FR-018). Every durable mutation takes the
profile mutation lease under a main-generated mutation id and refuses busy
rather than queueing (FR-017).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from loopplane.host import LoopPlaneHost

try:
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..protocol import RpcError
except ImportError:  # pragma: no cover - script-path load
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
_BUSY = RpcError(
    code=-32004,
    message="Busy",
    category="busy",
    retryable=False,
    message_key="desktop.error.busy",
)
_UNAVAILABLE = RpcError(
    code=-32008,
    message="Unavailable",
    category="unavailable",
    retryable=False,
    message_key="desktop.error.unavailable",
)

_UNAVAILABLE_REASON = "capability.unavailable"
# Desktop manages network MCP only; stdio command/args never cross this surface.
_MCP_TRANSPORTS = frozenset({"http", "sse", "websocket"})


def _require_mutation_id(params: Mapping[str, Any]) -> str:
    mid = params.get("mutation_id")
    if not isinstance(mid, str) or not mid.strip():
        raise _INVALID
    return mid


def _require_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _INVALID
    return value


def _optional_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    return value if isinstance(value, str) else ""


def _status_and_reason(record: Any) -> tuple[str, str | None]:
    # Only an explicit "unavailable" earns the reason: healthy MCP records
    # report "connected", and an unknown future status must not be mislabeled.
    status = str(getattr(record, "status", "unknown") or "unknown")
    return status, _UNAVAILABLE_REASON if status == "unavailable" else None


def _mcp_view(record: Any) -> dict[str, Any]:
    status, reason = _status_and_reason(record)
    transport = getattr(record, "transport", None)
    return {
        "id": str(record.id),
        "name": str(record.name),
        "status": status,
        "tool_count": int(getattr(record, "tool_count", 0) or 0),
        "transport": str(transport) if transport else None,
        "tools": [str(tool) for tool in (getattr(record, "tools", ()) or ())],
        "scope": str(getattr(record, "scope", "owned") or "owned"),
        "actions": [str(a) for a in (getattr(record, "actions", ()) or ())],
        "reason": reason,
    }


def _skill_view(record: Any) -> dict[str, Any]:
    status, reason = _status_and_reason(record)
    return {
        "id": str(record.id),
        "name": str(record.name),
        "description": str(getattr(record, "description", "") or ""),
        "status": status,
        "scope": str(getattr(record, "scope", "owned") or "owned"),
        "actions": [str(a) for a in (getattr(record, "actions", ()) or ())],
        "reason": reason,
    }


def _memory_view(record: Any) -> dict[str, Any]:
    status, reason = _status_and_reason(record)
    return {
        "id": str(record.id),
        "name": str(record.name),
        "kind": str(getattr(record, "kind", "") or ""),
        "description": str(getattr(record, "description", "") or ""),
        "snippet": str(getattr(record, "snippet", "") or "")[:512],
        "status": status,
        "scope": str(getattr(record, "scope", "owned") or "owned"),
        "actions": [str(a) for a in (getattr(record, "actions", ()) or ())],
        "reason": reason,
    }


def _operation_view(result: Any) -> dict[str, Any]:
    return {
        "ok": bool(getattr(result, "ok", False)),
        "message": str(getattr(result, "message", "") or ""),
    }


class CapabilityMethods:
    """Registerable handlers for MCP / skill / memory capability RPC."""

    def __init__(
        self,
        host: LoopPlaneHost,
        *,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
        mutation_lease: ProfileMutationLease | None = None,
    ) -> None:
        self._host = host
        self._principal_id = principal_id
        self._principal_provider = principal_provider
        self._mutation_lease = mutation_lease

    def _principal(self) -> str | None:
        if self._principal_provider is not None:
            return self._principal_provider()
        return self._principal_id

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "mcp.list": self.mcp_list,
            "mcp.get": self.mcp_get,
            "mcp.upsert": self.mcp_upsert,
            "mcp.reconnect": self.mcp_reconnect,
            "mcp.delete": self.mcp_delete,
            "skill.list": self.skill_list,
            "skill.get": self.skill_get,
            "skill.write": self.skill_write,
            "skill.import": self.skill_import,
            "skill.delete": self.skill_delete,
            "memory.list": self.memory_list,
            "memory.get": self.memory_get,
            "memory.write": self.memory_write,
            "memory.delete": self.memory_delete,
        }

    # --- lease discipline (FR-017) ---

    def _acquire(self, mutation_id: str) -> None:
        if self._mutation_lease is None:
            return
        try:
            self._mutation_lease.require_free_or_owner("capability", mutation_id)
            self._mutation_lease.acquire("capability", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc

    def _release(self, mutation_id: str) -> None:
        if self._mutation_lease is None:
            return
        self._mutation_lease.release("capability", mutation_id)

    # --- MCP (FR-006) ---

    async def mcp_list(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        try:
            records = self._host.list_managed_mcp(self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {"items": [_mcp_view(record) for record in records]}

    async def mcp_get(self, params: dict[str, Any]) -> dict[str, Any]:
        mcp_id = _require_str(params, "mcp_id")
        try:
            record = self._host.get_managed_mcp(mcp_id, principal_id=self._principal())
        except Exception as exc:
            raise _NOT_FOUND from exc
        return _mcp_view(record)

    async def mcp_upsert(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        name = _require_str(params, "name")
        transport = _require_str(params, "transport")
        if transport not in _MCP_TRANSPORTS:
            raise _INVALID
        url = _require_str(params, "url")
        self._acquire(mutation_id)
        try:
            result = await self._host.upsert_managed_mcp(
                name=name,
                transport=transport,  # type: ignore[arg-type]
                url=url,
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def mcp_reconnect(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        mcp_id = _require_str(params, "mcp_id")
        self._acquire(mutation_id)
        try:
            result = await self._host.reconnect_managed_mcp(
                mcp_id, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def mcp_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        mcp_id = _require_str(params, "mcp_id")
        self._acquire(mutation_id)
        try:
            result = await self._host.delete_managed_mcp(
                mcp_id, confirm=True, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    # --- Skills (FR-007) ---

    async def skill_list(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        try:
            records = self._host.list_managed_skills(self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {"items": [_skill_view(record) for record in records]}

    async def skill_get(self, params: dict[str, Any]) -> dict[str, Any]:
        skill_id = _require_str(params, "skill_id")
        try:
            record = self._host.get_managed_skill(
                skill_id, principal_id=self._principal()
            )
        except Exception as exc:
            raise _NOT_FOUND from exc
        view = _skill_view(record)
        view["instructions"] = str(getattr(record, "instructions", "") or "")
        return view

    async def skill_write(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        name = _require_str(params, "name")
        instructions = _require_str(params, "instructions")
        description = _optional_str(params, "description")
        self._acquire(mutation_id)
        try:
            result = self._host.write_managed_skill(
                name=name,
                description=description,
                instructions=instructions,
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def skill_import(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        name = _require_str(params, "name")
        instructions = _require_str(params, "instructions")
        description = _optional_str(params, "description")
        self._acquire(mutation_id)
        try:
            result = self._host.import_managed_skill(
                {
                    "name": name,
                    "description": description,
                    "instructions": instructions,
                },
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def skill_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        skill_id = _require_str(params, "skill_id")
        self._acquire(mutation_id)
        try:
            result = self._host.delete_managed_skill(
                skill_id, confirm=True, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    # --- Memory (FR-008; search stays a renderer-side filter) ---

    async def memory_list(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        try:
            records = self._host.list_managed_memory(principal_id=self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {"items": [_memory_view(record) for record in records]}

    async def memory_get(self, params: dict[str, Any]) -> dict[str, Any]:
        memory_id = _require_str(params, "memory_id")
        try:
            record = self._host.get_managed_memory(
                memory_id, principal_id=self._principal()
            )
        except Exception as exc:
            raise _NOT_FOUND from exc
        view = _memory_view(record)
        view["content"] = str(getattr(record, "content", "") or "")
        return view

    async def memory_write(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        name = _require_str(params, "name")
        kind = _require_str(params, "kind")
        content = _require_str(params, "content")
        description = _optional_str(params, "description")
        self._acquire(mutation_id)
        try:
            result = self._host.write_managed_memory(
                name=name,
                kind=kind,
                description=description,
                content=content,
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def memory_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        memory_id = _require_str(params, "memory_id")
        self._acquire(mutation_id)
        try:
            result = self._host.delete_managed_memory(
                memory_id, confirm=True, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)
