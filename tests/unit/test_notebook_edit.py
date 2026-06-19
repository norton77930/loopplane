"""Unit tests for the notebook_edit tool on the Internal Tool Adapter (spec 046).
Deterministic and offline.
"""

from __future__ import annotations

import json
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


def _code(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "source": source,
        "metadata": {},
        "outputs": [{"output_type": "stream", "text": "hi"}],
        "execution_count": 3,
    }


def _notebook(*cells: dict[str, object]) -> str:
    return json.dumps(
        {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"name": "python3"}},
            "cells": list(cells),
        },
        indent=1,
    )


def _doc(path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text("utf-8"))
    assert isinstance(parsed, dict)
    return parsed


# --- US1: edit a cell ---------------------------------------------------------


async def test_replace_preserves_other_content(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(
        _notebook(_code("a = 1"), {"cell_type": "markdown", "source": "# t"}),
        encoding="utf-8",
    )
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "nb.ipynb"}, context)
    (block,) = await _invoke(
        adapter,
        "notebook_edit",
        {"path": "nb.ipynb", "mode": "replace", "index": 0, "source": "a = 2"},
        context,
    )

    assert isinstance(block, TextBlock)
    doc = _doc(path)
    cells = doc["cells"]
    assert isinstance(cells, list)
    assert cells[0]["source"] == "a = 2"
    # Replace sets only the source; the cell's outputs/execution_count are preserved.
    assert cells[0]["outputs"] == [{"output_type": "stream", "text": "hi"}]
    assert cells[0]["execution_count"] == 3
    # Other cell + top-level nbformat preserved.
    assert cells[1]["source"] == "# t"
    assert doc["nbformat"] == 4
    assert len(cells) == 2


async def test_insert_shifts_cells(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(_notebook(_code("a = 1"), _code("b = 2")), encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "nb.ipynb"}, context)
    await _invoke(
        adapter,
        "notebook_edit",
        {
            "path": "nb.ipynb",
            "mode": "insert",
            "index": 1,
            "source": "# note",
            "cell_type": "markdown",
        },
        context,
    )

    cells = _doc(path)["cells"]
    assert isinstance(cells, list)
    assert len(cells) == 3
    assert cells[1]["cell_type"] == "markdown"
    assert cells[1]["source"] == "# note"
    assert cells[2]["source"] == "b = 2"


async def test_insert_at_end_appends_code_cell(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(_notebook(_code("a = 1")), encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "nb.ipynb"}, context)
    await _invoke(
        adapter,
        "notebook_edit",
        {
            "path": "nb.ipynb",
            "mode": "insert",
            "index": 1,
            "source": "c = 3",
            "cell_type": "code",
        },
        context,
    )

    cells = _doc(path)["cells"]
    assert isinstance(cells, list)
    assert len(cells) == 2
    assert cells[1]["source"] == "c = 3"
    assert cells[1]["outputs"] == []
    assert cells[1]["execution_count"] is None


async def test_delete_removes_cell(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(_notebook(_code("a = 1"), _code("b = 2")), encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "nb.ipynb"}, context)
    await _invoke(
        adapter,
        "notebook_edit",
        {"path": "nb.ipynb", "mode": "delete", "index": 0},
        context,
    )

    cells = _doc(path)["cells"]
    assert isinstance(cells, list)
    assert len(cells) == 1
    assert cells[0]["source"] == "b = 2"


# --- US2: guards (failures never write) ---------------------------------------


async def test_edit_without_a_read_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(_notebook(_code("a = 1")), encoding="utf-8")
    adapter = InternalToolAdapter()

    (error,) = await _invoke(
        adapter,
        "notebook_edit",
        {"path": "nb.ipynb", "mode": "replace", "index": 0, "source": "x"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    cells = _doc(path)["cells"]
    assert isinstance(cells, list)
    assert cells[0]["source"] == "a = 1"


async def test_changed_since_read_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(_notebook(_code("a = 1")), encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "nb.ipynb"}, context)
    path.write_text(_notebook(_code("a = 999")), encoding="utf-8")
    (error,) = await _invoke(
        adapter,
        "notebook_edit",
        {"path": "nb.ipynb", "mode": "replace", "index": 0, "source": "x"},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_out_of_range_index_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "nb.ipynb"
    path.write_text(_notebook(_code("a = 1")), encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "nb.ipynb"}, context)
    (error,) = await _invoke(
        adapter,
        "notebook_edit",
        {"path": "nb.ipynb", "mode": "delete", "index": 5},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    cells = _doc(path)["cells"]
    assert isinstance(cells, list)
    assert len(cells) == 1


async def test_not_a_notebook_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "data.ipynb"
    path.write_text('{"foo": "bar"}', encoding="utf-8")
    adapter = InternalToolAdapter()
    context = _context(tmp_path)

    await _invoke(adapter, "read_file", {"path": "data.ipynb"}, context)
    (error,) = await _invoke(
        adapter,
        "notebook_edit",
        {"path": "data.ipynb", "mode": "delete", "index": 0},
        context,
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


# --- US3: governed & scoped ---------------------------------------------------


async def test_path_outside_scope_is_rejected(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()

    (error,) = await _invoke(
        adapter,
        "notebook_edit",
        {"path": "../outside.ipynb", "mode": "delete", "index": 0},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"


async def test_describe_includes_notebook_edit_as_mutating() -> None:
    descriptors = {d.name: d for d in InternalToolAdapter().describe()}

    assert "notebook_edit" in descriptors
    assert descriptors["notebook_edit"].read_only is False
