"""Pure JSON-RPC dispatcher for Desktop V1 (078 T024).

Zero Host/store/profile construction. Method providers are injected.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

try:
    from .protocol import (
        INTERNAL_FAILURE,
        INVALID_PARAMS,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        PARSE_ERROR,
        PROTOCOL_MAJOR,
        PROTOCOL_MINOR,
        PROTOCOL_NAME,
        RUNTIME_EVENT_SCHEMA,
        SERVER_NAME,
        SERVER_VERSION,
        RpcError,
        decode_frame,
        make_error,
        make_notification,
        make_result,
    )
except ImportError:  # pragma: no cover - script-path load
    from protocol import (  # type: ignore[no-redef]
        INTERNAL_FAILURE,
        INVALID_PARAMS,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        PARSE_ERROR,
        PROTOCOL_MAJOR,
        PROTOCOL_MINOR,
        PROTOCOL_NAME,
        RUNTIME_EVENT_SCHEMA,
        SERVER_NAME,
        SERVER_VERSION,
        RpcError,
        decode_frame,
        make_error,
        make_notification,
        make_result,
    )

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]
RequestId = str
RequestIdentity = tuple[str, str]
MAX_CACHED_REQUESTS = 64
_REQUEST_FIELDS = frozenset({"jsonrpc", "id", "method", "params"})

REQUESTED_CAPABILITIES = (
    "sessions",
    "interaction",
    "projects",
    "inspection",
    "workspace",
    "backup",
)
NOTIFICATIONS = (
    "runtime.event",
    "runtime.outcome",
    "runtime.state",
    "runtime.subscriptionClosed",
)
LIMITS = {
    "control_frame_bytes": 1_048_576,
    "runtime_event_frame_bytes": 8_388_608,
    "prompt_bytes": 65_536,
    "pending_requests": 64,
    "subscriptions": 8,
}


@dataclass(frozen=True, slots=True)
class CachedResponse:
    identity: RequestIdentity
    response: dict[str, Any]


@dataclass
class DispatcherState:
    initialized: bool = False
    shutdown: bool = False
    notification_seq: int = 0
    cached_responses: dict[RequestId, CachedResponse] = field(default_factory=dict)


class Dispatcher:
    """Initialize / request dispatch / notification sequencing (non-executable)."""

    def __init__(
        self,
        *,
        methods: dict[str, MethodHandler] | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> None:
        self._methods = methods or {}
        self._capabilities = capabilities or {
            capability: "unavailable" for capability in REQUESTED_CAPABILITIES
        }
        self.state = DispatcherState()

    def register(self, name: str, handler: MethodHandler) -> None:
        self._methods[name] = handler

    async def handle_frame(self, line: bytes | str) -> list[dict[str, Any]]:
        """Return one terminal response for one exact client request frame."""

        try:
            msg = decode_frame(line)
        except Exception:
            return [make_error(None, PARSE_ERROR)]

        req_id = self._safe_error_id(msg.get("id"))
        if (
            set(msg) != _REQUEST_FIELDS
            or msg.get("jsonrpc") != "2.0"
            or not self._valid_request_id(msg.get("id"))
            or not isinstance(msg.get("method"), str)
            or not msg["method"]
        ):
            return [make_error(req_id, INVALID_REQUEST)]

        method = msg["method"]
        req_id = msg["id"]
        params = msg["params"]
        if not isinstance(params, dict):
            return [make_error(req_id, INVALID_PARAMS)]

        identity = self._request_identity(method, params)
        if method == "initialize" and self.state.initialized:
            return [await self._initialize(req_id, params)]

        cached = self.state.cached_responses.get(req_id)
        if cached is not None:
            if cached.identity == identity:
                return [cached.response]
            return [
                make_error(
                    req_id,
                    RpcError(
                        code=-32003,
                        message="Conflict",
                        category="conflict",
                        retryable=False,
                        message_key="desktop.error.conflict",
                    ),
                )
            ]
        cached_requests = sum(
            cached.identity[0] != "initialize"
            for cached in self.state.cached_responses.values()
        )
        if method != "initialize" and cached_requests >= MAX_CACHED_REQUESTS:
            return [
                make_error(
                    req_id,
                    RpcError(
                        code=-32004,
                        message="Busy",
                        category="busy",
                        retryable=False,
                        message_key="desktop.error.busy",
                    ),
                )
            ]

        if self.state.shutdown:
            response = make_error(
                req_id,
                RpcError(
                    code=-32005,
                    message="Shutting down",
                    category="invalid_state",
                    retryable=False,
                    message_key="desktop.error.shutting_down",
                ),
            )
            return [self._cache(req_id, identity, response)]

        if method == "initialize":
            response = await self._initialize(req_id, params)
            return [self._cache(req_id, identity, response)]

        if method == "system.status":
            if not self.state.initialized:
                response = self._not_initialized(req_id)
            else:
                response = make_result(
                    req_id,
                    {
                        "ready": not self.state.shutdown,
                        "initialized": self.state.initialized,
                        "shutdown": self.state.shutdown,
                    },
                )
            return [self._cache(req_id, identity, response)]

        if not self.state.initialized:
            return [self._cache(req_id, identity, self._not_initialized(req_id))]

        if method == "system.shutdown":
            handler = self._methods.get(method)
            if handler is not None:
                response = await self._invoke(handler, req_id, params)
            else:
                response = make_result(req_id, {"ok": True})
            if "result" in response:
                self.state.shutdown = True
            return [self._cache(req_id, identity, response)]

        handler = self._methods.get(method)
        if handler is None:
            response = make_error(req_id, METHOD_NOT_FOUND)
        else:
            response = await self._invoke(handler, req_id, params)
        return [self._cache(req_id, identity, response)]

    @staticmethod
    def _valid_request_id(value: Any) -> bool:
        return (
            isinstance(value, str) and bool(value) and len(value.encode("utf-8")) <= 128
        )

    @classmethod
    def _safe_error_id(cls, value: Any) -> RequestId | None:
        return value if cls._valid_request_id(value) else None

    @staticmethod
    def _request_identity(method: str, params: dict[str, Any]) -> RequestIdentity:
        canonical_params = json.dumps(
            params,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return method, canonical_params

    def _cache(
        self,
        req_id: RequestId,
        identity: RequestIdentity,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        self.state.cached_responses[req_id] = CachedResponse(identity, response)
        return response

    @staticmethod
    async def _invoke(
        handler: MethodHandler,
        req_id: RequestId,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return make_result(req_id, await handler(params))
        except RpcError as err:
            return make_error(req_id, err)
        except Exception:
            return make_error(req_id, INTERNAL_FAILURE)

    @staticmethod
    def _not_initialized(req_id: RequestId) -> dict[str, Any]:
        return make_error(
            req_id,
            RpcError(
                code=-32005,
                message="Not initialized",
                category="invalid_state",
                retryable=False,
                message_key="desktop.error.not_initialized",
            ),
        )

    async def _initialize(
        self, req_id: RequestId, params: dict[str, Any]
    ) -> dict[str, Any]:
        if self.state.initialized:
            return make_error(
                req_id,
                RpcError(
                    code=-32005,
                    message="Already initialized",
                    category="invalid_state",
                    retryable=False,
                    message_key="desktop.error.already_initialized",
                ),
            )

        client_proto = params.get("protocol")
        client = params.get("client")
        requested = params.get("requested_capabilities")
        if (
            not isinstance(client_proto, dict)
            or client_proto.get("name") != PROTOCOL_NAME
            or client_proto.get("major") != PROTOCOL_MAJOR
            or not isinstance(client_proto.get("minor"), int)
            or client_proto["minor"] > PROTOCOL_MINOR
            or params.get("runtime_event_schema") != RUNTIME_EVENT_SCHEMA
            or not isinstance(client, dict)
            or not isinstance(client.get("name"), str)
            or not isinstance(client.get("version"), str)
            or not isinstance(requested, list)
            or any(
                not isinstance(capability, str)
                or capability not in REQUESTED_CAPABILITIES
                for capability in requested
            )
            or len(set(requested)) != len(requested)
        ):
            return make_error(
                req_id,
                RpcError(
                    code=-32001,
                    message="Incompatible protocol",
                    category="incompatible_protocol",
                    retryable=False,
                    recovery="contact_support",
                    message_key="desktop.error.incompatible_runtime",
                ),
            )

        methods = sorted(
            set(self._methods.keys())
            | {"initialize", "system.shutdown", "system.status"}
        )
        self.state.initialized = True
        return make_result(
            req_id,
            {
                "protocol": {
                    "name": PROTOCOL_NAME,
                    "major": PROTOCOL_MAJOR,
                    "minor": PROTOCOL_MINOR,
                },
                "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
                "server": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "methods": methods,
                "notifications": list(NOTIFICATIONS),
                "capabilities": {
                    capability: self._capabilities.get(capability, "unavailable")
                    for capability in REQUESTED_CAPABILITIES
                },
                "limits": dict(LIMITS),
            },
        )

    def next_notification(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.state.notification_seq += 1
        payload = dict(params)
        payload["notification_seq"] = self.state.notification_seq
        return make_notification(method, payload)
