"""The recording boundary (FR-080, FR-094): owned by the Controller, never
the loop. History appends and run terminations become checkpoint records as
they occur; each append is flushed before the producing operation completes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from loopplane.checkpoint.records import (
    AssistantMessageRecord,
    AssistantMessageRecordPayload,
    ReplacementDecisionRecord,
    ReplacementDecisionRecordPayload,
    SessionMetaPayload,
    SessionMetaRecord,
    TerminationRecord,
    TerminationRecordPayload,
    ToolResultRecord,
    ToolResultRecordPayload,
    UserInputRecord,
    UserInputRecordPayload,
)
from loopplane.checkpoint.store import CheckpointStore
from loopplane.events.emitter import EventSink
from loopplane.events.envelope import (
    RunTerminatedEvent,
    RuntimeEvent,
    TerminationReason,
)
from loopplane.loop.history import HistoryEntry, is_tool_results_entry
from loopplane.model.content import ToolResultBlock


class SessionRecorder:
    def __init__(
        self,
        *,
        store: CheckpointStore,
        session_id: str,
        created_at: datetime,
        label: str | None = None,
        next_sequence: int = 1,
        meta_recorded: bool = False,
    ) -> None:
        self._store = store
        self._session_id = session_id
        self._created_at = created_at
        self._label = label
        self._next_sequence = next_sequence
        self._meta_recorded = meta_recorded

    def _sequence(self) -> int:
        value = self._next_sequence
        self._next_sequence += 1
        return value

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def _ensure_meta(self) -> None:
        if self._meta_recorded:
            return
        self._meta_recorded = True
        await self._store.append(
            SessionMetaRecord(
                session_id=self._session_id,
                sequence=self._sequence(),
                recorded_at=self._now(),
                payload=SessionMetaPayload(
                    created_at=self._created_at, label=self._label
                ),
            )
        )

    async def record_entry(self, entry: HistoryEntry) -> None:
        await self._ensure_meta()
        if entry.role == "assistant":
            await self._store.append(
                AssistantMessageRecord(
                    session_id=self._session_id,
                    sequence=self._sequence(),
                    recorded_at=self._now(),
                    payload=AssistantMessageRecordPayload(blocks=list(entry.blocks)),
                )
            )
            return
        if is_tool_results_entry(entry):
            for block in entry.blocks:
                if not isinstance(block, ToolResultBlock):
                    continue
                await self._store.append(
                    ToolResultRecord(
                        session_id=self._session_id,
                        sequence=self._sequence(),
                        recorded_at=self._now(),
                        payload=ToolResultRecordPayload(block=block),
                    )
                )
            return
        await self._store.append(
            UserInputRecord(
                session_id=self._session_id,
                sequence=self._sequence(),
                recorded_at=self._now(),
                payload=UserInputRecordPayload(blocks=list(entry.blocks)),
            )
        )

    async def record_replacement(
        self,
        *,
        artifact_reference: str,
        replaced_call_id: str,
        preview: str,
        decided_at: datetime,
    ) -> None:
        await self._ensure_meta()
        await self._store.append(
            ReplacementDecisionRecord(
                session_id=self._session_id,
                sequence=self._sequence(),
                recorded_at=self._now(),
                payload=ReplacementDecisionRecordPayload(
                    artifact_reference=artifact_reference,
                    replaced_call_id=replaced_call_id,
                    preview=preview,
                    decided_at=decided_at,
                ),
            )
        )

    async def record_termination(
        self, reason: TerminationReason, turns_taken: int
    ) -> None:
        await self._ensure_meta()
        await self._store.append(
            TerminationRecord(
                session_id=self._session_id,
                sequence=self._sequence(),
                recorded_at=self._now(),
                payload=TerminationRecordPayload(
                    reason=reason, turns_taken=turns_taken
                ),
            )
        )


class RecordingSink:
    """Wraps the outbound sink: a run termination is recorded durably before
    the event is forwarded (append-as-you-go).
    """

    def __init__(self, inner: EventSink, recorder: SessionRecorder) -> None:
        self._inner = inner
        self._recorder = recorder

    async def __call__(self, event: RuntimeEvent) -> None:
        if isinstance(event, RunTerminatedEvent) and not event.replay:
            await self._recorder.record_termination(
                event.payload.reason, event.payload.turns_taken
            )
        await self._inner(event)
