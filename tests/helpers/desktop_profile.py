"""Desktop profile / ownership-lock / generation fixtures (T014)."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

CheckpointState = Literal["absent_uninitialized", "initialized", "unexpected"]
ArtifactState = Literal["absent_uninitialized", "initialized", "unexpected"]


@dataclass
class GenerationReceipt:
    generation_id: str
    checkpoint_state: CheckpointState
    artifact_state: ArtifactState
    schema_version: int = 1


@dataclass
class ProfileFixture:
    """Temporary profile root with optional alias path and lock file."""

    root: Path
    alias: Path | None = None
    lock_path: Path | None = None
    pointer_path: Path | None = None
    proof_path: Path | None = None
    receipt: GenerationReceipt | None = None
    journals: list[Path] = field(default_factory=list)
    _tmpdir: tempfile.TemporaryDirectory[str] | None = None

    def cleanup(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None


def make_profile_root(*, with_alias: bool = False) -> ProfileFixture:
    tmp = tempfile.TemporaryDirectory(prefix="lp-desk-profile-")
    root = Path(tmp.name) / "profile"
    root.mkdir(parents=True)
    alias: Path | None = None
    if with_alias:
        alias = Path(tmp.name) / "alias-profile"
        try:
            os.symlink(root, alias, target_is_directory=True)
        except OSError:
            # Windows without privilege: create a junction-like second path via
            # a nested directory pointing at the same files by copy of path only.
            alias = root
    lock_path = root / "device-private" / "profile-owner.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return ProfileFixture(root=root, alias=alias, lock_path=lock_path, _tmpdir=tmp)


def write_pristine_absent_states(fx: ProfileFixture) -> GenerationReceipt:
    """Pristine profile: explicit absent_uninitialized, no store files."""

    gen = fx.root / "generations" / "g0"
    gen.mkdir(parents=True, exist_ok=True)
    receipt = GenerationReceipt(
        generation_id="g0",
        checkpoint_state="absent_uninitialized",
        artifact_state="absent_uninitialized",
    )
    fx.receipt = receipt
    fx.proof_path = gen / "proof.json"
    fx.pointer_path = fx.root / "current-generation"
    fx.proof_path.write_text(
        json.dumps(
            {
                "generation_id": receipt.generation_id,
                "checkpoint_state": receipt.checkpoint_state,
                "artifact_state": receipt.artifact_state,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Pristine bootstrap: proof without pointer until publication completes.
    return receipt


def write_unexpected_payload(fx: ProfileFixture) -> Path:
    """Unexpected pre-Host payload that must fail closed."""

    gen = fx.root / "generations" / "g-bad"
    gen.mkdir(parents=True, exist_ok=True)
    bad = gen / "checkpoint.sqlite"
    bad.write_bytes(b"NOT-A-SQLITE-UNEXPECTED")
    return bad


def acquire_ownership_lock(fx: ProfileFixture) -> Path:
    assert fx.lock_path is not None
    fx.lock_path.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
    return fx.lock_path


def ownership_lock_contention(fx: ProfileFixture) -> bool:
    """Return True if lock file already exists (second process would be busy)."""

    assert fx.lock_path is not None
    return fx.lock_path.is_file()


def release_ownership_lock(fx: ProfileFixture) -> None:
    assert fx.lock_path is not None
    if fx.lock_path.is_file():
        fx.lock_path.unlink()


def write_dual_journals(fx: ProfileFixture) -> list[Path]:
    jdir = fx.root / "journals"
    jdir.mkdir(parents=True, exist_ok=True)
    paths = [jdir / "slot-a.preimage", jdir / "slot-b.preimage"]
    for p in paths:
        p.write_bytes(b"preimage")
    fx.journals = paths
    return paths


def project_record(
    *,
    project_id: str = "proj-1",
    name: str = "Demo",
) -> dict[str, Any]:
    return {"id": project_id, "name": name, "session_ids": []}


def workspace_binding(
    *,
    workspace_id: str = "ws-1",
    label: str = "Work",
    relink_required: bool = False,
    private_path: str = "",
) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "label": label,
        "relink_required": relink_required,
        "private_path": private_path or str(Path.cwd()),
        "availability": "unavailable" if relink_required else "available",
    }


def all_writer_reservation(
    *,
    owner: str = "backup",
    held: bool = True,
) -> dict[str, Any]:
    return {
        "lease": "profile_mutation",
        "owner": owner,
        "held": held,
        "rejects": [
            "session.create",
            "session.rename",
            "interaction.submit",
            "project.create",
            "workspace.revalidate",
            "backup.create",
            "restore.validate",
        ],
    }


def stale_binding_same_ids() -> dict[str, Any]:
    """Identical profile/workspace IDs that must be ignored until explicit relink."""

    return {
        "profile_id": "p1",
        "workspace_id": "ws-1",
        "stale": True,
        "relink_required": True,
    }


def platform_publication_notes() -> dict[str, str]:
    return {
        "posix": "file+directory+parent fsync physical-power-loss claim",
        "windows": "flush+write-through move+reopen process-crash claim only",
    }
