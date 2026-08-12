"""Desktop stdio JSON-RPC V1 framing and envelopes (078 T023)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Final, Literal

PROTOCOL_NAME: Final[str] = "loopplane.desktop.stdio"
PROTOCOL_MAJOR: Final[int] = 1
PROTOCOL_MINOR: Final[int] = 0
# Legacy test import; wire negotiation uses the major/minor object above.
PROTOCOL_VERSION: Final[int] = PROTOCOL_MAJOR
RUNTIME_EVENT_SCHEMA: Final[int] = 1
SERVER_NAME: Final[str] = "loopplane-desktop-sidecar"
SERVER_VERSION: Final[str] = "0.4.0"
MAX_FRAME_BYTES: Final[int] = 1_048_576
MAX_RUNTIME_EVENT_FRAME_BYTES: Final[int] = 8_388_608
MAX_JSON_DEPTH: Final[int] = 32
MAX_KEYS: Final[int] = 128

ErrorCategory = Literal[
    "parse_error",
    "invalid_request",
    "method_not_found",
    "invalid_params",
    "not_found",
    "busy",
    "internal_failure",
    "incompatible_protocol",
    "conflict",
    "invalid_state",
    "workspace_relink_required",
    "unsafe_input",
    "unavailable",
    "cancelled",
    "deadline_exceeded",
    "durability_unsupported",
    "publication_failed",
]


@dataclass(frozen=True, slots=True)
class RpcError(Exception):
    code: int
    message: str
    category: ErrorCategory
    retryable: bool
    message_key: str
    recovery: str | None = None
    data: dict[str, Any] | None = None

    def __str__(self) -> str:  # pragma: no cover
        return self.message

    def to_jsonrpc(self) -> dict[str, Any]:
        err: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "data": {
                "category": self.category,
                "retryable": self.retryable,
                "messageKey": self.message_key,
            },
        }
        if self.recovery is not None:
            err["data"]["recovery"] = self.recovery
        if self.data:
            err["data"]["extra"] = self.data
        return err


INTERNAL_FAILURE = RpcError(
    code=-32603,
    message="Internal failure",
    category="internal_failure",
    retryable=True,
    message_key="desktop.error.internal_failure",
    recovery="restart_runtime",
)

PARSE_ERROR = RpcError(
    code=-32700,
    message="Parse error",
    category="parse_error",
    retryable=False,
    message_key="desktop.error.parse_error",
)

INVALID_REQUEST = RpcError(
    code=-32600,
    message="Invalid request",
    category="invalid_request",
    retryable=False,
    message_key="desktop.error.invalid_request",
)

METHOD_NOT_FOUND = RpcError(
    code=-32601,
    message="Method not found",
    category="method_not_found",
    retryable=False,
    message_key="desktop.error.method_not_found",
)

INVALID_PARAMS = RpcError(
    code=-32602,
    message="Invalid params",
    category="invalid_params",
    retryable=False,
    message_key="desktop.error.invalid_params",
)


class FrameDecodeError(ValueError):
    """Raised when a frame is not valid UTF-8 LF JSON-RPC."""


def _reject_nonfinite(_value: str) -> Any:
    raise FrameDecodeError("non-finite number")


def _json_depth(obj: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(obj, dict):
        if not obj:
            return depth
        return max(_json_depth(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return depth
        return max(_json_depth(v, depth + 1) for v in obj)
    return depth


def _validate_json_value(obj: Any) -> None:
    if isinstance(obj, dict):
        if len(obj) > MAX_KEYS:
            raise FrameDecodeError("too many keys")
        for value in obj.values():
            _validate_json_value(value)
        return
    if isinstance(obj, list):
        for value in obj:
            _validate_json_value(value)
        return
    if isinstance(obj, float) and not math.isfinite(obj):
        raise FrameDecodeError("non-finite number")
    if isinstance(obj, str):
        try:
            obj.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise FrameDecodeError("unpaired surrogate") from exc


def decode_frame(line: bytes | str) -> dict[str, Any]:
    """Decode one LF-delimited UTF-8 JSON object with size/depth/key bounds."""

    if isinstance(line, bytes):
        if len(line) > MAX_FRAME_BYTES:
            raise FrameDecodeError("frame too large")
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FrameDecodeError("invalid utf-8") from exc
    else:
        text = line
        if len(text.encode("utf-8")) > MAX_FRAME_BYTES:
            raise FrameDecodeError("frame too large")

    text = text.strip("\r\n")
    if not text:
        raise FrameDecodeError("empty frame")

    try:
        # Reject duplicate keys via object_pairs_hook.
        def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for k, v in pairs:
                if k in out:
                    raise FrameDecodeError("duplicate key")
                out[k] = v
            return out

        obj = json.loads(
            text,
            object_pairs_hook=_no_dupes,
            parse_constant=_reject_nonfinite,
        )
    except FrameDecodeError:
        raise
    except (ValueError, TypeError) as exc:
        raise FrameDecodeError("invalid json") from exc

    if not isinstance(obj, dict):
        raise FrameDecodeError("root must be object")
    if _json_depth(obj) > MAX_JSON_DEPTH:
        raise FrameDecodeError("json too deep")
    _validate_json_value(obj)
    return obj


def encode_frame(
    obj: dict[str, Any], *, max_frame_bytes: int = MAX_FRAME_BYTES
) -> bytes:
    """Encode one JSON object as a single bounded UTF-8 LF frame."""

    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > max_frame_bytes:
        raise FrameDecodeError("frame too large")
    return raw + b"\n"


def make_result(id_: str | int | None, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def make_error(id_: str | int | None, error: RpcError) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": error.to_jsonrpc()}


def make_notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


class SerializedWriter:
    """Serialize stdout frames with a bounded reentrant notification queue."""

    def __init__(
        self,
        write_bytes: Any,
        *,
        max_notification_frames: int = 128,
        max_notification_bytes: int = 16_777_216,
    ) -> None:
        self._write = write_bytes
        self._busy = False
        self.failed = False
        self._max_notification_frames = max_notification_frames
        self._max_notification_bytes = max_notification_bytes
        self._notifications: list[bytes] = []
        self._notification_bytes = 0

    def write_obj(self, obj: dict[str, Any]) -> None:
        if self.failed:
            raise RuntimeError("writer failed")
        frame_limit = (
            MAX_RUNTIME_EVENT_FRAME_BYTES
            if obj.get("method") == "runtime.event" and "id" not in obj
            else MAX_FRAME_BYTES
        )
        frame = encode_frame(obj, max_frame_bytes=frame_limit)
        if self._busy:
            if "method" not in obj or "id" in obj:
                raise RuntimeError("writer re-entered")
            if (
                len(self._notifications) >= self._max_notification_frames
                or self._notification_bytes + len(frame) > self._max_notification_bytes
            ):
                self.failed = True
                self._notifications.clear()
                self._notification_bytes = 0
                raise RuntimeError("notification queue overflow")
            self._notifications.append(frame)
            self._notification_bytes += len(frame)
            return

        self._busy = True
        try:
            current = frame
            while True:
                self._write(current)
                if not self._notifications:
                    break
                current = self._notifications.pop(0)
                self._notification_bytes -= len(current)
        except BaseException:
            self.failed = True
            self._notifications.clear()
            self._notification_bytes = 0
            raise
        finally:
            self._busy = False
