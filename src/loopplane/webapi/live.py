"""Additive live-channel helpers for the web/API host (074)."""

from __future__ import annotations

import json
import secrets
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class LiveTicketRecord:
    ticket: str
    principal_id: str
    session_id: str
    expires_at: datetime
    issued_at: datetime
    capabilities: tuple[str, ...]


class LiveTicketStore:
    """In-memory short-lived ticket store scoped to one ASGI app instance."""

    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._records: dict[str, LiveTicketRecord] = {}

    def issue(self, principal_id: str, session_id: str) -> LiveTicketRecord:
        now = datetime.now(UTC)
        record = LiveTicketRecord(
            ticket=secrets.token_urlsafe(24),
            principal_id=principal_id,
            session_id=session_id,
            issued_at=now,
            expires_at=now + self._ttl,
            capabilities=(
                "submit",
                "abort",
                "approval_decision",
                "question_answer",
                "ack",
            ),
        )
        self._records[record.ticket] = record
        return record

    def consume(self, ticket: str, session_id: str) -> LiveTicketRecord | None:
        record = self._records.pop(ticket, None)
        if record is None:
            return None
        if record.session_id != session_id:
            return None
        if record.expires_at <= datetime.now(UTC):
            return None
        return record


def latest_sequence(buffer: deque[tuple[int, str]] | None) -> int:
    if not buffer:
        return 0
    return max(seq for seq, _frame in buffer)


def replay_event_messages(
    buffer: deque[tuple[int, str]] | None, after_sequence: int
) -> list[dict[str, object]]:
    if not buffer:
        return []
    messages: list[dict[str, object]] = []
    for sequence, frame in list(buffer):
        if sequence <= after_sequence:
            continue
        payload = _payload_from_sse_frame(frame)
        if payload is None:
            continue
        messages.append(
            {
                "type": "event",
                "sequence": sequence,
                "session_id": payload.get("session_id"),
                "payload": payload,
            }
        )
    return messages


def _payload_from_sse_frame(frame: str) -> dict[str, object] | None:
    data = "\n".join(
        line.removeprefix("data:").strip()
        for line in frame.splitlines()
        if line.startswith("data:")
    )
    if not data:
        return None
    parsed = json.loads(data)
    return parsed if isinstance(parsed, dict) else None
