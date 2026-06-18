"""Unit 028: the UploadStore + the read_upload gateway tool (transient input by id)."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from loopplane.context import RunContext
from loopplane.host.upload_tool import make_read_upload_tool
from loopplane.model import TextBlock
from loopplane.webapi.uploads import UploadStore, UploadTooLarge


def test_store_save_read_info(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("alice", "notes.txt", b"hello world")
    assert stored.owner == "alice"
    assert stored.name == "notes.txt"
    assert stored.size == 11
    assert store.read(stored.reference) == b"hello world"
    info = store.info(stored.reference)
    assert info is not None and info.owner == "alice"
    # references are unguessable + distinct per save
    other = store.save("alice", "x", b"y")
    assert other.reference != stored.reference


def test_store_rejects_oversize(tmp_path: Path) -> None:
    store = UploadStore(tmp_path, max_bytes=4)
    with pytest.raises(UploadTooLarge):
        store.save("alice", "big", b"12345")


def test_store_read_missing_and_rejects_traversal(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    assert store.read("nope") is None
    assert store.read("../secret") is None
    assert store.read("") is None


def test_read_upload_tool_reads_by_reference(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    stored = store.save("alice", "doc.txt", b"the file body")
    tool = make_read_upload_tool(store.read)
    assert tool.descriptor.name == "read_upload"
    assert tool.descriptor.read_only is True
    ctx = RunContext(session_id="s1", working_scope=tmp_path)

    async def call(reference: str) -> list:
        return list(await tool.handler({"reference": reference}, ctx))

    assert anyio.run(call, stored.reference) == [TextBlock(text="the file body")]
    assert anyio.run(call, "nope") == [TextBlock(text="upload not found")]
