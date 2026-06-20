"""File-edit undo tool tests (spec 054). Offline + deterministic."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import TextBlock
from loopplane.tools.internal import InternalToolAdapter

pytestmark = pytest.mark.anyio


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(session_id="s", working_scope=tmp_path)


async def _invoke(
    adapter: InternalToolAdapter,
    name: str,
    call_input: dict[str, object],
    ctx: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, ctx)]


async def _overwrite(
    adapter: InternalToolAdapter, ctx: RunContext, path: str, content: str
) -> None:
    """Read (to satisfy the stale-write guard) then overwrite an existing file."""
    await _invoke(adapter, "read_file", {"path": path}, ctx)
    await _invoke(adapter, "write_file", {"path": path, "content": content}, ctx)


# --- US1: snapshot + undo -----------------------------------------------------


async def test_undo_restores_overwritten_file(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    ctx = _ctx(tmp_path)
    await _invoke(adapter, "write_file", {"path": "f.txt", "content": "v1"}, ctx)
    await _overwrite(adapter, ctx, "f.txt", "v2")
    assert (tmp_path / "f.txt").read_text() == "v2"
    (out,) = await _invoke(adapter, "undo_file", {"path": "f.txt"}, ctx)
    assert isinstance(out, TextBlock) and "reverted" in out.text
    assert (tmp_path / "f.txt").read_text() == "v1"


async def test_undo_walks_back_then_reports_nothing(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    ctx = _ctx(tmp_path)
    await _invoke(adapter, "write_file", {"path": "f.txt", "content": "v1"}, ctx)
    await _overwrite(adapter, ctx, "f.txt", "v2")  # snapshot v1
    await _overwrite(adapter, ctx, "f.txt", "v3")  # snapshot v2
    await _invoke(adapter, "undo_file", {"path": "f.txt"}, ctx)
    assert (tmp_path / "f.txt").read_text() == "v2"
    await _invoke(adapter, "undo_file", {"path": "f.txt"}, ctx)
    assert (tmp_path / "f.txt").read_text() == "v1"
    (out,) = await _invoke(adapter, "undo_file", {"path": "f.txt"}, ctx)
    assert isinstance(out, TextBlock) and "nothing to undo" in out.text


async def test_undo_works_for_edit_file(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    ctx = _ctx(tmp_path)
    await _invoke(adapter, "write_file", {"path": "f.txt", "content": "alpha"}, ctx)
    await _invoke(adapter, "read_file", {"path": "f.txt"}, ctx)
    await _invoke(
        adapter,
        "edit_file",
        {"path": "f.txt", "old_string": "alpha", "new_string": "beta"},
        ctx,
    )
    assert (tmp_path / "f.txt").read_text() == "beta"
    await _invoke(adapter, "undo_file", {"path": "f.txt"}, ctx)
    assert (tmp_path / "f.txt").read_text() == "alpha"


# --- US2: scoped, re-synced, faithful -----------------------------------------


async def test_undo_resyncs_stale_write_guard(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    ctx = _ctx(tmp_path)
    await _invoke(
        adapter, "write_file", {"path": "f.txt", "content": "hello world"}, ctx
    )
    await _overwrite(adapter, ctx, "f.txt", "goodbye world")
    await _invoke(
        adapter, "undo_file", {"path": "f.txt"}, ctx
    )  # restores "hello world"
    # An edit right after undo is accepted (the stale-write guard was re-synced).
    (out,) = await _invoke(
        adapter,
        "edit_file",
        {"path": "f.txt", "old_string": "hello", "new_string": "hi"},
        ctx,
    )
    assert isinstance(out, TextBlock) and "edited" in out.text
    assert (tmp_path / "f.txt").read_text() == "hi world"


async def test_undo_restores_binary_faithfully(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    ctx = _ctx(tmp_path)
    raw = b"\xff\xfe\x00\x01binary\x80data"
    (tmp_path / "f.bin").write_bytes(raw)
    await _invoke(adapter, "read_file", {"path": "f.bin"}, ctx)
    await _invoke(adapter, "write_file", {"path": "f.bin", "content": "text"}, ctx)
    assert (tmp_path / "f.bin").read_bytes() != raw
    await _invoke(adapter, "undo_file", {"path": "f.bin"}, ctx)
    assert (tmp_path / "f.bin").read_bytes() == raw  # exact raw bytes restored


async def test_undo_out_of_scope_errors(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    (out,) = await _invoke(
        adapter, "undo_file", {"path": "../escape.txt"}, _ctx(tmp_path)
    )
    assert isinstance(out, ErrorOutput)


async def test_undo_unknown_path_reports_nothing(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=5)
    (out,) = await _invoke(adapter, "undo_file", {"path": "never.txt"}, _ctx(tmp_path))
    assert isinstance(out, TextBlock) and "nothing to undo" in out.text


# --- US3: bounded + default-off -----------------------------------------------


async def test_snapshot_cap_drops_oldest(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(max_file_snapshots=2)
    ctx = _ctx(tmp_path)
    await _invoke(adapter, "write_file", {"path": "f.txt", "content": "v1"}, ctx)
    for content in ("v2", "v3", "v4"):  # three overwrites -> three snapshots
        await _overwrite(adapter, ctx, "f.txt", content)
    assert len(adapter._snapshots) == 2  # noqa: SLF001 - capped, oldest dropped


async def test_default_off_no_tool_no_snapshot(tmp_path: Path) -> None:
    adapter = InternalToolAdapter()  # default max_file_snapshots=0
    ctx = _ctx(tmp_path)
    assert "undo_file" not in {d.name for d in adapter.describe()}
    await _invoke(adapter, "write_file", {"path": "f.txt", "content": "v1"}, ctx)
    await _overwrite(adapter, ctx, "f.txt", "v2")
    assert adapter._snapshots == []  # noqa: SLF001 - no snapshot taken when disabled


async def test_enabled_registers_undo_file() -> None:
    adapter = InternalToolAdapter(max_file_snapshots=3)
    assert "undo_file" in {d.name for d in adapter.describe()}
