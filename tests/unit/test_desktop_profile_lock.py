"""Profile ownership lock tests (078 T018/T025)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import (  # noqa: E402
    ProfileBusyError,
    ProfileLockUnsupportedError,
    ProfileOwnershipLock,
    same_canonical_root,
)

from durability import (  # noqa: E402
    has_restore_journals,
    publish_pristine_generation,
    read_proof,
)


def _create_directory_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("Windows junction creation is unavailable")


def test_same_canonical_root(tmp_path: Path) -> None:
    a = tmp_path / "p"
    a.mkdir()
    assert same_canonical_root(a, a / ".")


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
@pytest.mark.parametrize("alias_level", ["directory", "file"])
def test_profile_lock_rejects_preserved_name_alias(
    tmp_path: Path, alias_level: str
) -> None:
    """The ownership lock requires exact collection and leaf names."""

    root = tmp_path / "profile"
    root.mkdir()
    if alias_level == "directory":
        alias = root / "Device-Private"
        alias.mkdir()
    else:
        alias = root / "device-private" / "Profile-Owner.Lock"
        alias.parent.mkdir()
        alias.write_bytes(b"")

    lock = ProfileOwnershipLock.for_root(root)
    with pytest.raises(ProfileLockUnsupportedError, match="unsafe profile lock"):
        lock.acquire()

    assert alias.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction lock boundary")
def test_profile_lock_rejects_device_private_junction_without_external_write(
    tmp_path: Path,
) -> None:
    """A junction cannot redirect the process-wide profile ownership lock."""

    root = tmp_path / "profile"
    root.mkdir()
    external = tmp_path / "external-lock"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    link = root / "device-private"
    _create_directory_junction(link, external)

    try:
        lock = ProfileOwnershipLock.for_root(root)
        with pytest.raises(ProfileLockUnsupportedError, match="unsafe profile lock"):
            lock.acquire()
        assert sentinel.read_text(encoding="utf-8") == "keep"
        assert not (external / "profile-owner.lock").exists()
    finally:
        if os.path.lexists(link):
            os.rmdir(link)


def test_lock_exclusive_second_process_busy(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    lock1 = ProfileOwnershipLock.for_root(root)
    lock1.acquire()
    try:
        lock2 = ProfileOwnershipLock.for_root(root)
        with pytest.raises(ProfileBusyError):
            lock2.acquire()
    finally:
        lock1.release()


def test_pristine_publish_proof_without_sqlite(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    root.mkdir()
    proof = publish_pristine_generation(root, "g0")
    data = read_proof(root, "g0")
    assert data["checkpoint_state"] == "absent_uninitialized"
    assert data["artifact_state"] == "absent_uninitialized"
    assert not list(root.rglob("*.sqlite"))
    assert proof.is_file()
    assert has_restore_journals(root) is False
