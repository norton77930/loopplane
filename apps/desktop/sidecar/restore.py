"""Safe restore staging reservation (078 T077/T078).

Validation creates an opaque, short-lived reservation over a manifest-validated,
streamed candidate tree.  It never extracts an archive wholesale and never mutates
the active generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from loopplane.host import DesktopPortableSnapshotProvider

try:
    from .archive import (
        ArchiveValidationError,
        _portable_profile,
        canonical_json,
        validate_archive,
    )
except ImportError:  # pragma: no cover - direct sidecar module imports
    from archive import (  # type: ignore[no-redef]  # noqa: I001
        ArchiveValidationError,
        _portable_profile,
        canonical_json,
        validate_archive,
    )

try:
    from .durability import is_link_or_reparse
except ImportError:  # pragma: no cover - direct sidecar module imports
    from durability import is_link_or_reparse  # type: ignore[no-redef]

_TOKEN_LIFETIME_SECONDS = 15 * 60
_STREAM_CHUNK_BYTES = 1024 * 1024
_MAX_PROFILE_BYTES = 8 * 1024 * 1024


class RestoreFaultInjector(Protocol):
    """Optional test-owned seam for one named restore transaction boundary."""

    def hit(self, boundary: str) -> None:
        """Observe, or raise at, a named transaction boundary."""
        ...


@dataclass
class RestoreReservation:
    token: str
    staging_dir: Path
    created_at: float
    archive_identity: str
    archive_path: Path
    host_snapshot_dir: Path
    manifest: dict[str, Any] = field(default_factory=dict)
    profile_portable: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    released: bool = False


class RestoreManager:
    def __init__(
        self,
        profile_root: Path,
        *,
        fault_injector: RestoreFaultInjector | None = None,
    ) -> None:
        self._root = Path(profile_root)
        self._reservations: dict[str, RestoreReservation] = {}
        self._staging_root = self._root / "staging" / "restore"
        self.fault_injector = fault_injector
        # Allocate the next opaque name before cleanup.  If that name is already
        # occupied, validate must reject it exclusively rather than deleting it.
        self._next_token = str(uuid.uuid4())
        self._remove_orphaned_staging(except_token=self._next_token)

    def has_active_reservation(self) -> bool:
        return any(not r.released for r in self._reservations.values())

    def validate_archive(self, archive_path: Path) -> RestoreReservation:
        """Manifest-validate and stream one archive into exclusive staging."""

        path = Path(archive_path)
        archive_identity = _archive_identity(path)
        try:
            manifest = validate_archive(path)
        except ArchiveValidationError as exc:
            raise ValueError("unsafe_or_invalid_archive") from exc
        if _archive_identity(path) != archive_identity:
            raise ValueError("archive_changed_during_validation")

        token = self._next_token
        staging = self._new_staging_directory(token)
        self._next_token = str(uuid.uuid4())
        try:
            self._stage_declared_members(path, manifest, staging)
            profile_portable = _validate_staged_profile(manifest, staging)
            host_validation = DesktopPortableSnapshotProvider(
                self._root
            ).validate_snapshot(staging)
            if not host_validation.ok:
                raise ValueError("profile_checkpoint_invalid")
            host_manifest = host_validation.manifest
            if not isinstance(host_manifest, dict):
                raise ValueError("profile_checkpoint_invalid")
            session_count = host_manifest.get("session_count")
            artifact_count = host_manifest.get("artifact_count")
            if type(session_count) is not int or type(artifact_count) is not int:
                raise ValueError("profile_checkpoint_invalid")
        except Exception:
            _remove_tree(staging)
            raise

        entries = manifest["entries"]
        reservation = RestoreReservation(
            token=token,
            staging_dir=staging,
            created_at=time.time(),
            archive_identity=archive_identity,
            archive_path=path,
            host_snapshot_dir=staging,
            manifest=manifest,
            profile_portable=profile_portable,
            summary={
                "entry_count": len(entries),
                "project_count": len(profile_portable["projects"]),
                "session_count": session_count,
                "artifact_count": artifact_count,
                "has_manifest": True,
                "has_profile": (staging / "profile" / "profile.json").is_file(),
                "format": manifest.get("format"),
                "version": manifest.get("version"),
                "created_at": manifest.get("created_at"),
                "drafts_excluded": True,
                "relink_required": True,
            },
        )
        self._reservations[token] = reservation
        return reservation

    def get(self, token: str) -> RestoreReservation | None:
        reservation = self._reservations.get(token)
        if reservation is None or reservation.released:
            return None
        return reservation

    def expired(self, reservation: RestoreReservation) -> bool:
        return time.time() - reservation.created_at >= _TOKEN_LIFETIME_SECONDS

    def revalidate_archive(self, reservation: RestoreReservation) -> bool:
        """Reject replacement or content drift before candidate publication."""

        if reservation.released:
            return False
        try:
            if (
                _archive_identity(reservation.archive_path)
                != reservation.archive_identity
            ):
                return False
            validate_archive(reservation.archive_path)
            return (
                _archive_identity(reservation.archive_path)
                == reservation.archive_identity
            )
        except (ArchiveValidationError, OSError, ValueError):
            return False

    def cancel(self, token: str) -> bool:
        reservation = self._reservations.pop(token, None)
        if reservation is None:
            return False
        # Logical authority is revoked before best-effort physical cleanup. A
        # sharing violation must not leave the token active or retain the writer
        # lease; startup orphan cleanup owns any staging bytes left behind.
        reservation.released = True
        try:
            _remove_tree(reservation.staging_dir)
        except OSError:
            pass
        return True

    def release_all(self) -> None:
        for token in list(self._reservations):
            self.cancel(token)

    def hit(self, boundary: str) -> None:
        """Expose the named test seam without importing test-only code."""

        if self.fault_injector is not None:
            self.fault_injector.hit(boundary)

    def _new_staging_directory(self, token: str) -> Path:
        staging_root = _restore_staging_root(self._root, create=True)
        candidate = staging_root / token
        # O_EXCL equivalent for directories: never clear or reuse an occupied name.
        os.mkdir(candidate, 0o700)
        _require_owned_directory(staging_root, token)
        return candidate

    def _stage_declared_members(
        self, archive_path: Path, manifest: dict[str, Any], staging: Path
    ) -> None:
        declared = manifest.get("entries")
        if not isinstance(declared, list):
            raise ValueError("invalid_manifest")
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                infos = {info.filename: info for info in archive.infolist()}
                for entry in declared:
                    if not isinstance(entry, dict):
                        raise ValueError("invalid_manifest")
                    path = entry.get("path")
                    if not isinstance(path, str):
                        raise ValueError("invalid_manifest")
                    info = infos.get(path)
                    if info is None:
                        raise ValueError("archive_declaration_mismatch")
                    target = _safe_staging_target(staging, path)
                    self.hit("restore.staging_target_ready")
                    _require_staging_target(staging, target)
                    _stream_member(archive, info, target, entry)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise ValueError("archive_stream_failed") from exc

    def _remove_orphaned_staging(self, *, except_token: str) -> None:
        staging_root = _restore_staging_root(self._root, create=False)
        if staging_root is None:
            return
        for child in staging_root.iterdir():
            if child.name != except_token:
                _remove_tree(child)


def _archive_identity(path: Path) -> str:
    """Hash the selected regular archive through a no-follow descriptor."""

    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("archive not found")
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if getattr(before, "st_file_attributes", 0) & reparse:
        raise ValueError("archive not found")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    size = 0
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            raise ValueError("archive_changed")
        while chunk := os.read(descriptor, _STREAM_CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    finally:
        os.close(descriptor)
    after = os.lstat(path)
    if (
        size != before.st_size
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
        or after.st_size != before.st_size
        or not stat.S_ISREG(after.st_mode)
    ):
        raise ValueError("archive_changed")
    return f"{before.st_dev}:{before.st_ino}:{before.st_size}:{digest.hexdigest()}"


def _exact_owned_child(parent: Path, name: str) -> Path | None:
    try:
        parent_info = os.lstat(parent)
    except OSError as exc:
        raise ValueError("unsafe_archive_path") from exc
    if not stat.S_ISDIR(parent_info.st_mode) or is_link_or_reparse(parent_info):
        raise ValueError("unsafe_archive_path")
    try:
        with os.scandir(parent) as entries:
            exact = any(entry.name == name for entry in entries)
    except OSError as exc:
        raise ValueError("unsafe_archive_path") from exc
    candidate = parent / name
    if exact:
        return candidate
    try:
        os.lstat(candidate)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("unsafe_archive_path") from exc
    raise ValueError("unsafe_archive_path")


def _require_owned_directory(parent: Path, name: str) -> Path:
    child = _exact_owned_child(parent, name)
    if child is None:
        raise ValueError("unsafe_archive_path")
    try:
        info = os.lstat(child)
    except OSError as exc:
        raise ValueError("unsafe_archive_path") from exc
    if not stat.S_ISDIR(info.st_mode) or is_link_or_reparse(info):
        raise ValueError("unsafe_archive_path")
    return child


def _owned_directory(parent: Path, name: str, *, create: bool) -> Path | None:
    child = _exact_owned_child(parent, name)
    if child is None and create:
        try:
            os.mkdir(parent / name, 0o700)
        except FileExistsError:
            pass
        child = _exact_owned_child(parent, name)
        if child is None:
            raise ValueError("unsafe_archive_path")
    if child is None:
        return None
    return _require_owned_directory(parent, name)


def _restore_staging_root(root: Path, *, create: bool) -> Path | None:
    root = Path(root)
    if not root.exists():
        if not create:
            return None
        root.mkdir(parents=True, exist_ok=True)
    try:
        root = root.resolve(strict=True)
        info = os.lstat(root)
    except OSError as exc:
        raise ValueError("unsafe_archive_path") from exc
    if not stat.S_ISDIR(info.st_mode) or is_link_or_reparse(info):
        raise ValueError("unsafe_archive_path")
    staging = _owned_directory(root, "staging", create=create)
    if staging is None:
        return None
    return _owned_directory(staging, "restore", create=create)


def _require_staging_target(staging: Path, target: Path) -> None:
    try:
        relative = target.relative_to(staging)
    except ValueError as exc:
        raise ValueError("unsafe_archive_path") from exc
    parent = staging
    for component in relative.parts[:-1]:
        parent = _require_owned_directory(parent, component)
    if _exact_owned_child(parent, relative.name) is not None:
        raise ValueError("unsafe_archive_path")


def _safe_staging_target(staging: Path, archive_name: str) -> Path:
    relative = Path(*archive_name.split("/"))
    target = staging.joinpath(relative)
    if not target.is_relative_to(staging):
        raise ValueError("unsafe_archive_path")
    parent = staging
    for component in relative.parts[:-1]:
        child = _owned_directory(parent, component, create=True)
        assert child is not None
        parent = child
    _require_staging_target(staging, target)
    return target


def _stream_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    target: Path,
    entry: dict[str, Any],
) -> None:
    expected_size = entry.get("size")
    expected_digest = entry.get("sha256")
    if not isinstance(expected_size, int) or not isinstance(expected_digest, str):
        raise ValueError("invalid_manifest")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    descriptor = os.open(target, flags, 0o600)
    digest = hashlib.sha256()
    size = 0
    try:
        with archive.open(info, "r") as member:
            while chunk := member.read(_STREAM_CHUNK_BYTES):
                size += len(chunk)
                if size > expected_size:
                    raise ValueError("archive_size_mismatch")
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
        if size != expected_size or digest.hexdigest() != expected_digest:
            raise ValueError("archive_integrity_failed")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_staged_profile(manifest: dict[str, Any], staging: Path) -> dict[str, Any]:
    """Bind canonical profile identity and Projects to checkpoint ownership."""

    normalized = _load_canonical_profile(staging / "profile" / "profile.json")
    if (
        normalized["profile_id"] != manifest.get("profile_id")
        or normalized["principal_id"] != manifest.get("principal_id")
        or normalized["schema_version"] != manifest.get("profile_schema_version")
    ):
        raise ValueError("profile_identity_mismatch")
    return normalized


def _load_canonical_profile(
    profile_path: Path, *, allow_active_workspace_state: bool = False
) -> dict[str, Any]:
    raw = _read_bounded_regular(profile_path, _MAX_PROFILE_BYTES)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("profile_invalid") from exc
    if not isinstance(value, dict) or canonical_json(value) != raw:
        raise ValueError("profile_invalid")
    validation_value = (
        _profile_with_portable_workspace_states(value)
        if allow_active_workspace_state
        else value
    )
    try:
        normalized = _portable_profile(validation_value)
    except ArchiveValidationError as exc:
        raise ValueError("profile_invalid") from exc
    if normalized != validation_value:
        raise ValueError("profile_invalid")
    return value


def _profile_with_portable_workspace_states(
    value: dict[str, Any],
) -> dict[str, Any]:
    references = value.get("workspace_references")
    if not isinstance(references, list):
        raise ValueError("profile_invalid")
    normalized_references: list[dict[str, Any]] = []
    for reference in references:
        if (
            not isinstance(reference, dict)
            or set(reference) != {"id", "label", "availability", "actions"}
            or reference.get("availability") not in {"available", "relink_required"}
            or reference.get("actions") != ["open", "relink", "remove"]
        ):
            raise ValueError("profile_invalid")
        normalized_references.append(
            {
                **reference,
                "availability": "relink_required",
            }
        )
    return {**value, "workspace_references": normalized_references}


def _read_bounded_regular(path: Path, limit: int) -> bytes:
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError("profile_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    chunks: list[bytes] = []
    size = 0
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            raise ValueError("profile_invalid")
        while chunk := os.read(descriptor, _STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > limit or size > before.st_size:
                raise ValueError("profile_invalid")
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    after = os.lstat(path)
    if (
        size != before.st_size
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
        or after.st_size != before.st_size
    ):
        raise ValueError("profile_invalid")
    return b"".join(chunks)


def _remove_tree(path: Path) -> None:
    """Remove only a sidecar-owned staging tree without following links."""

    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if is_link_or_reparse(info):
        raise OSError("refusing restore staging reparse-point cleanup")
    if not stat.S_ISDIR(info.st_mode):
        path.unlink(missing_ok=True)
        return
    for child in path.iterdir():
        _remove_tree(child)
    path.rmdir()
