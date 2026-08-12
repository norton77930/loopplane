"""Host turn audit facade (078 T068/T073)."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from loopplane.checkpoint.records import (
    SessionMetaPayload,
    SessionMetaRecord,
    TerminationRecord,
    TerminationRecordPayload,
    UserInputRecord,
    UserInputRecordPayload,
)
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextBlock

pytestmark = pytest.mark.anyio


def _host(tmp_path: Path) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(script=[ScriptedTurn()], context_capacity=100_000),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / "store",
            ),
        ),
        working_scope=tmp_path,
    )


async def _append_logical_turns(host: LoopPlaneHost) -> tuple[str, datetime, datetime]:
    store = host._assembled.checkpoint_store
    assert store is not None
    session_id = "audit-session"
    created_at = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    completed_at = created_at + timedelta(minutes=1)
    interrupted_at = created_at + timedelta(minutes=2)

    await store.append(
        SessionMetaRecord(
            session_id=session_id,
            sequence=1,
            recorded_at=created_at,
            payload=SessionMetaPayload(
                created_at=created_at,
                principal_id="private-principal-must-not-leak",
            ),
        )
    )
    await store.append(
        UserInputRecord(
            session_id=session_id,
            sequence=2,
            recorded_at=created_at,
            payload=UserInputRecordPayload(
                blocks=[TextBlock(text="private prompt must not leak")]
            ),
        )
    )
    await store.append(
        TerminationRecord(
            session_id=session_id,
            sequence=5,
            recorded_at=completed_at,
            payload=TerminationRecordPayload(
                reason="natural-completion", turns_taken=3
            ),
        )
    )
    await store.append(
        UserInputRecord(
            session_id=session_id,
            sequence=8,
            recorded_at=interrupted_at,
            payload=UserInputRecordPayload(
                blocks=[TextBlock(text="second private prompt must not leak")]
            ),
        )
    )
    return session_id, completed_at, interrupted_at


async def test_list_turn_audit_is_checkpoint_derived_safe_and_no_write(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    session_id, completed_at, interrupted_at = await _append_logical_turns(host)
    checkpoint_path = tmp_path / "store" / "checkpoints.sqlite3"
    bytes_before = checkpoint_path.read_bytes()

    entries = host.list_turn_audit(session_id)
    repeat = host.list_turn_audit(session_id)

    assert tuple(field.name for field in fields(entries[0])) == (
        "audit_id",
        "session_id",
        "turn_ordinal",
        "checkpoint_sequence",
        "recorded_at",
        "state",
        "termination_reason",
        "turns_taken",
    )
    assert [
        (
            entry.turn_ordinal,
            entry.checkpoint_sequence,
            entry.recorded_at,
            entry.state,
            entry.termination_reason,
            entry.turns_taken,
        )
        for entry in entries
    ] == [
        (1, 5, completed_at.isoformat(), "completed", "natural-completion", 3),
        (2, 8, interrupted_at.isoformat(), "interrupted", None, None),
    ]
    assert entries == repeat
    assert entries[0].audit_id != entries[1].audit_id
    assert all(entry.audit_id.startswith("audit_") for entry in entries)
    assert checkpoint_path.read_bytes() == bytes_before

    serialized = repr(entries)
    for forbidden in (
        "private prompt must not leak",
        "private-principal-must-not-leak",
        "TextBlock",
        "blocks",
    ):
        assert forbidden not in serialized


async def test_list_turn_audit_keeps_source_immutable_and_fork_empty_until_its_turn(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    source_session_id, _, _ = await _append_logical_turns(host)
    source_before = host.list_turn_audit(source_session_id)

    fork_id = await host.fork_session(
        source_session_id,
        principal_id="private-principal-must-not-leak",
        source_sequence=5,
    )

    async def sink(_event: object) -> None:
        return None

    async with host.resume_session(fork_id, sink) as fork:
        await fork.submit("fork-private-prompt")

    fork_audit = host.list_turn_audit(fork_id)
    assert host.list_turn_audit(source_session_id) == source_before
    assert len(fork_audit) == 1
    assert fork_audit[0].session_id == fork_id
    assert fork_audit[0].audit_id not in {entry.audit_id for entry in source_before}
