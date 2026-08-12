"""Desktop stdio JSON-RPC V1 framing and envelopes (078 T023)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final, Literal

PROTOCOL_NAME: Final[str] = "loopplane.desktop.stdio"
PROTOCOL_VERSION: Final[int] = 1
MAX_FRAME_BYTES: Final[int] = 1_048_576
MAX_JSON_DEPTH: Final[int] = 32
MAX_KEYS: Final[int] = 256

ErrorCategory = Literal[
    "protocol",
    "state",
    "not_found",
    "busy",
    "permission",
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
    category="protocol",
    retryable=False,
    message_key="desktop.error.parse_error",
)

INVALID_REQUEST = RpcError(
    code=-32600,
    message="Invalid request",
    category="protocol",
    retryable=False,
    message_key="desktop.error.invalid_request",
)

METHOD_NOT_FOUND = RpcError(
    code=-32601,
    message="Method not found",
    category="protocol",
    retryable=False,
    message_key="desktop.error.method_not_found",
)


class FrameDecodeError(ValueError):
    """Raised when a frame is not valid UTF-8 LF JSON-RPC."""


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


def _count_keys(obj: Any) -> int:
    if isinstance(obj, dict):
        return len(obj) + sum(_count_keys(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_keys(v) for v in obj)
    return 0


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

        obj = json.loads(text, object_pairs_hook=_no_dupes)
    except FrameDecodeError:
        raise
    except (ValueError, TypeError) as exc:
        raise FrameDecodeError("invalid json") from exc

    if not isinstance(obj, dict):
        raise FrameDecodeError("root must be object")
    if _json_depth(obj) > MAX_JSON_DEPTH:
        raise FrameDecodeError("json too deep")
    if _count_keys(obj) > MAX_KEYS:
        raise FrameDecodeError("too many keys")
    return obj


def encode_frame(obj: dict[str, Any]) -> bytes:
    """Encode one JSON object as a single UTF-8 LF-terminated frame."""

    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_FRAME_BYTES:
        raise FrameDecodeError("frame too large")
    return raw + b"\n"


def make_result(id_: str | int | None, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def make_error(id_: str | int | None, error: RpcError) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": error.to_jsonrpc()}


def make_notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


class SerializedWriter:
    """Single-threaded writer that emits one frame at a time."""

    def __init__(self, write_bytes: Any) -> None:
        self._write = write_bytes
        self._busy = False

    def write_obj(self, obj: dict[str, Any]) -> None:
        if self._busy:
            raise RuntimeError("writer re-entered")
        self._busy = True
        try:
            self._write(encode_frame(obj))
        finally:
            self._busy = False
