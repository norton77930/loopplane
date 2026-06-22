"""Contract tests for checkpoint records (contracts/checkpoint.md).

Asserts append-as-you-go durability, resume from records alone,
dangling-call repair with a warning, corrupted-record skip, concurrent-write
safety, and newest-first listing (FR-080–FR-085).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from loopplane.checkpoint import (
    AssistantMessageRecord,
    FileCheckpointStore,
    SessionMetaRecord,
    TerminationRecord,
    ToolResultRecord,
    UserInputRecord,
    rebuild_session,
)
from loopplane.errors import ErrorCategory, NormalizedError
from loopplane.model.content import (
    DocumentBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)


def _meta(session_id: str, sequence: int = 1) -> SessionMetaRecord:
    return SessionMetaRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=_NOW,
        payload={"created_at": _NOW, "label": "test session"},
    )


def _user(session_id: str, sequence: int, text: str) -> UserInputRecord:
    return UserInputRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=_NOW,
        payload={"blocks": [TextBlock(text=text)]},
    )


def _assistant(
    session_id: str, sequence: int, *blocks: object
) -> AssistantMessageRecord:
    return AssistantMessageRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=_NOW,
        payload={"blocks": list(blocks)},
    )


def _result(
    session_id: str, sequence: int, call_id: str, text: str
) -> ToolResultRecord:
    return ToolResultRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=_NOW,
        payload={
            "block": ToolResultBlock(
                call_id=call_id, outcome="success", outputs=[TextBlock(text=text)]
            )
        },
    )


def _termination(
    session_id: str, sequence: int, reason: str = "natural-completion", turns: int = 1
) -> TerminationRecord:
    return TerminationRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=_NOW,
        payload={"reason": reason, "turns_taken": turns},
    )


async def test_append_as_you_go_is_immediately_durable(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)

    await store.append(_meta("s1"))
    records, problems = FileCheckpointStore(tmp_path).load("s1")
    assert problems == []
    assert [r.record_kind for r in records] == ["session-meta"]

    await store.append(_user("s1", 2, "hello"))
    records, _ = FileCheckpointStore(tmp_path).load("s1")
    assert [r.record_kind for r in records] == ["session-meta", "user-input"]


async def test_resume_rebuilds_history_from_records_alone(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "do the thing"))
    await store.append(
        _assistant(
            "s1",
            3,
            TextBlock(text="calling a tool"),
            ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "hi"}),
        )
    )
    await store.append(_result("s1", 4, "c1", "hi"))
    await store.append(_assistant("s1", 5, TextBlock(text="all done")))
    await store.append(_termination("s1", 6, turns=2))

    records, problems = FileCheckpointStore(tmp_path).load("s1")
    rebuilt = rebuild_session(records)

    assert problems == []
    assert rebuilt.repairs == []
    assert [entry.role for entry in rebuilt.entries] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert rebuilt.entries[0].blocks == (TextBlock(text="do the thing"),)
    (result_block,) = rebuilt.entries[2].blocks
    assert isinstance(result_block, ToolResultBlock)
    assert result_block.call_id == "c1"


async def test_resume_preserves_document_user_input(tmp_path: Path) -> None:
    document = DocumentBlock(
        media="JVBERi0xLjcKJSVFT0Y=",
        format="application/pdf",
        name="report.pdf",
    )
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("s1"))
    await store.append(
        UserInputRecord(
            session_id="s1",
            sequence=2,
            recorded_at=_NOW,
            payload={"blocks": [TextBlock(text="read"), document]},
        )
    )

    records, problems = FileCheckpointStore(tmp_path).load("s1")
    rebuilt = rebuild_session(records)

    assert problems == []
    assert rebuilt.repairs == []
    assert rebuilt.entries[0].blocks == (TextBlock(text="read"), document)


async def test_resume_preserves_signed_assistant_tool_call(tmp_path: Path) -> None:
    tool_call = ToolCallBlock(
        call_id="c1",
        tool_name="echo",
        input={"text": "hi"},
        provider_signature="gemini-signature-1",
    )
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "go"))
    await store.append(_assistant("s1", 3, tool_call))
    await store.append(_result("s1", 4, "c1", "hi"))
    await store.append(_termination("s1", 5))

    records, problems = FileCheckpointStore(tmp_path).load("s1")
    rebuilt = rebuild_session(records)

    assert problems == []
    assert rebuilt.repairs == []
    assert rebuilt.entries[1].blocks == (tool_call,)


async def test_dangling_call_is_repaired_with_a_warning(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "go"))
    await store.append(
        _assistant(
            "s1",
            3,
            ToolCallBlock(call_id="c-lost", tool_name="echo", input={"text": "x"}),
        )
    )
    # The process died between the call and its result.

    records, _ = FileCheckpointStore(tmp_path).load("s1")
    rebuilt = rebuild_session(records)

    assert any("c-lost" in repair for repair in rebuilt.repairs)
    (synthetic,) = rebuilt.entries[-1].blocks
    assert isinstance(synthetic, ToolResultBlock)
    assert synthetic.call_id == "c-lost"
    assert synthetic.outcome == "failure"
    assert synthetic.error is not None
    assert synthetic.error == NormalizedError(
        category=synthetic.error.category, reason=synthetic.error.reason
    )
    assert synthetic.error.category == ErrorCategory.EXECUTION


async def test_corrupted_record_is_skipped_and_the_rest_load(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "first"))

    record_file = next((tmp_path / "s1").glob("*.jsonl"))
    with record_file.open("a", encoding="utf-8") as handle:
        handle.write("{this is not valid json\n")

    await store.append(_user("s1", 3, "second"))

    records, problems = FileCheckpointStore(tmp_path).load("s1")
    assert len(problems) == 1
    assert [r.record_kind for r in records] == [
        "session-meta",
        "user-input",
        "user-input",
    ]


async def test_concurrent_writes_never_interleave(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("s1"))

    async def writer(start: int) -> None:
        for offset in range(25):
            await store.append(_user("s1", start + offset, f"message {start + offset}"))

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(writer, 100)
        task_group.start_soon(writer, 200)

    records, problems = FileCheckpointStore(tmp_path).load("s1")
    assert problems == []
    assert len(records) == 51  # meta + 2 * 25, every line parseable


async def test_sessions_list_newest_first(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    await store.append(_meta("older"))
    await anyio.sleep(0.02)
    await store.append(_meta("newer"))
    await anyio.sleep(0.02)
    await store.append(_user("older", 2, "older got a late message"))

    summaries = store.list_sessions()

    assert [summary.session_id for summary in summaries] == ["older", "newer"]
    assert summaries[0].label == "test session"


def test_missing_storage_root_yields_an_empty_listing(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path / "never-created")
    assert store.list_sessions() == []
