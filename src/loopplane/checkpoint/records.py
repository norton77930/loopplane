"""Checkpoint record envelope and kinds (data-model.md: Checkpoint Record;
FR-080). Line-oriented JSON serialization with corrupt-line tolerance
(FR-083).
"""

from __future__ import annotations

import json
from typing import Annotated, Final, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)

from loopplane.events.envelope import TerminationReason
from loopplane.model.content import ContentBlock, ToolResultBlock

RECORD_SCHEMA_VERSION: Final[int] = 1

RECORD_KINDS: Final[tuple[str, ...]] = (
    "session-meta",
    "user-input",
    "assistant-message",
    "tool-result",
    "replacement-decision",
    "termination",
)


class _RecordModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class _Envelope(_RecordModel):
    schema_version: int = RECORD_SCHEMA_VERSION
    session_id: str
    sequence: int
    recorded_at: AwareDatetime


class SessionMetaPayload(_RecordModel):
    created_at: AwareDatetime
    label: str | None = None


class SessionMetaRecord(_Envelope):
    record_kind: Literal["session-meta"] = "session-meta"
    payload: SessionMetaPayload


class UserInputRecordPayload(_RecordModel):
    blocks: list[ContentBlock]


class UserInputRecord(_Envelope):
    record_kind: Literal["user-input"] = "user-input"
    payload: UserInputRecordPayload


class AssistantMessageRecordPayload(_RecordModel):
    blocks: list[ContentBlock]


class AssistantMessageRecord(_Envelope):
    record_kind: Literal["assistant-message"] = "assistant-message"
    payload: AssistantMessageRecordPayload


class ToolResultRecordPayload(_RecordModel):
    block: ToolResultBlock


class ToolResultRecord(_Envelope):
    record_kind: Literal["tool-result"] = "tool-result"
    payload: ToolResultRecordPayload


class ReplacementDecisionRecordPayload(_RecordModel):
    artifact_reference: str
    replaced_call_id: str
    preview: str
    decided_at: AwareDatetime


class ReplacementDecisionRecord(_Envelope):
    record_kind: Literal["replacement-decision"] = "replacement-decision"
    payload: ReplacementDecisionRecordPayload


class TerminationRecordPayload(_RecordModel):
    reason: TerminationReason
    turns_taken: int


class TerminationRecord(_Envelope):
    record_kind: Literal["termination"] = "termination"
    payload: TerminationRecordPayload


CheckpointRecord = Annotated[
    SessionMetaRecord
    | UserInputRecord
    | AssistantMessageRecord
    | ToolResultRecord
    | ReplacementDecisionRecord
    | TerminationRecord,
    Field(discriminator="record_kind"),
]

_adapter: TypeAdapter[CheckpointRecord] = TypeAdapter(CheckpointRecord)


def serialize_record(record: CheckpointRecord) -> str:
    return _adapter.dump_json(record).decode("utf-8")


def deserialize_record(line: str | bytes) -> CheckpointRecord | None:
    """One record per line; anything that fails to parse or validate yields
    None so the caller can skip it with a warning (FR-083).
    """
    try:
        document = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get("record_kind") not in RECORD_KINDS:
        return None
    try:
        return _adapter.validate_python(document)
    except ValidationError:
        return None
