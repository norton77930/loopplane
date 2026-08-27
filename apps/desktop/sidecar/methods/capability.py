"""Host-only capability management RPC (083 Wave 4, T020/T021/T022).

MCP / skills / memory over public ``LoopPlaneHost`` methods only. Every
response is a field-by-field allowlist projection: no endpoint URL, header,
token, credential, owner id, raw problem text, or path ever reaches the
renderer (FR-006–FR-008, FR-016, FR-018). Every durable mutation takes the
profile mutation lease under a main-generated mutation id and refuses busy
rather than queueing (FR-017).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from loopplane.adapters.mcp import AuthorizationResult, StoredAuthorizationMaterial
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
_AUTHORIZATION_REQUEST_TTL_SECONDS = 360.0


def _material_payload(material: StoredAuthorizationMaterial) -> str:
    """Serialize SDK-owned models without formatting or logging their values."""

    def model_value(value: Any) -> object | None:
        if value is None:
            return None
        dump = getattr(value, "model_dump", None)
        if not callable(dump):
            raise ValueError("authorization material is invalid")
        return dump(mode="json")

    return json.dumps(
        {
            "v": 1,
            "tokens": model_value(material.tokens),
            "client_info": model_value(material.client_info),
            "expires_at": material.expires_at,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _material_version(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_material(payload: str) -> StoredAuthorizationMaterial:
    """Restore the opaque vault payload; every rejection stays public-safe."""

    try:
        from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

        parsed = json.loads(payload)
        if not isinstance(parsed, dict) or parsed.get("v") != 1:
            raise ValueError
        if set(parsed) != {"v", "tokens", "client_info", "expires_at"}:
            raise ValueError
        token_value = parsed["tokens"]
        client_value = parsed["client_info"]
        expires_at = parsed["expires_at"]
        if expires_at is not None and (
            isinstance(expires_at, bool)
            or not isinstance(expires_at, (int, float))
            or not math.isfinite(float(expires_at))
        ):
            raise ValueError
        tokens = (
            OAuthToken.model_validate(token_value)
            if isinstance(token_value, dict)
            else None
        )
        client_info = (
            OAuthClientInformationFull.model_validate(client_value)
            if isinstance(client_value, dict)
            else None
        )
        if token_value is not None and tokens is None:
            raise ValueError
        if client_value is not None and client_info is None:
            raise ValueError
        return StoredAuthorizationMaterial(
            tokens=tokens,
            client_info=client_info,
            expires_at=float(expires_at) if expires_at is not None else None,
        )
    except (ImportError, KeyError, TypeError, ValueError):
        raise _INVALID from None


def _is_loopback_redirect(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "::1"}
            and parsed.port is not None
            and bool(parsed.path)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False


@dataclass
class _AuthorizationRequest:
    request_id: str
    principal: str | None
    server: str
    redirect_uri: str
    created_at: float
    url: str | None = None
    result: AuthorizationResult | None = None
    completion_delivered: bool = False
    state: str = "awaiting"
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None
    expiry: asyncio.TimerHandle | None = None
    acquire: Callable[[], None] | None = None
    release: Callable[[], None] | None = None
    lease_held: bool = False


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
    interactive = getattr(record, "authorization", None) == "interactive"
    authorization_state = (
        "authorized"
        if not interactive or status == "connected"
        else "needs_authorization"
        if status == "needs_authorization"
        else "failed"
    )
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
        "authorization": {
            "server": str(record.id),
            "mode": "interactive" if interactive else "none",
            "state": authorization_state,
        },
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


class DesktopMcpOAuth:
    """Sidecar implementation of the two runtime OAuth Protocols.

    Material is process-local here. Electron main is the only durable owner and
    receives the serialized value only through the private stdio RPC.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str | None, str], StoredAuthorizationMaterial] = {}
        self._versions: dict[tuple[str | None, str], str] = {}
        self._requests: dict[str, _AuthorizationRequest] = {}
        self._active: dict[tuple[str | None, str], str] = {}
        self._active_server: dict[str, str] = {}

    def _request_for_server(self, server: str) -> _AuthorizationRequest:
        request_id = self._active_server.get(server)
        request = self._requests.get(request_id or "")
        if request is None:
            raise RuntimeError("authorization request is unavailable")
        return request

    def redirect_uri(self, *, server: str) -> str:
        return self._request_for_server(server).redirect_uri

    async def present(self, url: str, *, server: str, principal: str | None) -> None:
        request = self._request_for_server(server)
        if request.principal != principal or request.state != "awaiting":
            raise RuntimeError("authorization request is unavailable")
        request.url = url

    async def await_result(
        self, *, server: str, principal: str | None
    ) -> AuthorizationResult:
        request = self._request_for_server(server)
        if request.principal != principal:
            raise RuntimeError("authorization request is unavailable")
        await request.ready.wait()
        if request.acquire is not None:
            request.acquire()
            request.lease_held = True
        result = request.result
        request.result = None
        if result is None:
            raise RuntimeError("authorization request is unavailable")
        return result

    async def load(
        self, *, principal: str | None, server: str
    ) -> StoredAuthorizationMaterial | None:
        return self._entries.get((principal, server))

    async def save(
        self,
        *,
        principal: str | None,
        server: str,
        material: StoredAuthorizationMaterial,
    ) -> None:
        payload = _material_payload(material)
        key = (principal, server)
        self._entries[key] = material
        self._versions[key] = _material_version(payload)

    async def discard(self, *, principal: str | None, server: str) -> None:
        key = (principal, server)
        self._entries.pop(key, None)
        self._versions.pop(key, None)

    def import_material(self, principal: str | None, server: str, payload: str) -> None:
        material = _parse_material(payload)
        key = (principal, server)
        self._entries[key] = material
        self._versions[key] = _material_version(_material_payload(material))

    def snapshot(self, principal: str | None, server: str) -> tuple[str, str] | None:
        material = self._entries.get((principal, server))
        if material is None:
            return None
        payload = _material_payload(material)
        return payload, self._versions[(principal, server)]

    def _forget_active(self, request: _AuthorizationRequest) -> None:
        key = (request.principal, request.server)
        if self._active.get(key) == request.request_id:
            self._active.pop(key, None)
        if self._active_server.get(request.server) == request.request_id:
            self._active_server.pop(request.server, None)

    def _cleanup(self) -> None:
        now = time.monotonic()
        for request_id, request in tuple(self._requests.items()):
            if now - request.created_at <= _AUTHORIZATION_REQUEST_TTL_SECONDS:
                continue
            self._expire(request_id)

    def _expire(self, request_id: str) -> None:
        request = self._requests.pop(request_id, None)
        if request is None:
            return
        if request.expiry is not None:
            request.expiry.cancel()
            request.expiry = None
        if request.task is not None and not request.task.done():
            request.task.cancel()
        self._forget_active(request)

    async def _run(
        self,
        request: _AuthorizationRequest,
        connect: Callable[[], Awaitable[Any]],
    ) -> None:
        try:
            result = await connect()
            request.state = (
                "authorized"
                if bool(getattr(result, "ok", False))
                and self.snapshot(request.principal, request.server) is not None
                else "failed"
            )
        except asyncio.CancelledError:
            request.state = "failed"
            raise
        except Exception:
            request.state = "failed"
        finally:
            self._forget_active(request)
            if request.lease_held and request.release is not None:
                request.release()
                request.lease_held = False

    def start_authorization(
        self,
        *,
        principal: str | None,
        server: str,
        redirect_uri: str,
        connect: Callable[[], Awaitable[Any]],
        acquire: Callable[[str], None] | None = None,
        release: Callable[[str], None] | None = None,
    ) -> str:
        self._cleanup()
        key = (principal, server)
        if key in self._active or server in self._active_server:
            raise _BUSY
        if not _is_loopback_redirect(redirect_uri):
            raise _INVALID
        request_id = secrets.token_urlsafe(24)
        request = _AuthorizationRequest(
            request_id=request_id,
            principal=principal,
            server=server,
            redirect_uri=redirect_uri,
            created_at=time.monotonic(),
            acquire=(lambda: acquire(request_id)) if acquire is not None else None,
            release=(lambda: release(request_id)) if release is not None else None,
        )
        try:
            self._requests[request_id] = request
            self._active[key] = request_id
            self._active_server[server] = request_id
            request.task = asyncio.create_task(
                self._run(request, connect),
                name=f"mcp-authorize-{request_id}",
            )
            request.expiry = asyncio.get_running_loop().call_later(
                _AUTHORIZATION_REQUEST_TTL_SECONDS,
                self._expire,
                request_id,
            )
        except Exception:
            self._expire(request_id)
            if request.lease_held and request.release is not None:
                request.release()
                request.lease_held = False
            raise
        return request_id

    def authorization_status(self, request_id: str) -> dict[str, Any]:
        self._cleanup()
        request = self._requests.get(request_id)
        if request is None:
            raise _NOT_FOUND
        if request.state == "awaiting":
            answer: dict[str, Any] = {"state": "awaiting"}
            if request.url is not None:
                answer["url"] = request.url
            return answer
        self._requests.pop(request_id, None)
        if request.expiry is not None:
            request.expiry.cancel()
            request.expiry = None
        if request.state != "authorized":
            return {"state": "failed"}
        snapshot = self.snapshot(request.principal, request.server)
        if snapshot is None:
            return {"state": "failed"}
        material, version = snapshot
        return {
            "state": "authorized",
            "principal": request.principal,
            "material": material,
            "version": version,
        }

    def complete_authorization(self, request_id: str, *, code: str, state: str) -> None:
        self._cleanup()
        request = self._requests.get(request_id)
        if (
            request is None
            or request.state != "awaiting"
            or request.completion_delivered
        ):
            raise _NOT_FOUND
        request.completion_delivered = True
        request.result = AuthorizationResult(code=code, state=state)
        request.ready.set()

    async def aclose(self) -> None:
        for request in self._requests.values():
            if request.expiry is not None:
                request.expiry.cancel()
                request.expiry = None
        tasks = [
            request.task
            for request in self._requests.values()
            if request.task is not None and not request.task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._requests.clear()
        self._active.clear()
        self._active_server.clear()

    def __repr__(self) -> str:
        return (
            "DesktopMcpOAuth("
            f"entries={len(self._entries)}, requests={len(self._requests)})"
        )

    __str__ = __repr__


class CapabilityMethods:
    """Registerable handlers for MCP / skill / memory capability RPC."""

    def __init__(
        self,
        host: LoopPlaneHost,
        *,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
        mutation_lease: ProfileMutationLease | None = None,
        mcp_oauth: DesktopMcpOAuth | None = None,
    ) -> None:
        self._host = host
        self._principal_id = principal_id
        self._principal_provider = principal_provider
        self._mutation_lease = mutation_lease
        self._mcp_oauth = mcp_oauth if mcp_oauth is not None else DesktopMcpOAuth()

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
            "mcp.authorize": self.mcp_authorize,
            "mcp.authorize_status": self.mcp_authorize_status,
            "mcp.authorize_complete": self.mcp_authorize_complete,
            "mcp.material": self.mcp_material,
            "mcp.disconnect": self.mcp_disconnect,
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

    async def aclose(self) -> None:
        await self._mcp_oauth.aclose()

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

    async def mcp_authorize(self, params: dict[str, Any]) -> dict[str, Any]:
        mcp_id = _require_str(params, "mcp_id")
        redirect_uri = _require_str(params, "redirect_uri")
        principal = self._principal()

        async def connect() -> Any:
            return await self._host.reconnect_managed_mcp(
                mcp_id, principal_id=principal
            )

        request_id = self._mcp_oauth.start_authorization(
            principal=principal,
            server=mcp_id,
            redirect_uri=redirect_uri,
            connect=connect,
            acquire=self._acquire,
            release=self._release,
        )
        return {"request_id": request_id}

    async def mcp_authorize_status(self, params: dict[str, Any]) -> dict[str, Any]:
        request_id = _require_str(params, "request_id")
        return self._mcp_oauth.authorization_status(request_id)

    async def mcp_authorize_complete(self, params: dict[str, Any]) -> dict[str, Any]:
        request_id = _require_str(params, "request_id")
        code = _require_str(params, "code")
        state = _require_str(params, "state")
        self._mcp_oauth.complete_authorization(
            request_id,
            code=code,
            state=state,
        )
        return {"ok": True}

    async def mcp_material(self, params: dict[str, Any]) -> dict[str, Any]:
        mcp_id = _require_str(params, "mcp_id")
        known_version = params.get("known_version")
        if known_version is not None and not isinstance(known_version, str):
            raise _INVALID
        snapshot = self._mcp_oauth.snapshot(self._principal(), mcp_id)
        if snapshot is None:
            return {
                "principal": self._principal(),
                "version": None,
                "material": None,
            }
        material, version = snapshot
        return {
            "principal": self._principal(),
            "version": version,
            "material": None if known_version == version else material,
        }

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
        mcp_id = name.strip()
        transport = _require_str(params, "transport")
        if transport not in _MCP_TRANSPORTS:
            raise _INVALID
        url = _require_str(params, "url")
        authorization = params.get("authorization")
        if authorization is not None and authorization != "interactive":
            raise _INVALID
        principal = self._principal()
        existing: Any | None = None
        try:
            existing = self._host.get_managed_mcp(mcp_id, principal_id=principal)
        except Exception:
            # A new record has no prior endpoint identity to invalidate.
            pass
        authorization_reset = existing is not None and (
            getattr(existing, "transport", None),
            getattr(existing, "url", None),
            getattr(existing, "authorization", None),
        ) != (transport, url, authorization)
        self._acquire(mutation_id)
        try:
            result = await self._host.upsert_managed_mcp(
                name=mcp_id,
                transport=transport,  # type: ignore[arg-type]
                url=url,
                principal_id=principal,
                authorization=authorization,
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        view = _operation_view(result)
        if view["ok"] and authorization_reset:
            await self._mcp_oauth.discard(principal=principal, server=mcp_id)
            view["authorization_reset"] = True
        return view

    async def mcp_reconnect(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        mcp_id = _require_str(params, "mcp_id")
        principal = self._principal()
        self._acquire(mutation_id)
        try:
            if "material" in params:
                material = _require_str(params, "material")
                try:
                    record = self._host.get_managed_mcp(mcp_id, principal_id=principal)
                except Exception as exc:
                    raise _NOT_FOUND from exc
                if getattr(record, "authorization", None) != "interactive":
                    raise _INVALID
                self._mcp_oauth.import_material(principal, mcp_id, material)
            result = await self._host.reconnect_managed_mcp(
                mcp_id, principal_id=principal
            )
        except RpcError:
            raise
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def mcp_disconnect(self, params: dict[str, Any]) -> dict[str, Any]:
        """Deactivate an interactive server while retaining its configuration."""

        mutation_id = _require_mutation_id(params)
        mcp_id = _require_str(params, "mcp_id")
        principal = self._principal()
        self._acquire(mutation_id)
        try:
            try:
                record = self._host.get_managed_mcp(mcp_id, principal_id=principal)
            except Exception as exc:
                raise _NOT_FOUND from exc
            transport = getattr(record, "transport", None)
            url = getattr(record, "url", None)
            if (
                getattr(record, "authorization", None) != "interactive"
                or transport not in {"http", "sse"}
                or not isinstance(url, str)
                or not url
            ):
                raise _INVALID
            result = await self._host.upsert_managed_mcp(
                name=mcp_id,
                transport=transport,
                url=url,
                principal_id=principal,
                authorization="interactive",
            )
            if bool(getattr(result, "ok", False)):
                await self._mcp_oauth.discard(principal=principal, server=mcp_id)
        except RpcError:
            raise
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def mcp_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        mcp_id = _require_str(params, "mcp_id")
        principal = self._principal()
        self._acquire(mutation_id)
        try:
            result = await self._host.delete_managed_mcp(
                mcp_id, confirm=True, principal_id=principal
            )
            if bool(getattr(result, "ok", False)):
                await self._mcp_oauth.discard(principal=principal, server=mcp_id)
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
