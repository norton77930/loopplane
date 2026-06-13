"""Resume: rebuild conversation state from records alone (FR-081), repairing
dangling tool calls (FR-082) and applying the same orphaned-input pruning
rule the live loop enforces (FR-007).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from loopplane.checkpoint.records import (
    AssistantMessageRecord,
    CheckpointRecord,
    ReplacementDecisionRecordPayload,
    SessionMetaRecord,
    TerminationRecord,
    ToolResultRecord,
    UserInputRecord,
)
from loopplane.errors import ErrorCategory, NormalizedError
from loopplane.loop.history import HistoryEntry, is_tool_results_entry
from loopplane.model.content import ToolCallBlock, ToolResultBlock


@dataclass
class RebuildResult:
    entries: list[HistoryEntry]
    decisions: list[ReplacementDecisionRecordPayload]
    label: str | None = None
    created_at: datetime | None = None
    repairs: list[str] = field(default_factory=list)


def rebuild_session(records: list[CheckpointRecord]) -> RebuildResult:
    result = RebuildResult(entries=[], decisions=[])
    entries = result.entries
    pending_calls: dict[str, datetime] = {}
    result_buffer: list[ToolResultBlock] = []
    buffer_time: datetime | None = None
    run_start = 0
    assistant_in_run = False

    def flush_results() -> None:
        nonlocal buffer_time
        if result_buffer:
            entries.append(
                HistoryEntry(
                    role="user",
                    blocks=tuple(result_buffer),
                    recorded_at=buffer_time or datetime.now().astimezone(),
                )
            )
            result_buffer.clear()
            buffer_time = None

    def repair_pending(at: datetime) -> None:
        if not pending_calls:
            return
        synthetic = tuple(
            ToolResultBlock(
                call_id=call_id,
                outcome="failure",
                outputs=[],
                error=NormalizedError(
                    category=ErrorCategory.EXECUTION,
                    reason="interrupted before completion; repaired on resume",
                ),
            )
            for call_id in pending_calls
        )
        if entries and is_tool_results_entry(entries[-1]):
            merged = entries[-1].blocks + synthetic
            entries[-1] = HistoryEntry(
                role="user", blocks=merged, recorded_at=entries[-1].recorded_at
            )
        else:
            entries.append(HistoryEntry(role="user", blocks=synthetic, recorded_at=at))
        result.repairs.extend(
            f"repaired dangling tool call {call_id} with a synthetic error result"
            for call_id in pending_calls
        )
        pending_calls.clear()

    for record in records:
        if isinstance(record, SessionMetaRecord):
            result.label = record.payload.label
            result.created_at = record.payload.created_at
        elif isinstance(record, UserInputRecord):
            flush_results()
            entries.append(
                HistoryEntry(
                    role="user",
                    blocks=tuple(record.payload.blocks),
                    recorded_at=record.recorded_at,
                )
            )
        elif isinstance(record, AssistantMessageRecord):
            flush_results()
            entries.append(
                HistoryEntry(
                    role="assistant",
                    blocks=tuple(record.payload.blocks),
                    recorded_at=record.recorded_at,
                )
            )
            assistant_in_run = True
            for block in record.payload.blocks:
                if isinstance(block, ToolCallBlock):
                    pending_calls[block.call_id] = record.recorded_at
        elif isinstance(record, ToolResultRecord):
            block = record.payload.block
            pending_calls.pop(block.call_id, None)
            result_buffer.append(block)
            buffer_time = record.recorded_at
        elif isinstance(record, TerminationRecord):
            flush_results()
            repair_pending(record.recorded_at)
            if (
                record.payload.reason == "cancelled"
                and not assistant_in_run
                and len(entries) > run_start
                and entries[-1].role == "user"
                and not is_tool_results_entry(entries[-1])
            ):
                # FR-007: a cancelled run that produced no assistant response
                # must not strand its triggering input.
                entries.pop()
            run_start = len(entries)
            assistant_in_run = False
        else:  # ReplacementDecisionRecord
            result.decisions.append(record.payload)

    # The stream ended without a termination: the process died mid-run.
    flush_results()
    if records:
        repair_pending(records[-1].recorded_at)
    return result
