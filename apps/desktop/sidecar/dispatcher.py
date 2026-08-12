"""Pure JSON-RPC dispatcher for Desktop V1 (078 T024).

Zero Host/store/profile construction. Method providers are injected.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

try:
    from .protocol import (
        INTERNAL_FAILURE,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        PROTOCOL_NAME,
        PROTOCOL_VERSION,
        RpcError,
        decode_frame,
        make_error,
        make_notification,
        make_result,
    )
except ImportError:  # pragma: no cover - script-path load
    from protocol import (  # type: ignore[no-redef]
        INTERNAL_FAILURE,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        PROTOCOL_NAME,
        PROTOCOL_VERSION,
        RpcError,
        decode_frame,
        make_error,
        make_notification,
        make_result,
    )

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class DispatcherState:
    initialized: bool = False
    shutdown: bool = False
    notification_seq: int = 0
    pending_results: dict[str | int, Any] = field(default_factory=dict)
    seen_ids: set[str | int] = field(default_factory=set)


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
            "protocol": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
        }
        self.state = DispatcherState()

    def register(self, name: str, handler: MethodHandler) -> None:
        self._methods[name] = handler

    async def handle_frame(self, line: bytes | str) -> list[dict[str, Any]]:
        """Return zero or more response/notification objects for one input frame."""

        try:
            msg = decode_frame(line)
        except Exception:
            return [make_error(None, INVALID_REQUEST)]

        if msg.get("jsonrpc") != "2.0":
            return [make_error(msg.get("id"), INVALID_REQUEST)]

        # Notification (no id)
        if "method" in msg and "id" not in msg:
            return []

        if "method" not in msg:
            return [make_error(msg.get("id"), INVALID_REQUEST)]

        method = str(msg["method"])
        req_id = msg.get("id")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            return [make_error(req_id, INVALID_REQUEST)]

        if self.state.shutdown:
            return [
                make_error(
                    req_id,
                    RpcError(
                        code=-32000,
                        message="Shutting down",
                        category="state",
                        retryable=False,
                        message_key="desktop.error.shutting_down",
                    ),
                )
            ]

        if method == "initialize":
            return [await self._initialize(req_id, params)]

        if method == "system.status":
            if not self.state.initialized:
                return [
                    make_error(
                        req_id,
                        RpcError(
                            code=-32001,
                            message="Not initialized",
                            category="state",
                            retryable=False,
                            message_key="desktop.error.not_initialized",
                        ),
                    )
                ]
            return [
                make_result(
                    req_id,
                    {
                        "ready": not self.state.shutdown,
                        "initialized": self.state.initialized,
                        "shutdown": self.state.shutdown,
                    },
                )
            ]

        if not self.state.initialized:
            return [
                make_error(
                    req_id,
                    RpcError(
                        code=-32001,
                        message="Not initialized",
                        category="state",
                        retryable=False,
                        message_key="desktop.error.not_initialized",
                    ),
                )
            ]

        # Idempotent replay for mutation ids
        if req_id is not None and req_id in self.state.pending_results:
            return [make_result(req_id, self.state.pending_results[req_id])]

        if method in ("shutdown", "system.shutdown"):
            handler = self._methods.get(method) or self._methods.get("system.shutdown")
            if handler is not None:
                try:
                    result = await handler(params)
                except RpcError as err:
                    return [make_error(req_id, err)]
                except Exception:
                    return [make_error(req_id, INTERNAL_FAILURE)]
            else:
                result = {"ok": True}
            self.state.shutdown = True
            if req_id is not None:
                self.state.pending_results[req_id] = result
                self.state.seen_ids.add(req_id)
            return [make_result(req_id, result)]

        handler = self._methods.get(method)
        if handler is None:
            return [make_error(req_id, METHOD_NOT_FOUND)]

        try:
            result = await handler(params)
        except RpcError as err:
            return [make_error(req_id, err)]
        except Exception:
            return [make_error(req_id, INTERNAL_FAILURE)]

        if req_id is not None:
            self.state.pending_results[req_id] = result
            self.state.seen_ids.add(req_id)
        return [make_result(req_id, result)]

    async def _initialize(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        client_proto = params.get("protocol")
        client_ver = params.get("version")
        if client_proto not in (None, PROTOCOL_NAME):
            return make_error(
                req_id,
                RpcError(
                    code=-32002,
                    message="Incompatible protocol",
                    category="protocol",
                    retryable=False,
                    message_key="desktop.error.incompatible_protocol",
                ),
            )
        if client_ver not in (None, PROTOCOL_VERSION):
            return make_error(
                req_id,
                RpcError(
                    code=-32003,
                    message="Incompatible version",
                    category="protocol",
                    retryable=False,
                    message_key="desktop.error.incompatible_version",
                ),
            )
        self.state.initialized = True
        return make_result(
            req_id,
            {
                "protocol": PROTOCOL_NAME,
                "version": PROTOCOL_VERSION,
                "capabilities": self._capabilities,
                "methods": sorted(self._methods.keys())
                + ["initialize", "shutdown", "system.shutdown", "system.status"],
            },
        )

    def next_notification(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.state.notification_seq += 1
        payload = dict(params)
        payload["sequence"] = self.state.notification_seq
        return make_notification(method, payload)
