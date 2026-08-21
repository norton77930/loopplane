"""Portable snapshot export/validation facades (078 T075).

The Desktop provider is Host-owned: it snapshots SQLite through its backup API and
only includes checkpoint-referenced ArtifactStore output.  The sidecar receives
neither live-store paths nor handles.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from loopplane.checkpoint import SqliteCheckpointStore
from loopplane.checkpoint.records import (
    ReplacementDecisionRecord,
    SessionMetaRecord,
    deserialize_record,
)
from loopplane.checkpoint.sqlite import validate_sqlite_checkpoint_schema

_STREAM_CHUNK_BYTES = 1024 * 1024
_MAX_ARTIFACT_METADATA_BYTES = 8 * 1024 * 1024


class PortableSnapshotUnavailable(RuntimeError):
    """Raised when no snapshot provider is injected (default Host posture)."""

    public_code = "unavailable"


@dataclass(frozen=True, slots=True)
class PortableSnapshotResult:
    ok: bool
    path: str | None = None
    entry_count: int = 0
    reason: str | None = None
    manifest: dict[str, Any] | None = None


class PortableSnapshotProvider(Protocol):
    """Desktop-injected provider — consistent SQLite + eligible artifacts."""

    def export_snapshot(self, destination: Path) -> PortableSnapshotResult:
        """Write a portable snapshot under destination (must be empty/writable)."""
        ...

    def validate_snapshot(self, source: Path) -> PortableSnapshotResult:
        """Read-only validation of an inactive staged snapshot."""
        ...


class UnavailablePortableSnapshotProvider:
    """Default provider: export/validate always unavailable."""

    def export_snapshot(self, destination: Path) -> PortableSnapshotResult:
        return PortableSnapshotResult(
            ok=False,
            reason="portable_snapshot_unavailable",
            path=None,
        )

    def validate_snapshot(self, source: Path) -> PortableSnapshotResult:
        return PortableSnapshotResult(
            ok=False,
            reason="portable_snapshot_unavailable",
            path=None,
        )


class DesktopPortableSnapshotProvider:
    """Host-owned SQLite/artifact snapshot provider for Desktop composition.

    The source root remains encapsulated in this provider.  It does not construct
    a checkpoint store or ArtifactStore: export uses SQLite's consistent backup
    API, and staged validation uses only a read-only SQLite URI plus no-follow
    regular-file checks.
    """

    def __init__(
        self,
        storage_root: Path,
        *,
        validate_root: Callable[[], None] | None = None,
    ) -> None:
        self._storage_root = Path(storage_root)
        self._validate_root = validate_root

    def export_snapshot(self, destination: Path) -> PortableSnapshotResult:
        destination = Path(destination)
        if not _empty_directory(destination):
            return _failed("snapshot_destination_invalid")
        try:
            if self._validate_root is not None:
                self._validate_root()
        except (OSError, RuntimeError, ValueError):
            return _failed("checkpoint_snapshot_unavailable")
        source_db = self._storage_root / "checkpoints.sqlite3"
        if not _retained_descriptor_root(self._storage_root) and not _regular_file(
            source_db
        ):
            return _failed("checkpoint_snapshot_unavailable")

        checkpoint_path = destination / "sessions" / "checkpoints.sqlite3"
        try:
            checkpoint_path.parent.mkdir()
            self._sqlite_backup(source_db, checkpoint_path)
            references = _checkpoint_references(checkpoint_path)
            if references is None:
                return _failed("checkpoint_snapshot_invalid")
            inventory = _copy_referenced_artifacts(
                self._storage_root,
                destination,
                references,
                retained_root=self._validate_root is not None,
            )
            if inventory is None:
                return _failed("artifact_provenance_unavailable")
            entries = [
                {
                    "path": "sessions/checkpoints.sqlite3",
                    "content_class": "checkpoint",
                    "size": checkpoint_path.stat().st_size,
                    "sha256": _sha256_file(checkpoint_path),
                },
                *inventory,
            ]
            return PortableSnapshotResult(
                ok=True,
                entry_count=len(entries),
                manifest={"entries": entries},
            )
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError):
            _clear_directory(destination)
            return _failed("snapshot_export_failed")

    def validate_snapshot(self, source: Path) -> PortableSnapshotResult:
        source = Path(source)
        try:
            entries = _validate_snapshot_tree(source)
            checkpoint_path = source / "sessions" / "checkpoints.sqlite3"
            session_count = _checkpoint_session_count(checkpoint_path)
            artifact_count = sum(
                entry.get("content_class") == "artifact" for entry in entries
            )
            profile_path = source / "profile" / "profile.json"
            if profile_path.exists():
                _validate_profile_against_checkpoint(
                    profile_path,
                    source / "sessions" / "checkpoints.sqlite3",
                    allow_active_workspace_state=False,
                )
            return PortableSnapshotResult(
                ok=True,
                entry_count=len(entries),
                manifest={
                    "entries": entries,
                    "session_count": session_count,
                    "artifact_count": artifact_count,
                },
            )
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError):
            return _failed("portable_snapshot_invalid")

    @staticmethod
    def _sqlite_backup(source: Path, destination: Path) -> None:
        """Use SQLite's backup API; never copy the live database bytes."""

        retained_root = source.parent
        if _retained_descriptor_root(retained_root):
            root_fd = _duplicate_retained_root(retained_root)
            source_fd: int | None = None
            try:
                source_fd, source_info = _open_regular_at(root_fd, source.name)
                source_uri = (
                    _descriptor_path(retained_root, source_fd).as_uri() + "?mode=ro"
                )
                _sqlite_backup_uri(source_uri, destination)
                _require_same_entry(root_fd, source.name, source_info)
            finally:
                if source_fd is not None:
                    os.close(source_fd)
                os.close(root_fd)
            return

        source_uri = source.resolve().as_uri() + "?mode=ro"
        _sqlite_backup_uri(source_uri, destination)


class DesktopRuntimeStorageInitializer:
    """Host-owned initialization and validation for Desktop serving storage."""

    def initialize(self, destination: Path) -> PortableSnapshotResult:
        destination = Path(destination)
        if not _empty_directory(destination):
            return _failed("runtime_storage_destination_invalid")
        try:
            SqliteCheckpointStore(destination / "checkpoints.sqlite3").initialize()
            if _validate_runtime_storage(destination) != (
                "initialized",
                "absent_uninitialized",
            ):
                raise ValueError("runtime_storage_invalid")
            return PortableSnapshotResult(ok=True)
        except (OSError, sqlite3.Error, ValueError):
            _clear_directory(destination)
            return _failed("runtime_storage_initialization_failed")

    def validate(self, source: Path) -> PortableSnapshotResult:
        try:
            _validate_runtime_storage(Path(source))
            return PortableSnapshotResult(ok=True)
        except (OSError, sqlite3.Error, ValueError):
            return _failed("runtime_storage_invalid")


class DesktopActiveGenerationProvider:
    """Read-only Desktop generation probe for ``validate_active_generation``.

    The provider owns SQLite/checkpoint/artifact interpretation. The sidecar passes
    only inactive generation/runtime roots through the public Host facade and never
    opens serving storage or deserializes checkpoint records itself.
    """

    def probe(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
        generation_value = source.get("generation_root")
        runtime_value = source.get("runtime_storage_root")
        profile_value = source.get("profile_path")
        generation = (
            Path(generation_value) if isinstance(generation_value, str) else None
        )
        runtime = Path(runtime_value) if isinstance(runtime_value, str) else None
        profile = Path(profile_value) if isinstance(profile_value, str) else None
        if generation is None and runtime is None:
            raise ValueError("desktop generation source missing")

        portable_states: tuple[str, str] | None = None
        if generation is not None:
            _validate_snapshot_tree(generation)
            checkpoint = generation / "sessions" / "checkpoints.sqlite3"
            references = _checkpoint_references(checkpoint)
            if references is None:
                raise ValueError("checkpoint_invalid")
            portable_states = (
                "initialized",
                "initialized" if references else "absent_uninitialized",
            )
            if runtime is None:
                _validate_profile_against_checkpoint(
                    generation / "profile" / "profile.json",
                    checkpoint,
                    allow_active_workspace_state=False,
                )

        runtime_states: tuple[str, str] | None = None
        if runtime is not None:
            if (
                generation is None
                and profile is not None
                and _entry_is_missing(runtime)
            ):
                _validate_profile_against_checkpoint(
                    profile,
                    None,
                    allow_active_workspace_state=True,
                )
                runtime_states = (
                    "absent_uninitialized",
                    "absent_uninitialized",
                )
            else:
                runtime_states = _validate_runtime_storage(runtime)
                profile_to_validate = (
                    profile
                    if profile is not None
                    else generation / "profile" / "profile.json"
                    if generation is not None
                    else None
                )
                if profile_to_validate is not None:
                    _validate_profile_against_checkpoint(
                        profile_to_validate,
                        runtime / "checkpoints.sqlite3",
                        allow_active_workspace_state=True,
                    )

        checkpoint_state, artifact_state = (
            portable_states
            or runtime_states
            or (
                "absent_uninitialized",
                "absent_uninitialized",
            )
        )
        return {
            "checkpoint_state": checkpoint_state,
            "artifact_state": artifact_state,
            "schema_version": 1,
        }


def _failed(reason: str) -> PortableSnapshotResult:
    return PortableSnapshotResult(ok=False, reason=reason, path=None)


def _empty_directory(path: Path) -> bool:
    try:
        return path.is_dir() and not any(path.iterdir())
    except OSError:
        return False


def _clear_directory(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def _entry_is_missing(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return True
    return False


def _regular_file(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode):
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return not bool(attributes & reparse)


def _regular_directory(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return not bool(attributes & reparse)


def _retained_descriptor_root(path: Path) -> bool:
    name = path.name
    return (
        path.is_absolute()
        and path.parent in {Path("/proc/self/fd"), Path("/dev/fd")}
        and name.isascii()
        and name.isdecimal()
    )


def _descriptor_path(root: Path, descriptor: int) -> Path:
    return root.parent / str(descriptor)


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and left.st_mode == right.st_mode
    )


def _duplicate_retained_root(root: Path) -> int:
    if not _retained_descriptor_root(root):
        raise ValueError("retained_root_invalid")
    descriptor = os.dup(int(root.name))
    try:
        opened = os.fstat(descriptor)
        visible = os.stat(root)
        if not stat.S_ISDIR(opened.st_mode) or not _same_identity(opened, visible):
            raise ValueError("retained_root_changed")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _entry_lstat(parent_fd: int, name: str) -> os.stat_result:
    return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)


def _open_regular_at(parent_fd: int, name: str) -> tuple[int, os.stat_result]:
    before = _entry_lstat(parent_fd, name)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("non_regular_source")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_identity(before, opened):
            raise ValueError("source_identity_changed")
        return descriptor, opened
    except Exception:
        os.close(descriptor)
        raise


def _open_directory_at(parent_fd: int, name: str) -> tuple[int, os.stat_result]:
    before = _entry_lstat(parent_fd, name)
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError("non_regular_directory")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or not _same_identity(before, opened):
            raise ValueError("source_identity_changed")
        return descriptor, opened
    except Exception:
        os.close(descriptor)
        raise


def _require_same_entry(parent_fd: int, name: str, opened: os.stat_result) -> None:
    current = _entry_lstat(parent_fd, name)
    if not _same_identity(current, opened):
        raise ValueError("source_identity_changed")


def _sqlite_backup_uri(source_uri: str, destination: Path) -> None:
    source_connection = sqlite3.connect(source_uri, uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def _stream_stable(
    path: Path, consumer: Callable[[bytes], object] | None = None
) -> tuple[int, str]:
    """Hash a no-follow regular file while optionally streaming each chunk.

    The before/open/after identity checks prevent a replacement from being
    accepted.  Callers use this for SQLite/artifact-sized payloads so those
    bytes are never accumulated in Python memory.
    """

    before = os.lstat(path)
    if not _regular_file(path):
        raise ValueError("non_regular_source")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    digest = hashlib.sha256()
    size = 0
    try:
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or getattr(opened, "st_ino", None) != getattr(before, "st_ino", None)
            or getattr(opened, "st_dev", None) != getattr(before, "st_dev", None)
        ):
            raise ValueError("source_identity_changed")
        while chunk := os.read(fd, _STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > before.st_size:
                raise ValueError("source_size_changed")
            digest.update(chunk)
            if consumer is not None:
                consumer(chunk)
    finally:
        os.close(fd)
    after = os.lstat(path)
    if (
        size != before.st_size
        or not stat.S_ISREG(after.st_mode)
        or after.st_size != before.st_size
        or getattr(after, "st_ino", None) != getattr(before, "st_ino", None)
        or getattr(after, "st_dev", None) != getattr(before, "st_dev", None)
    ):
        raise ValueError("source_identity_changed")
    return size, digest.hexdigest()


def _read_stable(path: Path) -> bytes:
    """Read bounded metadata only; payloads use ``_stream_stable``."""

    before = os.lstat(path)
    if before.st_size > _MAX_ARTIFACT_METADATA_BYTES:
        raise ValueError("metadata_too_large")
    chunks: list[bytes] = []
    _stream_stable(path, chunks.append)
    return b"".join(chunks)


def _stream_stable_at(
    parent_fd: int,
    name: str,
    consumer: Callable[[bytes], object] | None = None,
    *,
    expected: os.stat_result | None = None,
) -> tuple[int, str]:
    descriptor, opened = _open_regular_at(parent_fd, name)
    digest = hashlib.sha256()
    size = 0
    try:
        if expected is not None and not _same_identity(expected, opened):
            raise ValueError("source_identity_changed")
        while chunk := os.read(descriptor, _STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > opened.st_size:
                raise ValueError("source_size_changed")
            digest.update(chunk)
            if consumer is not None:
                consumer(chunk)
    finally:
        os.close(descriptor)
    _require_same_entry(parent_fd, name, opened)
    if size != opened.st_size:
        raise ValueError("source_size_changed")
    return size, digest.hexdigest()


def _read_stable_at(
    parent_fd: int,
    name: str,
    *,
    expected: os.stat_result | None = None,
) -> bytes:
    baseline = expected if expected is not None else _entry_lstat(parent_fd, name)
    if baseline.st_size > _MAX_ARTIFACT_METADATA_BYTES:
        raise ValueError("metadata_too_large")
    chunks: list[bytes] = []
    _stream_stable_at(
        parent_fd,
        name,
        chunks.append,
        expected=baseline,
    )
    return b"".join(chunks)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _stream_stable(path)[1]


def _safe_path_component(value: str) -> bool:
    """Accept opaque artifact identifiers only, never path syntax."""

    return (
        bool(value)
        and value not in {".", ".."}
        and not any(character in value for character in ("/", "\\", ":", "\x00"))
    )


def _checkpoint_session_count(checkpoint_path: Path) -> int:
    """Count durable sessions through the validated read-only SQLite seam."""

    uri = checkpoint_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        validate_sqlite_checkpoint_schema(connection)
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check != ("ok",):
            raise ValueError("checkpoint_invalid")
        row = connection.execute(
            "SELECT COUNT(DISTINCT session_id) FROM records"
        ).fetchone()
    finally:
        connection.close()
    if row is None or len(row) != 1 or not isinstance(row[0], int) or row[0] < 0:
        raise ValueError("checkpoint_invalid")
    return row[0]


def _checkpoint_references(
    checkpoint_path: Path,
) -> dict[tuple[str, str], str] | None:
    """Return ``(session, reference) -> call_id`` from a read-only snapshot."""

    references: dict[tuple[str, str], str] = {}
    # ``mode=ro`` is the dedicated no-write URI seam.  Do not mark a freshly
    # staged SQLite image immutable: some supported SQLite journal layouts need
    # ordinary read-only recovery before integrity queries.
    uri = checkpoint_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        validate_sqlite_checkpoint_schema(connection)
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check != ("ok",):
            return None
        rows = connection.execute("SELECT session_id, data FROM records").fetchall()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    for session_id, encoded in rows:
        if not isinstance(session_id, str) or not isinstance(encoded, (str, bytes)):
            return None
        try:
            record = deserialize_record(encoded)
        except (TypeError, ValueError):
            return None
        if record is None or record.session_id != session_id:
            return None
        if not isinstance(record, ReplacementDecisionRecord):
            continue
        payload = record.payload
        reference = payload.artifact_reference
        call_id = payload.replaced_call_id
        if not (_safe_path_component(session_id) and _safe_path_component(reference)):
            return None
        key = (session_id, reference)
        known = references.get(key)
        if known is not None and known != call_id:
            return None
        references[key] = call_id
    return references


def _copy_referenced_artifacts(
    storage_root: Path,
    destination: Path,
    references: dict[tuple[str, str], str],
    *,
    retained_root: bool = False,
) -> list[dict[str, Any]] | None:
    """Copy only checkpoint-referenced, stable ArtifactStore files.

    An existing artifact without a matching checkpoint reference is not silently
    omitted.  This is intentionally fail-closed instead of treating a directory
    walk as a backup allowlist. An exact retained ``/proc/self/fd/<fd>`` or
    ``/dev/fd/<fd>`` root is an already-validated capability, so only that root
    lookup may follow the descriptor link; every child remains no-follow checked.
    """

    if retained_root and _retained_descriptor_root(storage_root):
        return _copy_referenced_artifacts_retained(
            storage_root,
            destination,
            references,
        )
    if not _regular_directory(storage_root):
        return None
    expected = set(references)
    found: set[tuple[str, str]] = set()
    entries: list[dict[str, Any]] = []
    for session_dir in storage_root.iterdir():
        artifacts_dir = session_dir / "artifacts"
        if not _regular_directory(session_dir) or not artifacts_dir.exists():
            continue
        if not _regular_directory(artifacts_dir):
            return None
        for source in artifacts_dir.iterdir():
            if not _regular_file(source):
                return None
            suffix = source.suffix
            if suffix not in {".txt", ".json"}:
                return None
            if suffix == ".json" and not source.name.endswith(".meta.json"):
                return None
            reference = source.name.removesuffix(".meta.json").removesuffix(".txt")
            key = (session_dir.name, reference)
            if key not in expected:
                return None
            found.add(key)
    if found != expected:
        return None

    for session_id, reference in sorted(expected):
        payload_path = storage_root / session_id / "artifacts" / f"{reference}.txt"
        meta_path = storage_root / session_id / "artifacts" / f"{reference}.meta.json"
        target_dir = destination / "artifacts" / session_id
        target_dir.mkdir(parents=True, exist_ok=True)
        payload_target = target_dir / f"{reference}.txt"
        with payload_target.open("xb") as target:
            payload_size, payload_sha256 = _stream_stable(payload_path, target.write)
        metadata_bytes = _read_stable(meta_path)
        metadata = json.loads(metadata_bytes.decode("utf-8"))
        call_id = references[(session_id, reference)]
        if not isinstance(metadata, dict) or any(
            metadata.get(key) != value
            for key, value in {
                "reference": reference,
                "session_id": session_id,
                "call_id": call_id,
                "size": payload_size,
            }.items()
        ):
            return None
        media_kind = metadata.get("media_kind")
        if media_kind not in {"text", "image", "binary"}:
            return None
        metadata_target = target_dir / f"{reference}.meta.json"
        normalized_metadata = {
            "call_id": call_id,
            "content_origin": "gateway_tool_output",
            "media_kind": media_kind,
            "reference": reference,
            "session_id": session_id,
            "sha256": payload_sha256,
            "size": payload_size,
        }
        metadata_target.write_bytes(_canonical_json(normalized_metadata))
        metadata_size, metadata_sha256 = _stream_stable(metadata_target)
        entries.extend(
            (
                {
                    "path": payload_target.relative_to(destination).as_posix(),
                    "content_class": "artifact",
                    "size": payload_size,
                    "sha256": payload_sha256,
                },
                {
                    "path": metadata_target.relative_to(destination).as_posix(),
                    "content_class": "artifact_metadata",
                    "size": metadata_size,
                    "sha256": metadata_sha256,
                },
            )
        )
    return entries


def _copy_referenced_artifacts_retained(
    storage_root: Path,
    destination: Path,
    references: dict[tuple[str, str], str],
) -> list[dict[str, Any]] | None:
    root_fd: int | None = None
    try:
        root_fd = _duplicate_retained_root(storage_root)
        expected = set(references)
        found: set[tuple[str, str]] = set()
        session_identities: dict[str, os.stat_result] = {}
        artifacts_identities: dict[str, os.stat_result] = {}
        member_identities: dict[tuple[str, str], os.stat_result] = {}
        for session_name in os.listdir(root_fd):
            try:
                session_info = _entry_lstat(root_fd, session_name)
            except FileNotFoundError:
                return None
            if not stat.S_ISDIR(session_info.st_mode):
                continue
            session_fd: int | None = None
            artifacts_fd: int | None = None
            try:
                session_fd, opened_session = _open_directory_at(root_fd, session_name)
                if not _same_identity(session_info, opened_session):
                    return None
                try:
                    artifact_info = _entry_lstat(session_fd, "artifacts")
                except FileNotFoundError:
                    _require_same_entry(root_fd, session_name, opened_session)
                    continue
                if not stat.S_ISDIR(artifact_info.st_mode):
                    return None
                artifacts_fd, opened_artifacts = _open_directory_at(
                    session_fd, "artifacts"
                )
                if not _same_identity(artifact_info, opened_artifacts):
                    return None
                session_identities[session_name] = opened_session
                artifacts_identities[session_name] = opened_artifacts
                for source_name in os.listdir(artifacts_fd):
                    source_info = _entry_lstat(artifacts_fd, source_name)
                    if not stat.S_ISREG(source_info.st_mode):
                        return None
                    source = Path(source_name)
                    suffix = source.suffix
                    if suffix not in {".txt", ".json"}:
                        return None
                    if suffix == ".json" and not source.name.endswith(".meta.json"):
                        return None
                    reference = source.name.removesuffix(".meta.json").removesuffix(
                        ".txt"
                    )
                    key = (session_name, reference)
                    if key not in expected:
                        return None
                    member_identities[(session_name, source_name)] = source_info
                    found.add(key)
                _require_same_entry(session_fd, "artifacts", opened_artifacts)
                _require_same_entry(root_fd, session_name, opened_session)
            finally:
                if artifacts_fd is not None:
                    os.close(artifacts_fd)
                if session_fd is not None:
                    os.close(session_fd)
        if found != expected:
            return None

        entries: list[dict[str, Any]] = []
        for session_id, reference in sorted(expected):
            session_fd = None
            artifacts_fd = None
            try:
                session_fd, opened_session = _open_directory_at(root_fd, session_id)
                artifacts_fd, opened_artifacts = _open_directory_at(
                    session_fd, "artifacts"
                )
                inventoried_session = session_identities.get(session_id)
                inventoried_artifacts = artifacts_identities.get(session_id)
                payload_name = f"{reference}.txt"
                metadata_name = f"{reference}.meta.json"
                inventoried_payload = member_identities.get((session_id, payload_name))
                inventoried_metadata = member_identities.get(
                    (session_id, metadata_name)
                )
                if (
                    inventoried_session is None
                    or inventoried_artifacts is None
                    or inventoried_payload is None
                    or inventoried_metadata is None
                    or not _same_identity(inventoried_session, opened_session)
                    or not _same_identity(inventoried_artifacts, opened_artifacts)
                ):
                    return None
                target_dir = destination / "artifacts" / session_id
                target_dir.mkdir(parents=True, exist_ok=True)
                payload_target = target_dir / payload_name
                with payload_target.open("xb") as target:
                    payload_size, payload_sha256 = _stream_stable_at(
                        artifacts_fd,
                        payload_name,
                        target.write,
                        expected=inventoried_payload,
                    )
                metadata_bytes = _read_stable_at(
                    artifacts_fd,
                    metadata_name,
                    expected=inventoried_metadata,
                )
                metadata = json.loads(metadata_bytes.decode("utf-8"))
                call_id = references[(session_id, reference)]
                if not isinstance(metadata, dict) or any(
                    metadata.get(key) != value
                    for key, value in {
                        "reference": reference,
                        "session_id": session_id,
                        "call_id": call_id,
                        "size": payload_size,
                    }.items()
                ):
                    return None
                media_kind = metadata.get("media_kind")
                if media_kind not in {"text", "image", "binary"}:
                    return None
                _require_same_entry(session_fd, "artifacts", opened_artifacts)
                _require_same_entry(root_fd, session_id, opened_session)

                metadata_target = target_dir / f"{reference}.meta.json"
                normalized_metadata = {
                    "call_id": call_id,
                    "content_origin": "gateway_tool_output",
                    "media_kind": media_kind,
                    "reference": reference,
                    "session_id": session_id,
                    "sha256": payload_sha256,
                    "size": payload_size,
                }
                metadata_target.write_bytes(_canonical_json(normalized_metadata))
                metadata_size, metadata_sha256 = _stream_stable(metadata_target)
                entries.extend(
                    (
                        {
                            "path": payload_target.relative_to(destination).as_posix(),
                            "content_class": "artifact",
                            "size": payload_size,
                            "sha256": payload_sha256,
                        },
                        {
                            "path": metadata_target.relative_to(destination).as_posix(),
                            "content_class": "artifact_metadata",
                            "size": metadata_size,
                            "sha256": metadata_sha256,
                        },
                    )
                )
            finally:
                if artifacts_fd is not None:
                    os.close(artifacts_fd)
                if session_fd is not None:
                    os.close(session_fd)
        return entries
    except (OSError, ValueError):
        return None
    finally:
        if root_fd is not None:
            os.close(root_fd)


def _validate_snapshot_tree(source: Path) -> list[dict[str, Any]]:
    if not _regular_directory(source):
        raise ValueError("snapshot_root_invalid")
    checkpoint_path = source / "sessions" / "checkpoints.sqlite3"
    if not _regular_directory(source / "sessions") or not _regular_file(
        checkpoint_path
    ):
        raise ValueError("checkpoint_missing")
    references = _checkpoint_references(checkpoint_path)
    if references is None:
        raise ValueError("checkpoint_invalid")

    expected_paths = {"sessions/checkpoints.sqlite3"}
    entries: list[dict[str, Any]] = [
        {
            "path": "sessions/checkpoints.sqlite3",
            "content_class": "checkpoint",
            "size": checkpoint_path.stat().st_size,
            "sha256": _sha256_file(checkpoint_path),
        }
    ]
    # Restore passes the whole validated archive staging directory.  The profile
    # member is not Host snapshot payload, but allowing this one declared file
    # keeps the Host provider focused on its read-only checkpoint/artifact work.
    profile_path = source / "profile" / "profile.json"
    if profile_path.exists():
        if not _regular_directory(profile_path.parent) or not _regular_file(
            profile_path
        ):
            raise ValueError("profile_entry_invalid")
        expected_paths.add("profile/profile.json")
    manifest_path = source / "manifest.json"
    if manifest_path.exists():
        if not _regular_file(manifest_path):
            raise ValueError("manifest_entry_invalid")
        expected_paths.add("manifest.json")
    for session_id, reference in sorted(references):
        payload_path = source / "artifacts" / session_id / f"{reference}.txt"
        metadata_path = source / "artifacts" / session_id / f"{reference}.meta.json"
        payload_size, payload_sha256 = _stream_stable(payload_path)
        metadata = json.loads(_read_stable(metadata_path).decode("utf-8"))
        expected_metadata = {
            "call_id": references[(session_id, reference)],
            "content_origin": "gateway_tool_output",
            "media_kind": metadata.get("media_kind")
            if isinstance(metadata, dict)
            else None,
            "reference": reference,
            "session_id": session_id,
            "sha256": payload_sha256,
            "size": payload_size,
        }
        if (
            not isinstance(metadata, dict)
            or metadata.get("media_kind") not in {"text", "image", "binary"}
            or metadata != expected_metadata
        ):
            raise ValueError("artifact_metadata_invalid")
        metadata_size, metadata_sha256 = _stream_stable(metadata_path)
        for path, content_class, size, digest in (
            (payload_path, "artifact", payload_size, payload_sha256),
            (metadata_path, "artifact_metadata", metadata_size, metadata_sha256),
        ):
            rel = path.relative_to(source).as_posix()
            expected_paths.add(rel)
            entries.append(
                {
                    "path": rel,
                    "content_class": content_class,
                    "size": size,
                    "sha256": digest,
                }
            )
    actual_paths = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual_paths != expected_paths:
        raise ValueError("snapshot_unexpected_entry")
    return sorted(entries, key=lambda entry: str(entry["path"]))


def _validate_runtime_storage(storage: Path) -> tuple[str, str]:
    if not _regular_directory(storage):
        raise ValueError("runtime_storage_missing")
    checkpoint = storage / "checkpoints.sqlite3"
    if not _regular_file(checkpoint):
        raise ValueError("runtime_checkpoint_missing")
    references = _checkpoint_references(checkpoint)
    if references is None:
        raise ValueError("runtime_checkpoint_invalid")
    found: set[tuple[str, str]] = set()
    for session_dir in storage.iterdir():
        artifacts = session_dir / "artifacts"
        if session_dir.name == "checkpoints.sqlite3" or not artifacts.exists():
            continue
        if not _regular_directory(session_dir) or not _regular_directory(artifacts):
            raise ValueError("runtime_artifact_layout_invalid")
        for member in artifacts.iterdir():
            if not _regular_file(member) or not (
                member.name.endswith(".txt") or member.name.endswith(".meta.json")
            ):
                raise ValueError("runtime_artifact_layout_invalid")
            reference = member.name.removesuffix(".meta.json").removesuffix(".txt")
            found.add((session_dir.name, reference))
    if found != set(references):
        raise ValueError("runtime_artifact_inventory_mismatch")
    for (session_id, reference), call_id in references.items():
        artifacts = storage / session_id / "artifacts"
        payload = artifacts / f"{reference}.txt"
        metadata_path = artifacts / f"{reference}.meta.json"
        payload_size, payload_digest = _stream_stable(payload)
        metadata = json.loads(_read_stable(metadata_path))
        if not _runtime_artifact_metadata_is_valid(
            metadata,
            session_id=session_id,
            reference=reference,
            call_id=call_id,
            payload_size=payload_size,
            payload_digest=payload_digest,
        ):
            raise ValueError("runtime_artifact_metadata_invalid")
    return "initialized", "initialized" if references else "absent_uninitialized"


def _runtime_artifact_metadata_is_valid(
    metadata: object,
    *,
    session_id: str,
    reference: str,
    call_id: str,
    payload_size: int,
    payload_digest: str,
) -> bool:
    if not isinstance(metadata, dict) or metadata.get("media_kind") not in {
        "text",
        "image",
        "binary",
    }:
        return False
    portable = {
        "call_id": call_id,
        "content_origin": "gateway_tool_output",
        "media_kind": metadata["media_kind"],
        "reference": reference,
        "session_id": session_id,
        "sha256": payload_digest,
        "size": payload_size,
    }
    if metadata == portable:
        return True
    return (
        set(metadata)
        == {
            "call_id",
            "created_at",
            "media_kind",
            "reference",
            "session_id",
            "size",
        }
        and metadata.get("call_id") == call_id
        and metadata.get("reference") == reference
        and metadata.get("session_id") == session_id
        and metadata.get("size") == payload_size
        and isinstance(metadata.get("created_at"), str)
        and bool(metadata["created_at"])
    )


def _validate_profile_against_checkpoint(
    profile_path: Path,
    checkpoint_path: Path | None,
    *,
    allow_active_workspace_state: bool,
) -> None:
    raw = _read_stable(profile_path)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("profile_invalid") from exc
    if (
        not isinstance(value, dict)
        or _canonical_json(value) != raw
        or set(value)
        != {
            "principal_id",
            "profile_id",
            "projects",
            "preferences",
            "schema_version",
            "workspace_references",
        }
        or not isinstance(value.get("profile_id"), str)
        or not value["profile_id"]
        or not isinstance(value.get("principal_id"), str)
        or not value["principal_id"]
        or value.get("schema_version") != 1
        or not isinstance(value.get("projects"), list)
        or not isinstance(value.get("workspace_references"), list)
        or _safe_preferences(value.get("preferences")) != value.get("preferences")
    ):
        raise ValueError("profile_invalid")

    project_ids: set[str] = set()
    assigned_sessions: set[str] = set()
    session_ids = (
        _checkpoint_sessions_for_principal(checkpoint_path, value["principal_id"])
        if checkpoint_path is not None
        else set()
    )
    for project in value["projects"]:
        if (
            not isinstance(project, dict)
            or set(project) != {"id", "label", "session_ids", "workspace_id"}
            or not isinstance(project.get("id"), str)
            or not isinstance(project.get("label"), str)
            or not isinstance(project.get("session_ids"), list)
            or not all(isinstance(item, str) for item in project["session_ids"])
            or project.get("workspace_id") is not None
            and not isinstance(project.get("workspace_id"), str)
        ):
            raise ValueError("profile_invalid")
        project_sessions = set(project["session_ids"])
        if (
            project["id"] in project_ids
            or len(project_sessions) != len(project["session_ids"])
            or not project_sessions.issubset(session_ids)
            or not assigned_sessions.isdisjoint(project_sessions)
        ):
            raise ValueError("profile_project_inventory_mismatch")
        project_ids.add(project["id"])
        assigned_sessions.update(project_sessions)

    allowed_availability = (
        {"available", "relink_required"}
        if allow_active_workspace_state
        else {"relink_required"}
    )
    for reference in value["workspace_references"]:
        if (
            not isinstance(reference, dict)
            or set(reference) != {"id", "label", "availability", "actions"}
            or not isinstance(reference.get("id"), str)
            or not isinstance(reference.get("label"), str)
            or reference.get("availability") not in allowed_availability
            or reference.get("actions") != ["open", "relink", "remove"]
        ):
            raise ValueError("profile_invalid")


def _checkpoint_sessions_for_principal(
    checkpoint_path: Path, principal_id: str
) -> set[str]:
    uri = checkpoint_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("profile_checkpoint_invalid")
        rows = connection.execute("SELECT session_id, data FROM records").fetchall()
    except sqlite3.Error as exc:
        raise ValueError("profile_checkpoint_invalid") from exc
    finally:
        connection.close()

    sessions: set[str] = set()
    metadata_sessions: set[str] = set()
    for session_id, encoded in rows:
        if not isinstance(encoded, (str, bytes)):
            raise ValueError("profile_checkpoint_invalid")
        try:
            record = deserialize_record(encoded)
        except (TypeError, ValueError) as exc:
            raise ValueError("profile_checkpoint_invalid") from exc
        if (
            not isinstance(session_id, str)
            or record is None
            or record.session_id != session_id
        ):
            raise ValueError("profile_checkpoint_invalid")
        sessions.add(session_id)
        if isinstance(record, SessionMetaRecord):
            if record.payload.principal_id != principal_id:
                raise ValueError("profile_principal_mismatch")
            metadata_sessions.add(session_id)
    if sessions != metadata_sessions:
        raise ValueError("profile_checkpoint_missing_metadata")
    return sessions


def _safe_preferences(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_safe_preferences(item) for item in value]
    if not isinstance(value, dict):
        raise ValueError("profile_invalid")
    excluded = ("draft", "credential", "token", "secret", "private", "path")
    return {
        str(key): _safe_preferences(item)
        for key, item in value.items()
        if isinstance(key, str) and not any(term in key.lower() for term in excluded)
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
