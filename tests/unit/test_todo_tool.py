"""Unit tests for the todo_write task-list tool on the Internal Tool Adapter
(spec 044). Deterministic and offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import TextBlock
from loopplane.tools import InternalToolAdapter

pytestmark = pytest.mark.anyio


def _context(tmp_path: Path, session_id: str = "session-1") -> RunContext:
    return RunContext(session_id=session_id, working_scope=tmp_path)


async def _invoke(
    adapter: InternalToolAdapter,
    name: str,
    call_input: dict[str, object],
    context: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, context)]


def _todo(content: str, status: str) -> dict[str, str]:
    return {"content": content, "status": status}


def _stored(adapter: InternalToolAdapter, session_id: str) -> object:
    return adapter._todos.get(session_id)  # noqa: SLF001 - white-box state check


# --- US1: record & update -----------------------------------------------------


async def test_set_records_and_returns_the_list(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    (block,) = await _invoke(
        adapter,
        "todo_write",
        {"todos": [_todo("read code", "in_progress"), _todo("write tests", "pending")]},
        context,
    )

    assert isinstance(block, TextBlock)
    assert "read code" in block.text and "write tests" in block.text
    assert "[in_progress]" in block.text and "[pending]" in block.text
    assert _stored(adapter, context.session_id) == [
        {"content": "read code", "status": "in_progress"},
        {"content": "write tests", "status": "pending"},
    ]


async def test_second_call_replaces_with_no_residue(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(
        adapter,
        "todo_write",
        {"todos": [_todo("a", "pending"), _todo("b", "pending")]},
        context,
    )
    await _invoke(adapter, "todo_write", {"todos": [_todo("c", "completed")]}, context)

    assert _stored(adapter, context.session_id) == [
        {"content": "c", "status": "completed"}
    ]


async def test_status_update_is_retained(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "todo_write", {"todos": [_todo("task", "pending")]}, context)
    await _invoke(
        adapter, "todo_write", {"todos": [_todo("task", "completed")]}, context
    )

    assert _stored(adapter, context.session_id) == [
        {"content": "task", "status": "completed"}
    ]


async def test_empty_list_clears(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "todo_write", {"todos": [_todo("task", "pending")]}, context)
    (block,) = await _invoke(adapter, "todo_write", {"todos": []}, context)

    assert isinstance(block, TextBlock)
    assert "clear" in block.text.lower()
    assert _stored(adapter, context.session_id) == []


# --- US1: validation (errors never mutate the prior list) ---------------------


async def test_invalid_status_rejected_prior_list_unchanged(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "todo_write", {"todos": [_todo("keep", "pending")]}, context)
    (error,) = await _invoke(
        adapter, "todo_write", {"todos": [_todo("bad", "blocked")]}, context
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert _stored(adapter, context.session_id) == [
        {"content": "keep", "status": "pending"}
    ]


async def test_missing_field_rejected(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    (error,) = await _invoke(
        adapter, "todo_write", {"todos": [{"content": "no status"}]}, context
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert _stored(adapter, context.session_id) is None


async def test_blank_content_rejected(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    (error,) = await _invoke(
        adapter, "todo_write", {"todos": [_todo("   ", "pending")]}, context
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_oversized_list_rejected_prior_list_unchanged(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "todo_write", {"todos": [_todo("keep", "pending")]}, context)
    too_many = [_todo(f"t{i}", "pending") for i in range(101)]
    (error,) = await _invoke(adapter, "todo_write", {"todos": too_many}, context)

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert _stored(adapter, context.session_id) == [
        {"content": "keep", "status": "pending"}
    ]


# --- US2: per-session isolation & metadata safety -----------------------------


async def test_lists_isolated_per_session(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    ctx_a = _context(tmp_path, "session-a")
    ctx_b = _context(tmp_path, "session-b")

    await _invoke(adapter, "todo_write", {"todos": [_todo("a-task", "pending")]}, ctx_a)
    await _invoke(
        adapter, "todo_write", {"todos": [_todo("b-task", "completed")]}, ctx_b
    )

    assert _stored(adapter, "session-a") == [{"content": "a-task", "status": "pending"}]
    assert _stored(adapter, "session-b") == [
        {"content": "b-task", "status": "completed"}
    ]


async def test_result_surfaces_only_content_and_status(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    (block,) = await _invoke(
        adapter, "todo_write", {"todos": [_todo("ship it", "in_progress")]}, context
    )

    assert isinstance(block, TextBlock)
    assert block.text == "Recorded 1 todos:\n[in_progress] ship it"


# --- US3: governed like every other tool --------------------------------------


async def test_describe_includes_todo_write_as_mutating() -> None:
    descriptors = {d.name: d for d in InternalToolAdapter().describe()}

    assert "todo_write" in descriptors
    todo = descriptors["todo_write"]
    assert todo.read_only is False
    assert "todos" in todo.input_schema["properties"]
