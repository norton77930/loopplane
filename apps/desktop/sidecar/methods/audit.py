"""audit.list RPC over the Host checkpoint-derived turn-audit facade (078 T074)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from loopplane.host import LoopPlaneHost, TurnAuditEntry

try:
    from ..protocol import RpcError
except ImportError:  # pragma: no cover
    from protocol import RpcError  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]
_MAX_PAGE_LIMIT = 100

_INVALID = RpcError(
    code=-32602,
    message="Invalid params",
    category="protocol",
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


class AuditMethods:
    """Read-only audit projection and principal/session-bound cursor owner."""

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

    def handlers(self) -> dict[str, MethodHandler]:
        return {"audit.list": self.list_audit}

    async def list_audit(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("session_id")
        cursor = params.get("cursor")
        limit = params.get("limit", _MAX_PAGE_LIMIT)
        if (
            not isinstance(session_id, str)
            or not session_id.strip()
            or (cursor is not None and (not isinstance(cursor, str) or not cursor))
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= _MAX_PAGE_LIMIT
        ):
            raise _INVALID

        if not self._is_owned_session(session_id):
            # Enumeration-safe for a foreign principal or an unknown session.
            raise _NOT_FOUND

        entries = self._host.list_turn_audit(session_id)
        start = self._cursor_start(entries, cursor)
        page = entries[start : start + limit]
        next_cursor = (
            page[-1].audit_id if start + len(page) < len(entries) and page else None
        )
        return {
            "session_id": session_id,
            "entries": [_serialize_entry(entry) for entry in page],
            "next_cursor": next_cursor,
        }

    def _is_owned_session(self, session_id: str) -> bool:
        principal_id = self._principal()
        return any(
            summary.session_id == session_id
            and (principal_id is None or summary.principal_id == principal_id)
            for summary in self._host.list_sessions()
        )

    @staticmethod
    def _cursor_start(entries: tuple[TurnAuditEntry, ...], cursor: object) -> int:
        if cursor is None:
            return 0
        assert isinstance(cursor, str)  # validated by list_audit
        for index, entry in enumerate(entries):
            if entry.audit_id == cursor:
                return index + 1
        # The opaque audit ID is bound to this session because it must occur in
        # this session's ordered result set; do not expose cursor internals.
        raise _INVALID


def _serialize_entry(entry: TurnAuditEntry) -> dict[str, str | int | None]:
    """Exact renderer allowlist; never reflect checkpoint payload fields."""

    return {
        "audit_id": entry.audit_id,
        "session_id": entry.session_id,
        "turn_ordinal": entry.turn_ordinal,
        "checkpoint_sequence": entry.checkpoint_sequence,
        "recorded_at": entry.recorded_at,
        "state": entry.state,
        "termination_reason": entry.termination_reason,
        "turns_taken": entry.turns_taken,
    }
