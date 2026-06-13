"""Unit tests for rule precedence, the stale-write guard, the remaining
baseline tools, and output-size reduction (T030; FR-026, FR-030–FR-034,
FR-114).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.approval import PermissionRule, resolve_rules
from loopplane.context import RunContext
from loopplane.gateway import reduce_outputs
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import OutputBlock, TextBlock
from loopplane.tools import InternalToolAdapter

pytestmark = pytest.mark.anyio


def _context(tmp_path: Path) -> RunContext:
    return RunContext(session_id="session-1", working_scope=tmp_path)


async def _invoke(
    adapter: InternalToolAdapter,
    name: str,
    call_input: dict[str, object],
    context: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, context)]


# --- rule precedence (supplements the approval contract suite) ---------------


def test_three_scopes_resolve_to_the_most_local() -> None:
    rules = [
        PermissionRule(matcher="tool", effect="deny", scope="user"),
        PermissionRule(matcher="tool", effect="deny", scope="project"),
        PermissionRule(matcher="tool", effect="allow", scope="session-local"),
    ]
    assert resolve_rules(rules, "tool") == "allow"


def test_pattern_and_exact_rules_combine_within_one_scope() -> None:
    rules = [
        PermissionRule(matcher="mcp:*", effect="allow", scope="project"),
        PermissionRule(matcher="mcp:server:rm", effect="deny", scope="project"),
    ]
    assert resolve_rules(rules, "mcp:server:rm") == "deny"
    assert resolve_rules(rules, "mcp:server:ls") == "allow"


# --- stale-write guard (FR-034) -----------------------------------------------


async def test_creating_a_new_file_is_exempt_from_the_guard(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    outputs = await _invoke(
        adapter,
        "write_file",
        {"path": "fresh.txt", "content": "hello"},
        _context(tmp_path),
    )
    assert all(not isinstance(output, ErrorOutput) for output in outputs)
    assert (tmp_path / "fresh.txt").read_text("utf-8") == "hello"


async def test_overwriting_without_a_read_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
    adapter = InternalToolAdapter()

    outputs = await _invoke(
        adapter,
        "write_file",
        {"path": "existing.txt", "content": "clobbered"},
        _context(tmp_path),
    )

    (error,) = outputs
    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert (tmp_path / "existing.txt").read_text("utf-8") == "original"


async def test_read_then_write_succeeds(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("v1", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    outputs = await _invoke(
        adapter, "write_file", {"path": "doc.txt", "content": "v2"}, context
    )

    assert all(not isinstance(output, ErrorOutput) for output in outputs)
    assert (tmp_path / "doc.txt").read_text("utf-8") == "v2"


async def test_write_after_external_change_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "doc.txt"
    target.write_text("v1", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    target.write_text("changed behind the agent's back", encoding="utf-8")
    outputs = await _invoke(
        adapter, "write_file", {"path": "doc.txt", "content": "v2"}, context
    )

    (error,) = outputs
    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert "changed since" in error.message


async def test_consecutive_writes_by_the_same_session_succeed(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "write_file", {"path": "doc.txt", "content": "v1"}, context)
    outputs = await _invoke(
        adapter, "write_file", {"path": "doc.txt", "content": "v2"}, context
    )

    assert all(not isinstance(output, ErrorOutput) for output in outputs)
    assert (tmp_path / "doc.txt").read_text("utf-8") == "v2"


# --- remaining baseline tools (FR-030, FR-033) ----------------------------------


async def test_read_file_returns_the_content(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text(
        "line one\nline two", encoding="utf-8", newline="\n"
    )
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter, "read_file", {"path": "notes.txt"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert block.text == "line one\nline two"


async def test_search_files_finds_matching_lines(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha needle here\nbeta", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("another needle", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter, "search_files", {"pattern": "needle"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert "a.txt:1" in block.text
    assert "sub/b.txt:1" in block.text


async def test_run_command_captures_output_and_exit_status(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    python = sys.executable

    outputs = await _invoke(
        adapter,
        "run_command",
        {"command": f'"{python}" -c "print(40 + 2)"'},
        _context(tmp_path),
    )
    (block,) = outputs
    assert isinstance(block, TextBlock)
    assert "42" in block.text

    outputs = await _invoke(
        adapter,
        "run_command",
        {"command": f'"{python}" -c "import sys; sys.exit(3)"'},
        _context(tmp_path),
    )
    assert any(
        isinstance(output, ErrorOutput) and "exit code 3" in output.message
        for output in outputs
    )


async def test_ask_user_without_a_broker_is_an_error_output(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()

    (error,) = await _invoke(
        adapter,
        "ask_user",
        {"questions": [{"text": "are you there?"}]},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)


# --- output-size reduction (FR-026) ----------------------------------------------


def test_reduce_outputs_keeps_small_results_untouched() -> None:
    outputs: list[OutputBlock] = [TextBlock(text="small")]
    assert reduce_outputs(outputs, limit_bytes=1024) == outputs


def test_reduce_outputs_truncates_with_a_marker() -> None:
    outputs: list[OutputBlock] = [TextBlock(text="x" * 1000)]

    reduced = reduce_outputs(outputs, limit_bytes=100)

    assert isinstance(reduced[0], TextBlock)
    assert len(reduced[0].text) == 100
    assert isinstance(reduced[-1], TextBlock)
    assert "truncated" in reduced[-1].text
