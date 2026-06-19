"""Unit tests for the file-tool-parity additions to the Internal Tool Adapter
(spec 033): edit_file, glob_files, and grep. All deterministic and offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import TextBlock
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


# --- edit_file (US1) ----------------------------------------------------------


async def test_edit_file_replaces_unique_occurrence_after_read(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("alpha beta gamma", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    outputs = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "beta", "new_string": "BETA"},
        context,
    )

    assert all(not isinstance(output, ErrorOutput) for output in outputs)
    assert (tmp_path / "doc.txt").read_text("utf-8") == "alpha BETA gamma"


async def test_edit_file_refreshes_digest_for_a_second_edit(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("one two three", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "one", "new_string": "ONE"},
        context,
    )
    # A second edit without an intervening read must still succeed because the
    # first edit refreshed the recorded digest.
    outputs = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "three", "new_string": "THREE"},
        context,
    )

    assert all(not isinstance(output, ErrorOutput) for output in outputs)
    assert (tmp_path / "doc.txt").read_text("utf-8") == "ONE two THREE"


async def test_edit_file_without_a_read_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("original", encoding="utf-8")
    adapter = InternalToolAdapter()

    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "original", "new_string": "changed"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert (tmp_path / "doc.txt").read_text("utf-8") == "original"


async def test_edit_file_after_external_change_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "doc.txt"
    target.write_text("v1 content", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    target.write_text("v1 content changed", encoding="utf-8")
    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "content", "new_string": "CONTENT"},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert "changed since" in error.message


async def test_edit_file_missing_old_string_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("hello world", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "absent", "new_string": "x"},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert (tmp_path / "doc.txt").read_text("utf-8") == "hello world"


async def test_edit_file_non_unique_old_string_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("foo\nfoo\n", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "foo", "new_string": "bar"},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert (tmp_path / "doc.txt").read_text("utf-8") == "foo\nfoo\n"


async def test_edit_file_identical_strings_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("keep me", encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "doc.txt"}, context)
    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "doc.txt", "old_string": "keep", "new_string": "keep"},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_edit_file_path_escape_is_rejected(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "../outside.txt", "old_string": "a", "new_string": "b"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_edit_file_nonexistent_file_is_an_error(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    (error,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "ghost.txt", "old_string": "a", "new_string": "b"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)


# --- glob_files (US2) ---------------------------------------------------------


async def test_glob_files_returns_matching_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("", encoding="utf-8")
    (tmp_path / "c.txt").write_text("", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter, "glob_files", {"pattern": "**/*.py"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert "a.py" in block.text
    assert "sub/b.py" in block.text
    assert "c.txt" not in block.text


async def test_glob_files_excludes_directories(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter, "glob_files", {"pattern": "*"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert "a.txt" in block.text
    # "sub" is a directory and must not be listed.
    assert not any(line.strip() == "sub" for line in block.text.splitlines())


async def test_glob_files_no_match_is_not_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter, "glob_files", {"pattern": "**/*.rs"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert not isinstance(block, ErrorOutput)


async def test_glob_files_path_escape_is_rejected(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    (error,) = await _invoke(
        adapter,
        "glob_files",
        {"pattern": "*", "path": ".."},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


# --- grep (US3) ---------------------------------------------------------------


async def test_grep_content_mode_returns_lines(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha NEEDLE here\nbeta", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(adapter, "grep", {"pattern": "N.+LE"}, _context(tmp_path))

    assert isinstance(block, TextBlock)
    assert "a.txt:1" in block.text
    assert "NEEDLE" in block.text


async def test_grep_defaults_to_content_mode(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("match here", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(adapter, "grep", {"pattern": "match"}, _context(tmp_path))

    assert isinstance(block, TextBlock)
    assert "a.txt:1" in block.text


async def test_grep_files_with_matches_mode(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("needle", encoding="utf-8")
    (tmp_path / "b.txt").write_text("needle needle", encoding="utf-8")
    (tmp_path / "c.txt").write_text("nothing", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter,
        "grep",
        {"pattern": "needle", "output_mode": "files_with_matches"},
        _context(tmp_path),
    )

    assert isinstance(block, TextBlock)
    assert "a.txt" in block.text
    assert "b.txt" in block.text
    assert "c.txt" not in block.text
    # No line numbers in files_with_matches mode.
    assert ":1:" not in block.text


async def test_grep_count_mode(tmp_path: Path) -> None:
    # count = number of matching lines per file (ripgrep -c convention), so two
    # matching lines yield 2 even though only one keyword appears per line.
    (tmp_path / "b.txt").write_text("needle\nneedle\n", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(
        adapter,
        "grep",
        {"pattern": "needle", "output_mode": "count"},
        _context(tmp_path),
    )

    assert isinstance(block, TextBlock)
    assert "b.txt: 2" in block.text


async def test_grep_invalid_regex_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    adapter = InternalToolAdapter()

    (error,) = await _invoke(
        adapter, "grep", {"pattern": "([unterminated"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_grep_invalid_output_mode_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    adapter = InternalToolAdapter()

    (error,) = await _invoke(
        adapter,
        "grep",
        {"pattern": "x", "output_mode": "bogus"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_grep_path_escape_is_rejected(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()
    (error,) = await _invoke(
        adapter,
        "grep",
        {"pattern": "x", "path": "../.."},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_grep_no_match_is_not_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    adapter = InternalToolAdapter()

    (block,) = await _invoke(adapter, "grep", {"pattern": "zzz"}, _context(tmp_path))

    assert isinstance(block, TextBlock)
    assert not isinstance(block, ErrorOutput)
