"""Workspace Reference / Binding (078 T035/T040)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

from mutation_lease import ProfileMutationLease  # noqa: E402
from workspace import WorkspaceStore  # noqa: E402


def test_bind_list_projects_safe_reference_without_path(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    store = WorkspaceStore(state)
    target = tmp_path / "ws"
    target.mkdir()
    ref = store.bind(target, label="Docs")
    assert "id" in ref
    assert ref["label"] == "Docs"
    assert ref["availability"] == "available"
    blob = str(ref)
    assert str(target) not in blob
    assert ":" not in blob or "file" not in blob.lower()  # no absolute path leak
    listed = store.list()
    assert len(listed) == 1
    assert str(target) not in str(listed)


def test_relink_required_blocks_binding_lookup(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    store = WorkspaceStore(state)
    target = tmp_path / "ws"
    target.mkdir()
    ref = store.bind(target, label="Docs")
    store.mark_relink_required(ref["id"])
    with pytest.raises(LookupError) as exc:
        store.resolve_path(ref["id"])
    assert "relink" in str(exc.value).lower()


def test_stale_identical_id_binding_ignored_until_relink(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    store = WorkspaceStore(state)
    target = tmp_path / "ws"
    target.mkdir()
    ref = store.bind(target, label="Docs")
    # Simulate restore: mark relink_required but leave old binding bytes.
    store.mark_relink_required(ref["id"])
    with pytest.raises(LookupError):
        store.resolve_path(ref["id"])
    # Explicit relink creates usable binding again.
    other = tmp_path / "ws2"
    other.mkdir()
    updated = store.relink(ref["id"], other)
    assert updated["id"] == ref["id"]
    assert updated["availability"] == "available"
    assert store.resolve_path(ref["id"]) == other.resolve()


def test_revalidate_requires_mutation_lease(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    store = WorkspaceStore(state)
    lease = ProfileMutationLease()
    target = tmp_path / "ws"
    target.mkdir()
    ref = store.bind(target, label="Docs")
    # Backup/restore owner holds lease → revalidate busy.
    lease.acquire("backup")
    with pytest.raises(RuntimeError) as exc:
        store.revalidate(ref["id"], lease=lease)
    assert (
        getattr(exc.value, "public_code", "") == "busy"
        or "busy" in str(exc.value).lower()
    )
    lease.release()
    out = store.revalidate(ref["id"], lease=lease)
    assert out["availability"] == "available"


def test_remove_reference_does_not_delete_directory(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    store = WorkspaceStore(state)
    target = tmp_path / "ws"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("x", encoding="utf-8")
    ref = store.bind(target, label="Docs")
    store.remove(ref["id"])
    assert marker.is_file()
    assert store.list() == []
