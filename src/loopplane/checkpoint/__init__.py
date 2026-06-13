"""Checkpoint: durable append-only session records, resume with repair, and
session listing (contracts/checkpoint.md).
"""

from loopplane.checkpoint.rebuild import RebuildResult, rebuild_session
from loopplane.checkpoint.recorder import RecordingSink, SessionRecorder
from loopplane.checkpoint.records import (
    RECORD_KINDS,
    RECORD_SCHEMA_VERSION,
    AssistantMessageRecord,
    AssistantMessageRecordPayload,
    CheckpointRecord,
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
    deserialize_record,
    serialize_record,
)
from loopplane.checkpoint.store import CheckpointStore, SessionSummary

__all__ = [
    "RECORD_KINDS",
    "RECORD_SCHEMA_VERSION",
    "AssistantMessageRecord",
    "AssistantMessageRecordPayload",
    "CheckpointRecord",
    "CheckpointStore",
    "RebuildResult",
    "RecordingSink",
    "ReplacementDecisionRecord",
    "ReplacementDecisionRecordPayload",
    "SessionMetaPayload",
    "SessionMetaRecord",
    "SessionRecorder",
    "SessionSummary",
    "TerminationRecord",
    "TerminationRecordPayload",
    "ToolResultRecord",
    "ToolResultRecordPayload",
    "UserInputRecord",
    "UserInputRecordPayload",
    "deserialize_record",
    "rebuild_session",
    "serialize_record",
]
