"""T070 RED contract matrix for sidecar restore staging and recovery.

These tests use only the public restore manager, RPC-method owner, runtime owner,
and Host validation facade.  Durable candidate publication/journal interpretation
is deliberately expected to remain RED until T078.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import stat
import subprocess
import sys
import warnings
import zipfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol

import pytest

from loopplane.checkpoint import SqliteCheckpointStore
from loopplane.checkpoint.records import SessionMetaRecord, serialize_record

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

from archive import create_portable_archive, validate_archive  # noqa: E402
from interaction import InteractionLease  # noqa: E402
from methods.backup import BackupMethods  # noqa: E402
from methods.inspection import InspectionMethods  # noqa: E402
from methods.interaction import InteractionMethods  # noqa: E402
from methods.projects import ProjectMethods  # noqa: E402
from methods.sessions import SessionMethods  # noqa: E402
from methods.workspace import WorkspaceMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from protocol import RpcError  # noqa: E402
from restore import RestoreManager  # noqa: E402

pytestmark = pytest.mark.anyio

_PLATFORM_DURABILITY_BOUNDARIES = (
    [
        "windows.supported_local_ntfs_refs_check",
        "windows.regular_file_flush_file_buffers",
        "windows.same_volume_write_through_move",
        "windows.post_move_reopen_validation",
        "windows.process_crash_acknowledgement_boundary",
    ]
    if sys.platform == "win32"
    else [
        "posix.file_fsync",
        "posix.bottom_up_directory_fsync",
        "posix.same_volume_rename",
        "posix.former_staging_parent_fsync",
        "posix.generations_parent_fsync",
        "posix.reopen_inventory_schema_sqlite_artifact_validation",
    ]
)


class _SnapshotValidator:
    """Test-owned Host facade; staging is the only value it receives."""

    def __init__(self) -> None:
        self.staged: list[Path] = []

    def validate_portable_snapshot(self, staging: Path) -> SimpleNamespace:
        self.staged.append(staging)
        return SimpleNamespace(ok=True)


class _NoDispatchHost:
    """Fails if a competing writer reaches a Host facade."""

    called = False

    def __getattr__(self, _name: str) -> Callable[..., object]:
        def forbidden(*_args: object, **_kwargs: object) -> object:
            self.called = True
            raise AssertionError("restore reservation must reject before dispatch")

        return forbidden


class RestoreFaultInjector(Protocol):
    """Test-owned public seam for one named spec boundary."""

    def hit(self, boundary: str) -> None:
        """Raise only when the transaction reaches the selected boundary."""
        ...


def _create_directory_alias(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("Windows junction creation is unavailable")
        return
    os.symlink(target, link, target_is_directory=True)


def _remove_directory_alias(link: Path) -> None:
    if sys.platform == "win32":
        os.rmdir(link)
    else:
        link.unlink()


class _FaultAtBoundary:
    def __init__(self, fault: str, *, root: Path | None = None) -> None:
        self.fault = fault
        self.root = root
        self.seen: list[str] = []
        self.effect_snapshot: dict[str, bytes] | None = None

    def snapshot(self) -> dict[str, bytes]:
        assert self.root is not None
        names = (
            "active-generation.json",
            "active-generation-proof.json",
            "restore-journal-a.json",
            "restore-journal-b.json",
            "device-private/workspace-bindings.json",
        )
        return {
            name: (self.root / name).read_bytes()
            if (self.root / name).exists()
            else b""
            for name in names
        }

    def hit(self, boundary: str) -> None:
        self.seen.append(boundary)
        if boundary != self.fault:
            return
        if self.root is not None:
            self.effect_snapshot = self.snapshot()
        raise OSError(f"injected:{boundary}")


class _ReplaceBindingsParentWithAlias:
    """Replace device-private after proof but before stale-binding cleanup."""

    def __init__(self, root: Path, external: Path) -> None:
        self.root = root
        self.external = external
        self.retained = root / "device-private-retained"
        self.link = root / "device-private"
        self.replaced = False

    def hit(self, boundary: str) -> None:
        if boundary != "recovery.stale_bindings_before_unlink":
            return
        self.link.rename(self.retained)
        _create_directory_alias(self.link, self.external)
        self.replaced = True


class _CreateBindingsAliasAfterUnlink:
    """Recreate the exact stale binding name after retained deletion."""

    def __init__(self, root: Path, external: Path) -> None:
        self.link = root / "device-private" / "workspace-bindings.json"
        self.external = external

    def hit(self, boundary: str) -> None:
        if boundary != "recovery.stale_bindings_after_unlink":
            return
        os.link(self.external, self.link)


class _ReplaceStagingParentWithAlias:
    """Swap the first staged member parent at the public fault boundary."""

    def __init__(self, root: Path, external: Path) -> None:
        self.root = root
        self.external = external
        self.link: Path | None = None

    def hit(self, boundary: str) -> None:
        if boundary != "restore.staging_target_ready":
            return
        token_roots = list((self.root / "staging" / "restore").iterdir())
        assert len(token_roots) == 1
        directories = [path for path in token_roots[0].rglob("*") if path.is_dir()]
        assert directories
        parent = max(directories, key=lambda path: len(path.parts))
        parent.rmdir()
        _create_directory_alias(parent, self.external)
        self.link = parent


def _archive_for_restore(root: Path, name: str = "source.zip") -> Path:
    snapshot = root / "snapshot"
    checkpoint = snapshot / "sessions" / "checkpoints.sqlite3"
    SqliteCheckpointStore(checkpoint).initialize()
    archive = root / name
    create_portable_archive(
        archive,
        profile_portable={
            "schema_version": 1,
            "profile_id": "portable-profile",
            "principal_id": "portable-principal",
            "workspace_references": [],
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )
    return archive


def test_restore_preview_reports_exact_empty_snapshot_metadata(tmp_path: Path) -> None:
    """Preview counts durable sessions, not the single checkpoint archive member."""

    archive = _archive_for_restore(tmp_path)
    manifest = validate_archive(archive)
    reservation = RestoreManager(tmp_path / "profile").validate_archive(archive)

    assert reservation.summary == {
        "entry_count": 2,
        "project_count": 0,
        "session_count": 0,
        "artifact_count": 0,
        "has_manifest": True,
        "has_profile": True,
        "format": "loopplane.desktop.backup",
        "version": {"major": 1, "minor": 0},
        "created_at": manifest["created_at"],
        "drafts_excluded": True,
        "relink_required": True,
    }


def _rewrite_archive_member(
    archive_path: Path, member_name: str, member_bytes: bytes
) -> Path:
    """Keep every ZIP/hash contract valid while changing one member's semantics."""

    with zipfile.ZipFile(archive_path, "r") as source:
        manifest = json.loads(source.read("manifest.json"))
        members = {
            info.filename: source.read(info)
            for info in source.infolist()
            if info.filename != "manifest.json"
        }
    members[member_name] = member_bytes
    for entry in manifest["entries"]:
        payload = members[entry["path"]]
        entry["size"] = len(payload)
        entry["sha256"] = hashlib.sha256(payload).hexdigest()
    total = sum(len(payload) for payload in members.values())
    manifest["totals"]["compressed_bytes"] = total
    manifest["totals"]["uncompressed_bytes"] = total
    replacement = archive_path.with_suffix(".replacement.zip")
    with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_STORED) as target:
        for name, payload in [
            ("manifest.json", _canonical_bytes(manifest)),
            *[(entry["path"], members[entry["path"]]) for entry in manifest["entries"]],
        ]:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = stat.S_IFREG << 16
            target.writestr(info, payload)
    return replacement


def _rewrite_archive_profile(archive_path: Path, profile_bytes: bytes) -> Path:
    return _rewrite_archive_member(archive_path, "profile/profile.json", profile_bytes)


def _archive_without_member(archive_path: Path, member_name: str) -> Path:
    with zipfile.ZipFile(archive_path, "r") as source:
        manifest = json.loads(source.read("manifest.json"))
        members = {
            info.filename: source.read(info)
            for info in source.infolist()
            if info.filename not in {"manifest.json", member_name}
        }
    manifest["entries"] = [
        entry for entry in manifest["entries"] if entry["path"] != member_name
    ]
    total = sum(len(payload) for payload in members.values())
    manifest["totals"] = {
        "compressed_bytes": total,
        "entries": len(manifest["entries"]),
        "uncompressed_bytes": total,
    }
    replacement = archive_path.with_suffix(".missing.zip")
    with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_STORED) as target:
        for name, payload in [
            ("manifest.json", _canonical_bytes(manifest)),
            *[(entry["path"], members[entry["path"]]) for entry in manifest["entries"]],
        ]:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = stat.S_IFREG << 16
            target.writestr(info, payload)
    return replacement


def _methods_with_pending_restore(
    root: Path,
) -> tuple[BackupMethods, RestoreManager, ProfileMutationLease, str, Path]:
    archive = _archive_for_restore(root)
    state = ProfileState.open(root / "profile")
    manager = RestoreManager(state.root)
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=manager,
    )
    return methods, manager, lease, "restore-owner", archive


def _manifest(entries: list[tuple[str, str, bytes]]) -> dict[str, Any]:
    declared = [
        {
            "path": path,
            "kind": "regular_file",
            "content_class": content_class,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, content_class, payload in entries
    ]
    return {
        "format": "loopplane.desktop.backup",
        "version": {"major": 1, "minor": 0},
        "profile_schema_version": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "profile_id": "portable-profile",
        "principal_id": "portable-principal",
        "disclosure": {"version": 1, "acknowledged": True},
        "totals": {
            "entries": len(declared),
            "compressed_bytes": sum(len(payload) for _, _, payload in entries),
            "uncompressed_bytes": sum(len(payload) for _, _, payload in entries),
        },
        "entries": declared,
    }


def _write_unvalidated_archive(
    path: Path,
    entries: list[tuple[str, str, bytes]],
    *,
    manifest_first: bool = True,
    duplicate_member: bool = False,
    compression: int = zipfile.ZIP_STORED,
    external_mode: int = stat.S_IFREG,
    corrupt_digest: bool = False,
) -> None:
    manifest = _manifest(entries)
    if corrupt_digest:
        manifest["entries"][0]["sha256"] = "0" * 64
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        ordered: list[tuple[str, bytes, int]] = [
            (name, payload, external_mode) for name, _kind, payload in entries
        ]
        if manifest_first:
            ordered.insert(0, ("manifest.json", manifest_bytes, stat.S_IFREG))
        else:
            ordered.append(("manifest.json", manifest_bytes, stat.S_IFREG))
        for name, payload, mode in ordered:
            info = zipfile.ZipInfo(name)
            info.compress_type = compression
            info.external_attr = mode << 16
            archive.writestr(info, payload)
        if duplicate_member:
            name, _kind, payload = entries[-1]
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="Duplicate name", category=UserWarning
                )
                archive.writestr(name, payload)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt(generation: str, nonce: str) -> tuple[dict[str, Any], str]:
    receipt = {
        "artifact_state": "absent_uninitialized",
        "checkpoint_state": "initialized",
        "generation_id": generation,
        "platform": "test",
        "publication_nonce": nonce,
        "publication_sequence": 1,
        "receipt_version": 1,
        "schema_version": 1,
        "validation_digest": hashlib.sha256(b"test-validation").hexdigest(),
    }
    return receipt, hashlib.sha256(_canonical_bytes(receipt)).hexdigest()


def _recovery_bytes(generation: str, nonce: str) -> tuple[bytes, bytes]:
    receipt, receipt_digest = _receipt(generation, nonce)
    pointer = _canonical_bytes(
        {"generation_id": generation, "receipt_sha256": receipt_digest}
    )
    proof = {
        "active_generation": generation,
        "active_pointer_bytes_b64": base64.b64encode(pointer).decode("ascii"),
        "active_pointer_sha256": hashlib.sha256(pointer).hexdigest(),
        "generation_publication_receipt": receipt,
        "generation_receipt_sha256": receipt_digest,
        "proof_kind": "restore",
        "proof_sequence": 1,
        "proof_version": 1,
        "restore_id": "restore-1",
        "verified_at": "2026-01-01T00:00:00Z",
    }
    proof["record_sha256"] = hashlib.sha256(_canonical_bytes(proof)).hexdigest()
    return pointer, _canonical_bytes(proof)


def _journal_record(
    *,
    slot: str,
    state: str,
    sequence: int,
    previous_pointer: bytes,
    previous_proof: bytes,
    candidate_pointer: bytes,
    candidate_generation: str = "candidate",
    previous_generation: str = "previous",
) -> bytes:
    candidate_receipt, candidate_receipt_digest = _receipt(
        candidate_generation, "after"
    )
    candidate_pointer_b64 = base64.b64encode(candidate_pointer).decode("ascii")
    previous_pointer_b64 = base64.b64encode(previous_pointer).decode("ascii")
    previous_proof_b64 = base64.b64encode(previous_proof).decode("ascii")
    record = {
        "archive_sha256": hashlib.sha256(b"selected-archive").hexdigest(),
        "candidate_generation": candidate_generation,
        "candidate_generation_publication_receipt": candidate_receipt,
        "candidate_generation_receipt_sha256": candidate_receipt_digest,
        "candidate_pointer_bytes_b64": candidate_pointer_b64,
        "candidate_pointer_sha256": hashlib.sha256(candidate_pointer).hexdigest(),
        "candidate_proof_sha256": None,
        "journal_sequence": sequence,
        "journal_version": 1,
        "previous_generation": previous_generation,
        "previous_pointer_bytes_b64": previous_pointer_b64,
        "previous_pointer_sha256": hashlib.sha256(previous_pointer).hexdigest(),
        "previous_proof_bytes_b64": previous_proof_b64,
        "previous_proof_sha256": hashlib.sha256(previous_proof).hexdigest(),
        "restore_id": "restore-1",
        "slot": slot,
        "state": state,
        "updated_at": "2026-01-01T00:00:00Z",
    }
    record["record_sha256"] = hashlib.sha256(_canonical_bytes(record)).hexdigest()
    return _canonical_bytes(record)


def _prepare_pristine_generation(root: Path, generation: str) -> None:
    """Create the on-disk candidate shape accepted by the public snapshot validator."""

    generation_root = root / "generations" / generation
    profile = generation_root / "profile" / "profile.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_bytes(
        _canonical_bytes(
            {
                "preferences": {},
                "principal_id": "portable-principal",
                "profile_id": "portable-profile",
                "projects": [],
                "schema_version": 1,
                "workspace_references": [],
            }
        )
    )
    checkpoint = generation_root / "sessions" / "checkpoints.sqlite3"
    runtime_checkpoint = (
        root / "generation-storage" / generation / "checkpoints.sqlite3"
    )
    for candidate in (checkpoint, runtime_checkpoint):
        SqliteCheckpointStore(candidate).initialize()


def _capture_active_recovery_files(root: Path) -> dict[str, bytes]:
    files = ("active-generation.json", "active-generation-proof.json")
    return {
        name: (root / name).read_bytes() if (root / name).exists() else b""
        for name in files
    }


def test_restore_validation_forbids_extractall_and_stages_declared_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T078 must validate manifest-first and stream, never delegate extraction."""

    archive = _archive_for_restore(tmp_path)
    manager = RestoreManager(tmp_path / "profile")

    def forbidden_extractall(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("restore.validate must not call ZipFile.extractall")

    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbidden_extractall)
    reservation = manager.validate_archive(archive)

    assert (reservation.staging_dir / "profile" / "profile.json").is_file()
    assert (reservation.staging_dir / "sessions" / "checkpoints.sqlite3").is_file()


@pytest.mark.parametrize(
    "profile_bytes",
    [
        b"{}",
        b"{",
        _canonical_bytes(
            {
                "preferences": {},
                "principal_id": "foreign-principal",
                "profile_id": "portable-profile",
                "projects": [],
                "schema_version": 1,
                "workspace_references": [],
            }
        ),
        _canonical_bytes(
            {
                "preferences": {},
                "principal_id": "portable-principal",
                "profile_id": "portable-profile",
                "projects": [
                    {
                        "id": "project-one",
                        "label": "Project",
                        "session_ids": ["unknown-session"],
                        "workspace_id": None,
                    }
                ],
                "schema_version": 1,
                "workspace_references": [],
            }
        ),
    ],
    ids=("missing-identity", "malformed-json", "principal-mismatch", "unknown-session"),
)
def test_restore_validation_rejects_semantically_inconsistent_profile(
    tmp_path: Path,
    profile_bytes: bytes,
) -> None:
    """A hash-valid archive cannot disagree on profile identity or inventory."""

    archive = _rewrite_archive_profile(_archive_for_restore(tmp_path), profile_bytes)
    manager = RestoreManager(tmp_path / "profile")

    with pytest.raises(ValueError, match="profile"):
        manager.validate_archive(archive)

    assert manager.has_active_reservation() is False


@pytest.mark.parametrize(
    "projects",
    [
        [
            {
                "id": "project-one",
                "label": "One",
                "session_ids": ["session-one", "session-one"],
                "workspace_id": None,
            }
        ],
        [
            {
                "id": "project-one",
                "label": "One",
                "session_ids": ["session-one"],
                "workspace_id": None,
            },
            {
                "id": "project-two",
                "label": "Two",
                "session_ids": ["session-one"],
                "workspace_id": None,
            },
        ],
    ],
    ids=("duplicate-within-project", "duplicate-across-projects"),
)
async def test_restore_validation_rejects_duplicate_project_session_membership(
    tmp_path: Path,
    projects: list[dict[str, Any]],
) -> None:
    """Each restored session has one ordered-unique Project membership."""

    snapshot = tmp_path / "snapshot-project-membership"
    checkpoint = snapshot / "sessions" / "checkpoints.sqlite3"
    checkpoint.parent.mkdir(parents=True)
    recorded_at = datetime(2026, 1, 1, tzinfo=UTC)
    record = SessionMetaRecord(
        session_id="session-one",
        sequence=1,
        recorded_at=recorded_at,
        payload={
            "created_at": recorded_at,
            "label": "Session",
            "principal_id": "portable-principal",
        },
    )
    SqliteCheckpointStore(checkpoint).initialize()
    connection = sqlite3.connect(checkpoint)
    try:
        connection.execute(
            "INSERT INTO records(session_id, sequence, recorded_at, data) "
            "VALUES (?, ?, ?, ?)",
            (
                record.session_id,
                record.sequence,
                record.recorded_at.isoformat(),
                serialize_record(record),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    archive = tmp_path / "duplicate-project-membership.zip"
    create_portable_archive(
        archive,
        profile_portable={
            "schema_version": 1,
            "profile_id": "portable-profile",
            "principal_id": "portable-principal",
            "projects": projects,
            "workspace_references": [],
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )
    state = ProfileState.open(tmp_path / "profile")
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        ProfileMutationLease(),
        restore_manager=RestoreManager(state.root),
    )

    with pytest.raises(RpcError) as caught:
        await methods.restore_validate(
            {"mutation_id": "restore-owner", "source_path": str(archive)}
        )

    assert caught.value.category == "unsafe_input"


async def test_restore_validation_maps_non_text_checkpoint_payload_to_unsafe_input(
    tmp_path: Path,
) -> None:
    """A hash-valid malformed SQLite record is untrusted input, not availability."""

    checkpoint = tmp_path / "malformed.sqlite3"
    SqliteCheckpointStore(checkpoint).initialize()
    connection = sqlite3.connect(checkpoint)
    try:
        connection.execute(
            "INSERT INTO records(session_id, sequence, recorded_at, data) "
            "VALUES (?, ?, ?, ?)",
            ("session", 1, datetime.now(UTC).isoformat(), 7),
        )
        connection.commit()
    finally:
        connection.close()
    archive = _rewrite_archive_member(
        _archive_for_restore(tmp_path),
        "sessions/checkpoints.sqlite3",
        checkpoint.read_bytes(),
    )
    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=RestoreManager(state.root),
    )

    with pytest.raises(RpcError) as caught:
        await methods.restore_validate(
            {"mutation_id": "restore-owner", "source_path": str(archive)}
        )

    assert caught.value.category == "unsafe_input"
    assert lease.held() is False


@pytest.mark.parametrize(
    "extra_sql",
    [
        "CREATE TABLE unexpected (value TEXT)",
        ("CREATE TRIGGER unexpected AFTER DELETE ON records BEGIN SELECT 1; END"),
    ],
    ids=["extra-table", "delete-trigger"],
)
async def test_restore_validation_rejects_extra_checkpoint_schema_objects(
    tmp_path: Path,
    extra_sql: str,
) -> None:
    """A restored checkpoint owns no extra data or executable schema objects."""

    checkpoint = tmp_path / "extra-schema.sqlite3"
    SqliteCheckpointStore(checkpoint).initialize()
    with sqlite3.connect(checkpoint) as connection:
        connection.execute(extra_sql)
    archive = _rewrite_archive_member(
        _archive_for_restore(tmp_path),
        "sessions/checkpoints.sqlite3",
        checkpoint.read_bytes(),
    )
    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=RestoreManager(state.root),
    )

    with pytest.raises(RpcError) as caught:
        await methods.restore_validate(
            {"mutation_id": "restore-owner", "source_path": str(archive)}
        )

    assert caught.value.category == "unsafe_input"
    assert lease.held() is False


@pytest.mark.parametrize(
    "member_name",
    ["profile/profile.json", "sessions/checkpoints.sqlite3"],
)
async def test_restore_validation_maps_missing_required_member_to_unsafe_input(
    tmp_path: Path,
    member_name: str,
) -> None:
    """A hash-valid archive still requires both profile and checkpoint members."""

    archive = _archive_without_member(_archive_for_restore(tmp_path), member_name)
    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=RestoreManager(state.root),
    )

    with pytest.raises(RpcError) as caught:
        await methods.restore_validate(
            {"mutation_id": "restore-owner", "source_path": str(archive)}
        )

    assert caught.value.category == "unsafe_input"
    assert lease.held() is False


@pytest.mark.parametrize(
    "case",
    [
        "manifest_missing",
        "manifest_not_first",
        "duplicate_member",
        "backslash_path",
        "casefold_collision",
        "non_regular_member",
        "unsupported_compression",
        "declared_hash_mismatch",
    ],
)
def test_restore_validation_rejects_untrusted_archive_shapes(
    tmp_path: Path,
    case: str,
) -> None:
    """Path/type/collision/hash policy is enforced before any staging publish."""

    archive = tmp_path / f"{case}.zip"
    entries: list[tuple[str, str, bytes]] = [("profile/profile.json", "profile", b"{}")]
    kwargs: dict[str, Any] = {}
    if case == "manifest_missing":
        with zipfile.ZipFile(archive, "w") as source:
            source.writestr("profile/profile.json", b"{}")
    else:
        if case == "manifest_not_first":
            kwargs["manifest_first"] = False
        elif case == "duplicate_member":
            kwargs["duplicate_member"] = True
        elif case == "backslash_path":
            entries = [(r"profile\\profile.json", "profile", b"{}")]
        elif case == "casefold_collision":
            entries = [
                ("artifacts/session/A.txt", "artifact", b"A"),
                ("artifacts/session/a.txt", "artifact", b"a"),
            ]
        elif case == "non_regular_member":
            kwargs["external_mode"] = stat.S_IFLNK
        elif case == "unsupported_compression":
            kwargs["compression"] = zipfile.ZIP_BZIP2
        elif case == "declared_hash_mismatch":
            kwargs["corrupt_digest"] = True
        _write_unvalidated_archive(archive, entries, **kwargs)

    with pytest.raises(ValueError):
        RestoreManager(tmp_path / "profile").validate_archive(archive)


def test_restore_validation_rejects_short_stream_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Declared size/hash must be checked against actual streamed bytes."""

    archive = _archive_for_restore(tmp_path)

    def short_read(_self: object, _size: int = -1) -> bytes:
        return b""

    monkeypatch.setattr(zipfile.ZipExtFile, "read", short_read)
    with pytest.raises(ValueError):
        RestoreManager(tmp_path / "profile").validate_archive(archive)


def test_restore_validation_uses_exclusive_no_follow_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-existing candidate name is never recursively removed or reused."""

    import restore as restore_module

    archive = _archive_for_restore(tmp_path)
    fixed_token = "fixed-token"
    occupied = tmp_path / "profile" / "staging" / "restore" / fixed_token
    occupied.mkdir(parents=True)
    marker = occupied / "must-not-delete"
    marker.write_text("sentinel", encoding="utf-8")

    class FixedToken:
        def __str__(self) -> str:
            return fixed_token

    monkeypatch.setattr(restore_module.uuid, "uuid4", FixedToken)

    with pytest.raises((FileExistsError, ValueError)):
        RestoreManager(tmp_path / "profile").validate_archive(archive)

    assert marker.read_text(encoding="utf-8") == "sentinel"


def test_restore_candidate_staging_is_same_volume_and_outside_active_generation(
    tmp_path: Path,
) -> None:
    """A valid reservation uses a same-volume, generation-external candidate root."""

    archive = _archive_for_restore(tmp_path)
    root = tmp_path / "profile"
    active = root / "generations" / "active"
    active.mkdir(parents=True)
    reservation = RestoreManager(root).validate_archive(archive)

    assert reservation.staging_dir.stat().st_dev == root.stat().st_dev
    assert not reservation.staging_dir.is_relative_to(active)


async def test_restore_reservation_blocks_every_competing_writer_before_dispatch(
    tmp_path: Path,
) -> None:
    """The restore-held all-writer lease owns the complete pre-dispatch matrix."""

    methods, manager, lease, owner_id, archive = _methods_with_pending_restore(tmp_path)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )
    assert manager.get(validated["restore_token"]) is not None
    assert lease.held_by("restore", owner_id)

    host = _NoDispatchHost()
    state = ProfileState.open(tmp_path / "profile")
    sessions = SessionMethods(host, lease)  # type: ignore[arg-type]
    interactions = InteractionMethods(
        host,  # type: ignore[arg-type]
        InteractionLease(),
        mutation_lease=lease,
    )
    projects = ProjectMethods(state, lease)
    workspaces = WorkspaceMethods(state, lease)
    capabilities = InspectionMethods(host, mutation_lease=lease)  # type: ignore[arg-type]
    before_profile = state.portable_path().read_bytes()
    calls = (
        (sessions.rename, {"mutation_id": "s-rename", "session_id": "s", "title": "n"}),
        (
            sessions.set_starred,
            {"mutation_id": "s-star", "session_id": "s", "starred": True},
        ),
        (
            sessions.fork,
            {"mutation_id": "s-fork", "session_id": "s", "confirmation": True},
        ),
        (
            sessions.delete,
            {"mutation_id": "s-delete", "session_id": "s", "confirmation": True},
        ),
        (interactions.create_interactive, {"mutation_id": "i-open"}),
        (
            interactions.submit,
            {"mutation_id": "i-submit", "subscription_id": "sub", "prompt": "p"},
        ),
        (
            interactions.answer_approval,
            {
                "mutation_id": "i-approval",
                "subscription_id": "sub",
                "request_id": "r",
                "allow": True,
            },
        ),
        (
            interactions.answer_question,
            {
                "mutation_id": "i-question",
                "subscription_id": "sub",
                "request_id": "r",
                "answers": ["a"],
            },
        ),
        (projects.create, {"mutation_id": "p-create", "label": "Project"}),
        (
            projects.rename,
            {"mutation_id": "p-rename", "project_id": "p", "label": "Project"},
        ),
        (projects.remove, {"mutation_id": "p-remove", "project_id": "p"}),
        (
            projects.assign_session,
            {"mutation_id": "p-assign", "project_id": "p", "session_id": "s"},
        ),
        (workspaces.bind, {"mutation_id": "w-bind", "path": str(tmp_path)}),
        (
            workspaces.relink,
            {"mutation_id": "w-relink", "workspace_id": "w", "path": str(tmp_path)},
        ),
        (workspaces.remove, {"mutation_id": "w-remove", "workspace_id": "w"}),
        (workspaces.revalidate, {"mutation_id": "w-revalidate", "workspace_id": "w"}),
        (
            capabilities.capabilities_invoke,
            {"mutation_id": "c", "capability_id": "memory", "action": "refresh"},
        ),
        (
            methods.create,
            {
                "mutation_id": "backup",
                "acknowledgement": True,
                "destination_path": str(tmp_path / "backup.zip"),
            },
        ),
        (
            methods.restore_validate,
            {"mutation_id": "restore-other", "source_path": str(archive)},
        ),
    )
    for call, params in calls:
        with pytest.raises(RpcError) as exc:
            await call(params)
        assert exc.value.category == "busy"

    assert host.called is False
    assert state.portable_path().read_bytes() == before_profile


@pytest.mark.parametrize("transition", ["commit", "cancel"])
async def test_restore_transition_accepts_its_own_rpc_mutation_identity(
    tmp_path: Path,
    transition: str,
) -> None:
    """The token owns the reservation while each transition owns a fresh RPC ID."""

    methods, manager, lease, owner_id, archive = _methods_with_pending_restore(tmp_path)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )
    token = validated["restore_token"]
    request = {"mutation_id": f"restore-{transition}", "restore_token": token}
    if transition == "commit":
        request["confirmation"] = True
        result = await methods.restore_commit(request)
        assert result["committed"] is True
    else:
        result = await methods.restore_cancel(request)
        assert result["cancelled"] is True

    assert manager.get(token) is None
    assert lease.held() is False


async def test_restore_token_expires_after_fifteen_minutes_without_active_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expiry deletes staging/releases the reservation but not pointer/proof lineage."""

    import restore as restore_module

    methods, manager, lease, owner_id, archive = _methods_with_pending_restore(tmp_path)
    root = tmp_path / "profile"
    pointer, proof = _recovery_bytes("previous", "receipt-before")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    before = _capture_active_recovery_files(root)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )
    reservation = manager.get(validated["restore_token"])
    assert reservation is not None
    monkeypatch.setattr(
        restore_module.time, "time", lambda: reservation.created_at + 901
    )

    with pytest.raises(RpcError):
        await methods.restore_commit(
            {
                "mutation_id": owner_id,
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    assert manager.get(validated["restore_token"]) is None
    assert reservation.staging_dir.exists() is False
    assert lease.held() is False
    assert _capture_active_recovery_files(root) == before


async def test_expired_restore_is_reaped_before_unrelated_project_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import restore as restore_module

    methods, manager, lease, owner_id, archive = _methods_with_pending_restore(tmp_path)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )
    token = validated["restore_token"]
    reservation = manager.get(token)
    assert reservation is not None
    monkeypatch.setattr(
        restore_module.time, "time", lambda: reservation.created_at + 901
    )

    project = await ProjectMethods(
        ProfileState.open(tmp_path / "profile"), lease
    ).create({"mutation_id": "project-after-expiry", "label": "Recovered writer"})

    assert project["project"]["label"] == "Recovered writer"
    assert manager.get(token) is None
    assert reservation.staging_dir.exists() is False
    assert lease.held() is False


async def test_restore_commit_revalidates_archive_content_not_only_selected_filename(
    tmp_path: Path,
) -> None:
    """TOCTOU replacement of the selected archive is rejected before publication."""

    methods, _manager, _lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    root = tmp_path / "profile"
    pointer, proof = _recovery_bytes("previous", "receipt-before")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    before = _capture_active_recovery_files(root)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )
    replacement = _archive_for_restore(tmp_path, "replacement.zip")
    os.replace(replacement, archive)

    with pytest.raises(RpcError):
        await methods.restore_commit(
            {
                "mutation_id": owner_id,
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    assert _capture_active_recovery_files(root) == before


def test_connection_shutdown_cleanup_removes_staging_without_new_work(
    tmp_path: Path,
) -> None:
    """Manager teardown only deletes its candidate and never touches active lineage."""

    root = tmp_path / "profile"
    root.mkdir()
    archive = _archive_for_restore(tmp_path)
    pointer, proof = _recovery_bytes("previous", "receipt-before")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    before = _capture_active_recovery_files(root)
    manager = RestoreManager(root)
    reservation = manager.validate_archive(archive)

    manager.release_all()

    assert reservation.staging_dir.exists() is False
    assert manager.has_active_reservation() is False
    assert _capture_active_recovery_files(root) == before


def test_sidecar_restart_quarantines_or_removes_stale_restore_staging(
    tmp_path: Path,
) -> None:
    """A process-local token cannot keep unreferenced staging alive after restart."""

    root = tmp_path / "profile"
    stale = root / "staging" / "restore" / "orphaned-token"
    stale.mkdir(parents=True)
    (stale / "untrusted-stage").write_text("stale", encoding="utf-8")

    RestoreManager(root)

    assert stale.exists() is False


@pytest.mark.parametrize(
    "boundary",
    [
        *_PLATFORM_DURABILITY_BOUNDARIES,
        "recovery.prepared_a_temp_write_flush_replace_reread",
        "recovery.prepared_b_temp_write_flush_replace_reread",
        "recovery.candidate_pointer_before_replace",
        "recovery.published_slot_copy_on_write",
        "recovery.candidate_host_readiness",
        "recovery.old_host_close",
        "recovery.runtime_owner_swap",
        "recovery.proof_before_replace",
    ],
)
async def test_restore_faults_before_authoritative_proof_restore_previous_pair(
    tmp_path: Path,
    boundary: str,
) -> None:
    """Each named injected boundary is reached and preserves exact prior authority."""

    archive = _archive_for_restore(tmp_path)
    state = ProfileState.open(tmp_path / "profile")
    _prepare_pristine_generation(state.root, "previous")
    injector = _FaultAtBoundary(boundary)
    fault_seam: RestoreFaultInjector = injector
    manager = RestoreManager(state.root)
    manager.fault_injector = fault_seam  # type: ignore[attr-defined]
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=manager,
    )
    pointer, proof = _recovery_bytes("previous", "receipt-before")
    (state.root / "active-generation.json").write_bytes(pointer)
    (state.root / "active-generation-proof.json").write_bytes(proof)
    bindings = state.root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_bytes(b'{"existing":"binding"}')
    before = _capture_active_recovery_files(state.root)
    before_generations = {item.name for item in (state.root / "generations").iterdir()}
    validated = await methods.restore_validate(
        {"mutation_id": "restore-owner", "source_path": str(archive)}
    )

    with pytest.raises(RpcError) as caught:
        await methods.restore_commit(
            {
                "mutation_id": "restore-commit",
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    rolled_back = boundary in {
        "recovery.published_slot_copy_on_write",
        "recovery.candidate_host_readiness",
        "recovery.old_host_close",
        "recovery.runtime_owner_swap",
        "recovery.proof_before_replace",
    }
    assert caught.value.to_jsonrpc() == {
        "code": -32012,
        "message": "Publication failed",
        "data": {
            "category": "publication_failed",
            "retryable": True,
            "messageKey": (
                "restore.error.rolled_back"
                if rolled_back
                else "restore.error.publication_failed_retryable"
            ),
            "recovery": "retry",
        },
    }
    assert boundary in injector.seen
    assert _capture_active_recovery_files(state.root) == before
    assert (state.root / "restore-journal-a.json").exists() is False
    assert (state.root / "restore-journal-b.json").exists() is False
    assert {
        item.name for item in (state.root / "generations").iterdir()
    } == before_generations
    assert bindings.read_bytes() == b'{"existing":"binding"}'


async def test_unsupported_windows_volume_uses_the_exact_durability_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import durability

    methods, _manager, lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    monkeypatch.setattr(durability.sys, "platform", "win32")
    monkeypatch.setattr(
        durability,
        "_windows_supported_local_volume",
        lambda _path: False,
    )
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )

    with pytest.raises(RpcError) as caught:
        await methods.restore_commit(
            {
                "mutation_id": "restore-commit",
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    assert caught.value.to_jsonrpc() == {
        "code": -32011,
        "message": "Durability unsupported",
        "data": {
            "category": "durability_unsupported",
            "retryable": False,
            "messageKey": "restore.error.durability_unsupported",
            "recovery": "contact_support",
        },
    }
    assert lease.held() is False


async def test_preproof_rollback_revalidates_previous_authority_before_cleanup(
    tmp_path: Path,
) -> None:
    """A previous generation damaged after journal prepare must remain fail-locked."""

    archive = _archive_for_restore(tmp_path)
    state = ProfileState.open(tmp_path / "profile")
    _prepare_pristine_generation(state.root, "previous")

    class CorruptPreviousAtReadiness:
        def hit(self, boundary: str) -> None:
            if boundary != "recovery.candidate_host_readiness":
                return
            checkpoint = (
                state.root / "generation-storage" / "previous" / "checkpoints.sqlite3"
            )
            checkpoint.write_bytes(b"corrupt-after-journal-prepare")
            raise OSError("candidate readiness failed")

    manager = RestoreManager(state.root)
    manager.fault_injector = CorruptPreviousAtReadiness()  # type: ignore[attr-defined]
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=manager,
    )
    pointer, proof = _recovery_bytes("previous", "before")
    (state.root / "active-generation.json").write_bytes(pointer)
    (state.root / "active-generation-proof.json").write_bytes(proof)
    validated = await methods.restore_validate(
        {"mutation_id": "restore-owner", "source_path": str(archive)}
    )

    with pytest.raises(RpcError) as error:
        await methods.restore_commit(
            {
                "mutation_id": "restore-owner",
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    assert error.value.to_jsonrpc() == {
        "code": -32012,
        "message": "Publication failed",
        "data": {
            "category": "publication_failed",
            "retryable": False,
            "messageKey": "restore.error.publication_failed_restart",
            "recovery": "restart_runtime",
        },
    }
    assert (state.root / "restore-journal-a.json").is_file()
    assert (state.root / "restore-journal-b.json").is_file()
    assert lease.held_by("restore", "restore-owner")


@pytest.mark.parametrize(
    "boundary",
    [
        "recovery.verified_slot_copy_on_write",
        "recovery.cleanup_between_journal_unlinks",
    ],
)
async def test_faults_after_authoritative_proof_never_roll_back_candidate(
    tmp_path: Path,
    boundary: str,
) -> None:
    """A matching candidate proof remains authority through resumable cleanup faults."""

    archive = _archive_for_restore(tmp_path)
    state = ProfileState.open(tmp_path / "profile")
    _prepare_pristine_generation(state.root, "previous")
    injector = _FaultAtBoundary(boundary)
    fault_seam: RestoreFaultInjector = injector
    manager = RestoreManager(state.root)
    manager.fault_injector = fault_seam  # type: ignore[attr-defined]
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=manager,
    )
    pointer, proof = _recovery_bytes("previous", "receipt-before")
    (state.root / "active-generation.json").write_bytes(pointer)
    (state.root / "active-generation-proof.json").write_bytes(proof)
    validated = await methods.restore_validate(
        {"mutation_id": "restore-owner", "source_path": str(archive)}
    )

    try:
        await methods.restore_commit(
            {
                "mutation_id": "restore-owner",
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )
    except RpcError:
        pass

    assert boundary in injector.seen
    active_pointer = json.loads(
        (state.root / "active-generation.json").read_text("utf-8")
    )
    active_proof = json.loads(
        (state.root / "active-generation-proof.json").read_text("utf-8")
    )
    assert active_pointer["generation_id"] != "previous"
    assert active_proof["active_generation"] == active_pointer["generation_id"]
    assert state.generation_id == active_pointer["generation_id"]
    assert state.profile_id == "portable-profile"
    assert state.principal_id == "portable-principal"
    assert lease.held() is False


async def test_proof_reread_failure_never_reports_success_or_cleans_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A returned replace is not success until the proof rereads as authority."""

    import durability

    methods, _manager, lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    root = tmp_path / "profile"
    _prepare_pristine_generation(root, "previous")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    (root / "active-generation.json").write_bytes(previous_pointer)
    (root / "active-generation-proof.json").write_bytes(previous_proof)
    original_replace = durability._durable_replace

    def corrupt_proof_after_replace(path: Path, payload: bytes) -> None:
        original_replace(path, payload)
        if path.name == "active-generation-proof.json":
            path.write_bytes(b"corrupt-after-return")

    monkeypatch.setattr(durability, "_durable_replace", corrupt_proof_after_replace)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )

    with pytest.raises(RpcError) as error:
        await methods.restore_commit(
            {
                "mutation_id": owner_id,
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    assert error.value.to_jsonrpc() == {
        "code": -32012,
        "message": "Publication failed",
        "data": {
            "category": "publication_failed",
            "retryable": False,
            "messageKey": "restore.error.publication_failed_restart",
            "recovery": "restart_runtime",
        },
    }
    assert (
        root / "active-generation-proof.json"
    ).read_bytes() == b"corrupt-after-return"
    assert (root / "restore-journal-a.json").is_file()
    assert (root / "restore-journal-b.json").is_file()
    assert lease.held_by("restore", owner_id)


async def test_proof_effect_before_acknowledgement_freezes_recovery_for_startup(
    tmp_path: Path,
) -> None:
    """Possible proof effect preserves recovery data for startup-only adjudication."""

    archive = _archive_for_restore(tmp_path)
    state = ProfileState.open(tmp_path / "profile")
    _prepare_pristine_generation(state.root, "previous")
    injector = _FaultAtBoundary(
        "recovery.proof_effect_before_acknowledgement",
        root=state.root,
    )
    fault_seam: RestoreFaultInjector = injector
    manager = RestoreManager(state.root)
    manager.fault_injector = fault_seam  # type: ignore[attr-defined]
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        lease,
        restore_manager=manager,
    )
    bindings = state.root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"same-workspace":{"canonical_path":"old"}}', encoding="utf-8")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    (state.root / "active-generation.json").write_bytes(previous_pointer)
    (state.root / "active-generation-proof.json").write_bytes(previous_proof)
    validated = await methods.restore_validate(
        {"mutation_id": "restore-owner", "source_path": str(archive)}
    )

    with pytest.raises(RpcError) as initial:
        await methods.restore_commit(
            {
                "mutation_id": "restore-commit",
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )

    expected_restart = {
        "code": -32012,
        "message": "Publication failed",
        "data": {
            "category": "publication_failed",
            "retryable": False,
            "messageKey": "restore.error.publication_failed_restart",
            "recovery": "restart_runtime",
        },
    }
    assert initial.value.to_jsonrpc() == expected_restart
    assert "recovery.proof_effect_before_acknowledgement" in injector.seen
    assert injector.effect_snapshot is not None
    assert injector.snapshot() == injector.effect_snapshot
    assert (state.root / "restore-journal-a.json").is_file()
    assert (state.root / "restore-journal-b.json").is_file()
    assert bindings.is_file()
    assert lease.held() is True

    frozen = injector.snapshot()
    with pytest.raises(RpcError) as retried:
        await methods.restore_commit(
            {
                "mutation_id": "restore-retry",
                "restore_token": validated["restore_token"],
                "confirmation": True,
            }
        )
    assert retried.value.to_jsonrpc() == expected_restart
    assert injector.snapshot() == frozen

    with pytest.raises(RpcError) as cancelled:
        await methods.restore_cancel(
            {
                "mutation_id": "restore-cancel",
                "restore_token": validated["restore_token"],
            }
        )
    assert cancelled.value.to_jsonrpc() == expected_restart
    assert injector.snapshot() == frozen

    methods.shutdown()
    assert injector.snapshot() == frozen
    assert lease.held() is True


async def test_verified_cleanup_refuses_device_private_alias_without_external_delete(
    tmp_path: Path,
) -> None:
    """Post-proof cleanup never traverses a replaced device-private directory."""

    methods, manager, _lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    root = tmp_path / "profile"
    _prepare_pristine_generation(root, "previous")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    (root / "active-generation.json").write_bytes(previous_pointer)
    (root / "active-generation-proof.json").write_bytes(previous_proof)
    bindings = root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"stale":{"canonical_path":"old"}}', encoding="utf-8")
    external = tmp_path / "external-device-private"
    external.mkdir()
    sentinel = external / "workspace-bindings.json"
    sentinel.write_text("external-sentinel", encoding="utf-8")
    injector = _ReplaceBindingsParentWithAlias(root, external)
    manager.fault_injector = injector  # type: ignore[attr-defined]
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )

    try:
        with pytest.raises(RpcError) as caught:
            await methods.restore_commit(
                {
                    "mutation_id": owner_id,
                    "restore_token": validated["restore_token"],
                    "confirmation": True,
                }
            )
        assert caught.value.to_jsonrpc() == {
            "code": -32012,
            "message": "Publication failed",
            "data": {
                "category": "publication_failed",
                "retryable": False,
                "messageKey": "restore.error.publication_failed_restart",
                "recovery": "restart_runtime",
            },
        }
        assert sentinel.read_text(encoding="utf-8") == "external-sentinel"
    finally:
        if injector.replaced and os.path.lexists(injector.link):
            _remove_directory_alias(injector.link)
        if injector.retained.exists():
            injector.retained.rename(injector.link)
        methods.shutdown()


async def test_verified_cleanup_fail_locks_when_binding_alias_reappears(
    tmp_path: Path,
) -> None:
    """Post-proof cleanup cannot succeed while the exact stale name exists."""

    methods, manager, _lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    root = tmp_path / "profile"
    _prepare_pristine_generation(root, "previous")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    (root / "active-generation.json").write_bytes(previous_pointer)
    (root / "active-generation-proof.json").write_bytes(previous_proof)
    bindings = root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"stale":{"canonical_path":"old"}}', encoding="utf-8")
    external = tmp_path / "external-workspace-bindings.json"
    external.write_text("external-sentinel", encoding="utf-8")
    injector = _CreateBindingsAliasAfterUnlink(root, external)
    manager.fault_injector = injector  # type: ignore[attr-defined]
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )

    try:
        with pytest.raises(RpcError) as caught:
            await methods.restore_commit(
                {
                    "mutation_id": owner_id,
                    "restore_token": validated["restore_token"],
                    "confirmation": True,
                }
            )
        assert caught.value.to_jsonrpc() == {
            "code": -32012,
            "message": "Publication failed",
            "data": {
                "category": "publication_failed",
                "retryable": False,
                "messageKey": "restore.error.publication_failed_restart",
                "recovery": "restart_runtime",
            },
        }
        assert external.read_text(encoding="utf-8") == "external-sentinel"
        assert os.path.samefile(bindings, external)
    finally:
        if os.path.lexists(bindings):
            bindings.unlink()
        methods.shutdown()


async def test_restore_commit_writes_dual_preimages_and_verified_cleanup(
    tmp_path: Path,
) -> None:
    """T078 success owns prepared/published/verified COW records and receipt lineage."""

    methods, _manager, _lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    root = tmp_path / "profile"
    _prepare_pristine_generation(root, "previous")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    (root / "active-generation.json").write_bytes(previous_pointer)
    (root / "active-generation-proof.json").write_bytes(previous_proof)
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )

    result = await methods.restore_commit(
        {
            "mutation_id": owner_id,
            "restore_token": validated["restore_token"],
            "confirmation": True,
        }
    )

    assert result["committed"] is True
    proof = json.loads((root / "active-generation-proof.json").read_text("utf-8"))
    assert proof["active_generation"] != "previous"
    assert proof["generation_receipt_sha256"]
    assert (root / "restore-journal-a.json").exists() is False
    assert (root / "restore-journal-b.json").exists() is False


@pytest.mark.parametrize(
    "authority_name",
    ["active-generation.json", "active-generation-proof.json"],
)
def test_startup_rejects_reparse_marked_active_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_name: str,
) -> None:
    """Pointer/proof recovery authority must be an exact owned regular file."""

    import durability
    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    pointer, proof = _recovery_bytes("previous", "before")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    target = root / authority_name
    real_lstat = os.lstat

    def reparse_authority(
        path: os.PathLike[str] | str,
    ) -> os.stat_result | SimpleNamespace:
        info = real_lstat(path)
        if Path(path) != target:
            return info
        return SimpleNamespace(
            st_mode=info.st_mode,
            st_dev=info.st_dev,
            st_ino=info.st_ino,
            st_size=info.st_size,
            st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        )

    monkeypatch.setattr(durability.os, "lstat", reparse_authority)
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()


@pytest.mark.parametrize(
    ("authority_name", "slot", "sequence"),
    [
        ("restore-journal-a.json", "a", 1),
        ("restore-journal-b.json", "b", 2),
    ],
)
def test_startup_rejects_reparse_marked_restore_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_name: str,
    slot: str,
    sequence: int,
) -> None:
    """A linked/reparse journal cannot authorize startup rollback."""

    import durability
    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    old_pointer, old_proof = _recovery_bytes("previous", "before")
    candidate_pointer, _candidate_proof = _recovery_bytes("candidate", "after")
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"corrupt-proof")
    target = root / authority_name
    target.write_bytes(
        _journal_record(
            slot=slot,
            state="prepared" if slot == "a" else "published",
            sequence=sequence,
            previous_pointer=old_pointer,
            previous_proof=old_proof,
            candidate_pointer=candidate_pointer,
        )
    )
    real_lstat = os.lstat

    def reparse_authority(
        path: os.PathLike[str] | str,
    ) -> os.stat_result | SimpleNamespace:
        info = real_lstat(path)
        if Path(path) != target:
            return info
        return SimpleNamespace(
            st_mode=info.st_mode,
            st_dev=info.st_dev,
            st_ino=info.st_ino,
            st_size=info.st_size,
            st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        )

    monkeypatch.setattr(durability.os, "lstat", reparse_authority)
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()


@pytest.mark.parametrize(
    "authority_name",
    [
        "active-generation.json",
        "active-generation-proof.json",
        "restore-journal-a.json",
        "restore-journal-b.json",
    ],
)
def test_startup_rejects_oversized_recovery_record_before_unbounded_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_name: str,
) -> None:
    """Every recovery record is size-bounded before any high-level file read."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    target = root / authority_name
    target.write_bytes(b"x" * (8 * 1024 * 1024 + 1))
    original_read_bytes = Path.read_bytes

    def reject_unbounded_read(path: Path) -> bytes:
        if path == target:
            raise AssertionError("recovery record used unbounded Path.read_bytes")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_unbounded_read)
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()


def test_recovery_with_one_torn_slot_rolls_back_exact_previous_pointer_and_proof(
    tmp_path: Path,
) -> None:
    """One complete valid COW preimage is sufficient; corrupted sibling is ignored."""

    from runtime import DesktopRuntimeOwner

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    old_pointer, old_proof = _recovery_bytes("previous", "before")
    candidate_pointer, _candidate_proof = _recovery_bytes("candidate", "after")
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"corrupt-proof")
    (root / "restore-journal-a.json").write_bytes(b"torn")
    (root / "restore-journal-b.json").write_bytes(
        _journal_record(
            slot="b",
            state="published",
            sequence=2,
            previous_pointer=old_pointer,
            previous_proof=old_proof,
            candidate_pointer=candidate_pointer,
        )
    )
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        outcome = owner.bootstrap_generation()
    finally:
        owner.release()

    assert outcome["generation_id"] == "previous"
    assert (root / "active-generation.json").read_bytes() == old_pointer
    assert (root / "active-generation-proof.json").read_bytes() == old_proof


def test_startup_rollback_cleans_exact_candidate_before_second_restart(
    tmp_path: Path,
) -> None:
    """A pristine rollback cannot leave candidate bytes as false recovery authority."""

    from runtime import DesktopRuntimeOwner

    root = tmp_path / "profile"
    root.mkdir()
    candidate_generation = "restore-" + "a" * 32
    _prepare_pristine_generation(root, candidate_generation)
    candidate_pointer, _candidate_proof = _recovery_bytes(candidate_generation, "after")
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"")
    (root / "restore-journal-a.json").write_bytes(
        _journal_record(
            slot="a",
            state="prepared",
            sequence=1,
            previous_pointer=b"",
            previous_proof=b"",
            candidate_pointer=candidate_pointer,
            candidate_generation=candidate_generation,
            previous_generation="g0",
        )
    )

    first = DesktopRuntimeOwner(root)
    first.acquire()
    try:
        assert first.bootstrap_generation()["generation_id"] == "g0"
    finally:
        first.release()

    second = DesktopRuntimeOwner(root)
    second.acquire()
    try:
        assert second.bootstrap_generation()["generation_id"] == "g0"
    finally:
        second.release()

    assert not (root / "generations" / candidate_generation).exists()
    assert not (root / "generation-storage" / candidate_generation).exists()


def test_startup_recovery_rejects_case_alias_generation_before_cleanup(
    tmp_path: Path,
) -> None:
    """A lexical candidate alias cannot authorize deleting prior generation bytes."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    previous = root / "generations" / "g0"
    previous.mkdir(parents=True)
    sentinel = previous / "previous-authority"
    sentinel.write_bytes(b"keep")
    candidate_generation = "G0"
    candidate_pointer, _candidate_proof = _recovery_bytes(candidate_generation, "after")
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"")
    journal = _journal_record(
        slot="a",
        state="prepared",
        sequence=1,
        previous_pointer=b"",
        previous_proof=b"",
        candidate_pointer=candidate_pointer,
        candidate_generation=candidate_generation,
        previous_generation="g0",
    )
    (root / "restore-journal-a.json").write_bytes(journal)

    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert sentinel.read_bytes() == b"keep"
    assert (root / "active-generation.json").read_bytes() == candidate_pointer
    assert (root / "restore-journal-a.json").read_bytes() == journal


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction staging boundary")
def test_restore_validation_refuses_staging_junction_without_external_write(
    tmp_path: Path,
) -> None:
    """A staged member parent cannot be replaced with a directory junction."""

    root = tmp_path / "profile"
    archive = _archive_for_restore(tmp_path)
    external = tmp_path / "external-staging"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    injector = _ReplaceStagingParentWithAlias(root, external)
    manager = RestoreManager(root, fault_injector=injector)

    try:
        with pytest.raises((OSError, ValueError)):
            manager.validate_archive(archive)
        assert injector.link is not None
        assert sentinel.read_text(encoding="utf-8") == "keep"
        assert [entry.name for entry in external.iterdir()] == ["keep.txt"]
    finally:
        if injector.link is not None and os.path.lexists(injector.link):
            _remove_directory_alias(injector.link)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction cleanup boundary")
def test_restore_cancel_refuses_junction_without_external_delete(
    tmp_path: Path,
) -> None:
    """Cancellation revokes the token but never traverses a staged junction."""

    root = tmp_path / "profile"
    archive = _archive_for_restore(tmp_path)
    manager = RestoreManager(root)
    reservation = manager.validate_archive(archive)
    profile = reservation.staging_dir / "profile"
    retained = reservation.staging_dir / "profile-retained"
    profile.rename(retained)
    external = tmp_path / "external-cancel"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    _create_directory_alias(profile, external)

    try:
        assert manager.cancel(reservation.token) is True
        assert manager.get(reservation.token) is None
        assert sentinel.read_text(encoding="utf-8") == "keep"
        assert os.path.lexists(profile)
    finally:
        if os.path.lexists(profile):
            _remove_directory_alias(profile)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction cleanup boundary")
def test_restore_orphan_cleanup_refuses_junction_without_external_delete(
    tmp_path: Path,
) -> None:
    """Startup orphan cleanup fails closed instead of traversing a junction."""

    root = tmp_path / "profile"
    orphan = root / "staging" / "restore" / "orphan"
    orphan.mkdir(parents=True)
    external = tmp_path / "external-orphan"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    link = orphan / "artifacts"
    _create_directory_alias(link, external)

    try:
        with pytest.raises(OSError, match="reparse"):
            RestoreManager(root)
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        if os.path.lexists(link):
            _remove_directory_alias(link)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction cleanup boundary")
def test_startup_rollback_refuses_candidate_junction_without_external_delete(
    tmp_path: Path,
) -> None:
    """Startup recovery never descends through a candidate directory junction."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    candidate_generation = "restore-" + "b" * 32
    candidate_pointer, _candidate_proof = _recovery_bytes(candidate_generation, "after")
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"")
    journal = _journal_record(
        slot="a",
        state="prepared",
        sequence=1,
        previous_pointer=b"",
        previous_proof=b"",
        candidate_pointer=candidate_pointer,
        candidate_generation=candidate_generation,
        previous_generation="g0",
    )
    (root / "restore-journal-a.json").write_bytes(journal)

    external = tmp_path / "external-candidate"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    candidate = root / "generations" / candidate_generation
    candidate.parent.mkdir()
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(candidate), str(external)],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("Windows junction creation is unavailable")

    try:
        owner = DesktopRuntimeOwner(root)
        owner.acquire()
        try:
            with pytest.raises(RestoreJournalsPresent):
                owner.bootstrap_generation()
        finally:
            owner.release()

        assert sentinel.read_text(encoding="utf-8") == "keep"
        assert (root / "restore-journal-a.json").read_bytes() == journal
    finally:
        if os.path.lexists(candidate):
            os.rmdir(candidate)


@pytest.mark.parametrize(
    "damage",
    [
        "unexpected_key",
        "journal_version",
        "slot_filename",
        "state_sequence",
        "empty_restore_id",
        "previous_generation",
        "receipt_extra",
        "receipt_version",
        "receipt_state",
        "candidate_pointer_receipt",
    ],
)
def test_single_checksum_valid_incompatible_journal_fails_locked(
    tmp_path: Path, damage: str
) -> None:
    """One slot grants rollback authority only under the exact journal contract."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    candidate_pointer, _candidate_proof = _recovery_bytes("candidate", "after")
    record = json.loads(
        _journal_record(
            slot="a",
            state="prepared",
            sequence=1,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=candidate_pointer,
        )
    )

    if damage == "unexpected_key":
        record["unexpected"] = "field"
    elif damage == "journal_version":
        record["journal_version"] = 2
    elif damage == "slot_filename":
        record["slot"] = "b"
    elif damage == "state_sequence":
        record["journal_sequence"] = 2
    elif damage == "empty_restore_id":
        record["restore_id"] = ""
    elif damage == "previous_generation":
        record["previous_generation"] = "other"
    elif damage in {"receipt_extra", "receipt_version", "receipt_state"}:
        receipt = record["candidate_generation_publication_receipt"]
        if damage == "receipt_extra":
            receipt["unexpected"] = "field"
        elif damage == "receipt_version":
            receipt["receipt_version"] = 2
        else:
            receipt["checkpoint_state"] = "unknown"
        receipt_digest = hashlib.sha256(_canonical_bytes(receipt)).hexdigest()
        record["candidate_generation_receipt_sha256"] = receipt_digest
        candidate_pointer = _canonical_bytes(
            {"generation_id": "candidate", "receipt_sha256": receipt_digest}
        )
        record["candidate_pointer_bytes_b64"] = base64.b64encode(
            candidate_pointer
        ).decode("ascii")
        record["candidate_pointer_sha256"] = hashlib.sha256(
            candidate_pointer
        ).hexdigest()
    else:
        candidate_pointer = _canonical_bytes(
            {"generation_id": "candidate", "receipt_sha256": "0" * 64}
        )
        record["candidate_pointer_bytes_b64"] = base64.b64encode(
            candidate_pointer
        ).decode("ascii")
        record["candidate_pointer_sha256"] = hashlib.sha256(
            candidate_pointer
        ).hexdigest()

    record.pop("record_sha256")
    record["record_sha256"] = hashlib.sha256(_canonical_bytes(record)).hexdigest()
    journal = _canonical_bytes(record)
    active_before = candidate_pointer
    (root / "active-generation.json").write_bytes(active_before)
    (root / "active-generation-proof.json").write_bytes(b"corrupt-proof")
    (root / "restore-journal-a.json").write_bytes(journal)

    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert (root / "active-generation.json").read_bytes() == active_before
    assert (root / "restore-journal-a.json").read_bytes() == journal


def test_journal_rejects_pointer_only_previous_proof(
    tmp_path: Path,
) -> None:
    """Rollback authority requires the previous proof's complete durable contract."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, _previous_proof = _recovery_bytes("previous", "before")
    candidate_pointer, _candidate_proof = _recovery_bytes("candidate", "after")
    forged_previous_proof = _canonical_bytes(
        {
            "active_generation": "previous",
            "active_pointer_bytes_b64": base64.b64encode(previous_pointer).decode(
                "ascii"
            ),
            "active_pointer_sha256": hashlib.sha256(previous_pointer).hexdigest(),
        }
    )
    journal = _journal_record(
        slot="a",
        state="prepared",
        sequence=1,
        previous_pointer=previous_pointer,
        previous_proof=forged_previous_proof,
        candidate_pointer=candidate_pointer,
    )
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"corrupt-proof")
    (root / "restore-journal-a.json").write_bytes(journal)

    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert (root / "active-generation.json").read_bytes() == candidate_pointer
    assert (root / "restore-journal-a.json").read_bytes() == journal


def test_valid_preproof_slot_with_checksum_valid_incompatible_sibling_fails_locked(
    tmp_path: Path,
) -> None:
    """A checksum-valid conflicting sibling is not equivalent to one torn slot."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    candidate_pointer, _candidate_proof = _recovery_bytes("candidate", "after")
    valid = _journal_record(
        slot="a",
        state="prepared",
        sequence=1,
        previous_pointer=previous_pointer,
        previous_proof=previous_proof,
        candidate_pointer=candidate_pointer,
    )
    incompatible_value = json.loads(
        _journal_record(
            slot="b",
            state="published",
            sequence=2,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=candidate_pointer,
        )
    )
    incompatible_value["journal_version"] = 2
    incompatible_value.pop("record_sha256")
    incompatible_value["record_sha256"] = hashlib.sha256(
        _canonical_bytes(incompatible_value)
    ).hexdigest()
    incompatible = _canonical_bytes(incompatible_value)
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"corrupt-proof")
    (root / "restore-journal-a.json").write_bytes(valid)
    (root / "restore-journal-b.json").write_bytes(incompatible)

    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert (root / "active-generation.json").read_bytes() == candidate_pointer
    assert (root / "restore-journal-a.json").read_bytes() == valid
    assert (root / "restore-journal-b.json").read_bytes() == incompatible


def test_recovery_with_two_invalid_slots_fails_locked_without_host(
    tmp_path: Path,
) -> None:
    """No candidate is guessed when both independent preimages are unusable."""

    import runtime as runtime_module
    from runtime import DesktopRuntimeOwner

    root = tmp_path / "profile"
    root.mkdir()
    (root / "active-generation.json").write_bytes(b'{"generation_id":"candidate"}')
    (root / "active-generation-proof.json").write_bytes(b"mismatch")
    (root / "restore-journal-a.json").write_bytes(b"torn")
    (root / "restore-journal-b.json").write_bytes(b"corrupt")
    constructed = False

    def forbid_host(*_args: object, **_kwargs: object) -> object:
        nonlocal constructed
        constructed = True
        raise AssertionError("fail-locked recovery must not construct a Host")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runtime_module, "LoopPlaneHost", forbid_host)
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RuntimeError):
            owner.bootstrap_generation()
    finally:
        owner.release()
        monkeypatch.undo()

    assert constructed is False


def test_matching_proof_is_authoritative_when_journals_are_missing_or_older(
    tmp_path: Path,
) -> None:
    """A matching candidate proof beats a valid but older prepared journal."""

    from runtime import DesktopRuntimeOwner

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    pointer, proof = _recovery_bytes("candidate", "after")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    (root / "restore-journal-a.json").write_bytes(
        _journal_record(
            slot="a",
            state="prepared",
            sequence=1,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=pointer,
        )
    )
    bindings = root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"stale":{"canonical_path":"old"}}', encoding="utf-8")
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        outcome = owner.bootstrap_generation()
    finally:
        owner.release()

    assert outcome["generation_id"] == "candidate"
    assert (root / "restore-journal-a.json").exists() is False
    assert (root / "device-private" / "workspace-bindings.json").exists() is False


@pytest.mark.parametrize(
    "damage", ["checksum_valid_incompatible", "conflicting_lineage"]
)
def test_matching_proof_fails_locked_on_checksum_valid_conflicting_journal(
    tmp_path: Path, damage: str
) -> None:
    """Authoritative proof cannot erase checksum-valid conflicting evidence."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    pointer, proof = _recovery_bytes("candidate", "after")
    journal_pointer = pointer
    if damage == "conflicting_lineage":
        _prepare_pristine_generation(root, "other")
        journal_pointer, _other_proof = _recovery_bytes("other", "other")
    journal_value = json.loads(
        _journal_record(
            slot="a",
            state="prepared",
            sequence=1,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=journal_pointer,
        )
    )
    if damage == "checksum_valid_incompatible":
        journal_value["journal_version"] = 2
    else:
        other_receipt, other_receipt_digest = _receipt("other", "other")
        journal_value["candidate_generation"] = "other"
        journal_value["candidate_generation_publication_receipt"] = other_receipt
        journal_value["candidate_generation_receipt_sha256"] = other_receipt_digest
    journal_value.pop("record_sha256")
    journal_value["record_sha256"] = hashlib.sha256(
        _canonical_bytes(journal_value)
    ).hexdigest()
    journal = _canonical_bytes(journal_value)
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    (root / "restore-journal-a.json").write_bytes(journal)
    bindings = root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"stale":{"canonical_path":"old"}}', encoding="utf-8")

    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert (root / "active-generation.json").read_bytes() == pointer
    assert (root / "restore-journal-a.json").read_bytes() == journal
    assert bindings.is_file()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("proof_version", 999),
        ("proof_kind", "unsupported"),
        ("unexpected", "field"),
    ],
)
def test_matching_proof_rejects_checksum_valid_incompatible_schema(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    """Checksum validity cannot authorize an unknown proof contract."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "candidate")
    pointer, proof = _recovery_bytes("candidate", "after")
    proof_value = json.loads(proof)
    proof_value[field] = value
    proof_value.pop("record_sha256")
    proof_value["record_sha256"] = hashlib.sha256(
        _canonical_bytes(proof_value)
    ).hexdigest()
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(_canonical_bytes(proof_value))
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()


def test_bridge_startup_adjudicates_matching_proof_before_host_composition(
    tmp_path: Path,
) -> None:
    """The production bridge path delegates journal authority to the runtime owner."""

    from bridge import bootstrap_desktop_owner

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    pointer, proof = _recovery_bytes("candidate", "after")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    (root / "restore-journal-a.json").write_bytes(
        _journal_record(
            slot="a",
            state="prepared",
            sequence=1,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=pointer,
        )
    )
    bindings = root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"stale":{"canonical_path":"old"}}', encoding="utf-8")

    owner = bootstrap_desktop_owner(root)
    try:
        assert owner.generation_id == "candidate"
        assert (root / "restore-journal-a.json").exists() is False
        assert bindings.exists() is False
    finally:
        owner.release()


def test_two_consistent_preproof_slots_roll_back_without_fail_lock(
    tmp_path: Path,
) -> None:
    """Two independently complete prepared/published slots prove pre-proof rollback."""

    from runtime import DesktopRuntimeOwner

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "previous")
    _prepare_pristine_generation(root, "candidate")
    previous_pointer, previous_proof = _recovery_bytes("previous", "before")
    candidate_pointer, _candidate_proof = _recovery_bytes("candidate", "after")
    (root / "active-generation.json").write_bytes(candidate_pointer)
    (root / "active-generation-proof.json").write_bytes(b"")
    (root / "restore-journal-a.json").write_bytes(
        _journal_record(
            slot="a",
            state="prepared",
            sequence=1,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=candidate_pointer,
        )
    )
    (root / "restore-journal-b.json").write_bytes(
        _journal_record(
            slot="b",
            state="published",
            sequence=2,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_pointer=candidate_pointer,
        )
    )
    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        outcome = owner.bootstrap_generation()
    finally:
        owner.release()

    assert outcome["generation_id"] == "previous"
    assert (root / "active-generation.json").read_bytes() == previous_pointer
    assert (root / "active-generation-proof.json").read_bytes() == previous_proof


@pytest.mark.parametrize("damage", ["missing", "corrupt_sqlite"])
def test_matching_proof_requires_a_valid_candidate_inventory(
    tmp_path: Path, damage: str
) -> None:
    """A syntactically matching proof cannot authorize a missing/corrupt generation."""

    from runtime import DesktopRuntimeOwner, RestoreJournalsPresent

    root = tmp_path / "profile"
    root.mkdir()
    _prepare_pristine_generation(root, "candidate")
    pointer, proof = _recovery_bytes("candidate", "after")
    (root / "active-generation.json").write_bytes(pointer)
    (root / "active-generation-proof.json").write_bytes(proof)
    candidate = root / "generations" / "candidate"
    if damage == "missing":
        for child in sorted(candidate.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            else:
                child.rmdir()
        candidate.rmdir()
    else:
        (candidate / "sessions" / "checkpoints.sqlite3").write_bytes(b"not-sqlite")

    owner = DesktopRuntimeOwner(root)
    owner.acquire()
    try:
        with pytest.raises(RestoreJournalsPresent):
            owner.bootstrap_generation()
    finally:
        owner.release()


def test_generation_receipt_accepts_mutable_current_state() -> None:
    """Publication receipts bind lineage, not a permanent hash of later turn data."""

    from loopplane.host import GenerationExpectation, validate_active_generation

    result = validate_active_generation(
        {
            "checkpoint_state": "initialized",
            "artifact_state": "initialized",
            "schema_version": 1,
            "publication_receipt": "receipt-at-publication",
            "current_checkpoint_digest": "changed-after-normal-turn",
            "current_artifact_digest": "changed-after-normal-turn",
        },
        GenerationExpectation(
            checkpoint_state="initialized",
            artifact_state="initialized",
            schema_version=1,
        ),
    )

    assert result.ok is True


def test_relink_required_rejects_identical_stale_binding_before_lookup(
    tmp_path: Path,
) -> None:
    """Candidate readiness cannot authorize an old same-ID device binding."""

    from workspace import WorkspaceStore

    state = ProfileState.open(tmp_path / "profile")
    state.save_portable(
        {
            **state.load_portable(),
            "workspace_references": [
                {
                    "id": "same-workspace",
                    "label": "Work",
                    "availability": "relink_required",
                }
            ],
        }
    )
    bindings = state.root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    # An unreadable old binding makes an accidental lookup observable without
    # testing or naming a private lookup helper.
    bindings.write_text("not-json", encoding="utf-8")
    store = WorkspaceStore(state)

    with pytest.raises(LookupError, match="relink required"):
        store.resolve_path("same-workspace")


async def test_binding_cleanup_waits_for_authoritative_candidate_proof(
    tmp_path: Path,
) -> None:
    """T078 retains rollback bindings through proof, then cleans stale data."""

    methods, _manager, _lease, owner_id, archive = _methods_with_pending_restore(
        tmp_path
    )
    state_root = tmp_path / "profile"
    bindings = state_root / "device-private" / "workspace-bindings.json"
    bindings.parent.mkdir(parents=True, exist_ok=True)
    bindings.write_text('{"same-workspace":{"canonical_path":"old"}}', encoding="utf-8")
    validated = await methods.restore_validate(
        {"mutation_id": owner_id, "source_path": str(archive)}
    )

    result = await methods.restore_commit(
        {
            "mutation_id": owner_id,
            "restore_token": validated["restore_token"],
            "confirmation": True,
        }
    )

    assert result["committed"] is True
    assert bindings.exists() is False


async def test_restore_publication_calls_the_active_platform_durability_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A public restore commit executes the current OS adapter, not label-only hooks."""

    import durability

    archive = _archive_for_restore(tmp_path)
    state = ProfileState.open(tmp_path / "profile")
    manager = RestoreManager(state.root)
    methods = BackupMethods(
        _SnapshotValidator(),  # type: ignore[arg-type]
        state,
        ProfileMutationLease(),
        restore_manager=manager,
    )
    adapter_name = (
        "_publish_candidate_windows"
        if sys.platform == "win32"
        else "_publish_candidate_posix"
    )
    original_adapter = getattr(durability, adapter_name)
    observed: list[str] = []

    def observe_adapter(*args: object, **kwargs: object) -> object:
        observed.append(adapter_name)
        return original_adapter(*args, **kwargs)

    monkeypatch.setattr(durability, adapter_name, observe_adapter)
    if sys.platform == "win32":
        original_flush = durability._windows_flush_regular_file

        def observe_flush(path: Path) -> None:
            observed.append("flush")
            original_flush(path)

        monkeypatch.setattr(durability, "_windows_flush_regular_file", observe_flush)

    validated = await methods.restore_validate(
        {"mutation_id": "restore-owner", "source_path": str(archive)}
    )
    result = await methods.restore_commit(
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["restore_token"],
            "confirmation": True,
        }
    )

    assert result["committed"] is True
    assert observed[0] == adapter_name
    if sys.platform == "win32":
        assert "flush" in observed
