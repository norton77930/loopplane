"""Metadata-safe checkpoint-derived logical-turn audit projection (078 T073).

The projection reads only durable checkpoint envelopes.  It intentionally never
looks at reconstructed history or runtime events, because either can contain
prompt, model, tool, approval, or diagnostic payloads that are excluded from
the Desktop audit contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from loopplane.checkpoint.records import (
    CheckpointRecord,
    TerminationRecord,
    UserInputRecord,
)

AuditState = Literal["completed", "interrupted"]


@dataclass(frozen=True, slots=True)
class TurnAuditEntry:
    """One metadata-only logical submitted-turn checkpoint outcome."""

    audit_id: str
    session_id: str
    turn_ordinal: int
    checkpoint_sequence: int
    recorded_at: str | None
    state: AuditState
    termination_reason: str | None
    turns_taken: int | None


def checkpoint_records_to_audit_entries(
    records: Sequence[CheckpointRecord],
) -> tuple[TurnAuditEntry, ...]:
    """Return logical submitted-turn outcomes from durable checkpoint records.

    A user-input record starts one logical turn.  Its first following durable
    termination record completes that turn.  A following user input, or an
    end-of-stream without termination, is the only durable evidence available
    for an interrupted turn; its reason and turn count remain unavailable.
    """

    entries: list[TurnAuditEntry] = []
    active: UserInputRecord | None = None
    ordinal = 0

    for record in sorted(records, key=lambda item: item.sequence):
        if isinstance(record, UserInputRecord):
            if active is not None:
                entries.append(_interrupted_entry(active, ordinal))
            ordinal += 1
            active = record
            continue
        if isinstance(record, TerminationRecord) and active is not None:
            entries.append(_terminal_entry(active, record, ordinal))
            active = None

    if active is not None:
        entries.append(_interrupted_entry(active, ordinal))

    return tuple(
        sorted(entries, key=lambda item: (item.checkpoint_sequence, item.audit_id))
    )


def _audit_id(session_id: str, input_sequence: int) -> str:
    """Produce a deterministic opaque ID without exposing checkpoint payloads."""

    digest = sha256(
        f"loopplane.turn-audit.v1\0{session_id}\0{input_sequence}".encode()
    ).hexdigest()
    return f"audit_{digest}"


def _interrupted_entry(source: UserInputRecord, ordinal: int) -> TurnAuditEntry:
    return TurnAuditEntry(
        audit_id=_audit_id(source.session_id, source.sequence),
        session_id=source.session_id,
        turn_ordinal=ordinal,
        checkpoint_sequence=source.sequence,
        recorded_at=source.recorded_at.isoformat(),
        state="interrupted",
        termination_reason=None,
        turns_taken=None,
    )


def _terminal_entry(
    source: UserInputRecord, termination: TerminationRecord, ordinal: int
) -> TurnAuditEntry:
    reason = termination.payload.reason
    state: AuditState = (
        "interrupted" if reason in {"cancelled", "unrecoverable-error"} else "completed"
    )
    return TurnAuditEntry(
        audit_id=_audit_id(source.session_id, source.sequence),
        session_id=source.session_id,
        turn_ordinal=ordinal,
        checkpoint_sequence=termination.sequence,
        recorded_at=termination.recorded_at.isoformat(),
        state=state,
        termination_reason=reason,
        turns_taken=termination.payload.turns_taken,
    )
