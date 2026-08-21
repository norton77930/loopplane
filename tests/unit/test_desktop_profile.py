"""Desktop profile principal/projects/portable state (078 T034/T039)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import (  # noqa: E402
    PORTABLE_EXCLUDE_LOCK_NAME,
    ProfileBusyError,
    ProfileOwnershipLock,
    ProfileState,
    same_canonical_root,
)

from projects import ProjectStore  # noqa: E402
from runtime import DesktopRuntimeOwner  # noqa: E402


@pytest.mark.parametrize(
    "generation_id",
    ["G0", "g0.", "g0 ", "../outside", "-g0", "g0-", "g0--next", "con"],
)
def test_profile_rejects_noncanonical_generation_before_writing(
    tmp_path: Path, generation_id: str
) -> None:
    """Portable profile state never composes a path from an aliased generation id."""

    root = tmp_path / "profile"

    with pytest.raises(ValueError, match="generation id"):
        ProfileState.open(root, generation_id=generation_id)

    assert not root.exists()


def test_profile_rejects_absolute_generation_before_writing(tmp_path: Path) -> None:
    """An absolute generation value never replaces the profile-owned base path."""

    root = tmp_path / "profile"
    outside = (tmp_path / "outside").resolve()

    with pytest.raises(ValueError, match="generation id"):
        ProfileState.open(root, generation_id=str(outside))

    assert not root.exists()
    assert not outside.exists()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
def test_profile_rejects_case_aliased_generation_directory(tmp_path: Path) -> None:
    """ProfileState requires the preserved leaf name to exactly match authority."""

    root = tmp_path / "profile"
    alias = root / "generations" / "G0"
    alias.mkdir(parents=True)

    with pytest.raises(ValueError, match="generation path"):
        ProfileState.open(root, generation_id="g0")

    assert list(alias.iterdir()) == []


def test_profile_creates_immutable_principal_and_profile_id(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    assert state.principal_id
    assert state.profile_id
    first_principal = state.principal_id
    first_profile = state.profile_id
    # Restart load preserves principal (immutable).
    state2 = ProfileState.open(root)
    assert state2.principal_id == first_principal
    assert state2.profile_id == first_profile


def test_drafts_never_written_to_portable_profile_json(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    # Attempting to stash a draft must be rejected / ignored by portable API.
    state.set_preference("theme", "dark")
    portable = state.load_portable()
    assert "draft" not in json.dumps(portable).lower()
    assert "unsent" not in json.dumps(portable).lower()
    # Explicit draft keys are stripped if injected.
    with pytest.raises(ValueError):
        state.set_preference("composer_draft", "secret unsent text")


def test_profile_owner_lock_excluded_from_portable_export(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    lock = ProfileOwnershipLock.for_root(root)
    lock.acquire()
    try:
        state = ProfileState.open(root)
        names = state.portable_member_names()
        assert PORTABLE_EXCLUDE_LOCK_NAME not in names
        assert "profile-owner.lock" not in names
        assert "device-private" not in names
    finally:
        lock.release()


def test_project_create_list_rename_remove_does_not_delete_sessions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "profile"
    state = ProfileState.open(root)
    store = ProjectStore(state)
    proj = store.create(label="Alpha")
    store.assign_session(proj["id"], "sess-1")
    store.assign_session(proj["id"], "sess-2")
    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["session_ids"] == ["sess-1", "sess-2"]
    store.rename(proj["id"], "Beta")
    store.remove(proj["id"])
    # Sessions remain as data — project removal only ungroups.
    assert store.list() == []
    # Session ids are not owned/deleted by project store.
    assert store.session_project("sess-1") is None


def test_second_process_busy_zero_host(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    owner.bootstrap_generation()
    other = DesktopRuntimeOwner(profile_root=root)
    with pytest.raises(ProfileBusyError):
        other.acquire()
    assert other.host is None
    owner.release()


def test_alias_same_canonical_root(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    assert same_canonical_root(root, root / ".")


def test_runtime_loads_profile_state_after_bootstrap(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    owner.bootstrap_generation()
    state = owner.ensure_profile_state()
    assert state.principal_id
    # Profile portable file lives under generation, not device-private.
    portable_path = state.portable_path()
    assert "device-private" not in portable_path.as_posix()
    assert portable_path.is_file()
    owner.release()
