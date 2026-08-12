"""Canonical portable-backup archive creation and verification (078 T069/T076).

This module owns the ZIP container only.  Restore staging/pointer publication is
intentionally outside this boundary (T070); callers may use ``validate_archive``
to validate a finished archive without extracting it.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import unicodedata
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_FORMAT = "loopplane.desktop.backup"
_VERSION = {"major": 1, "minor": 0}
_MAX_ARCHIVE_BYTES = 4 * 1024 * 1024 * 1024
_MAX_ENTRY_COUNT = 10_000
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024
_MAX_SINGLE_ENTRY_BYTES = 2 * 1024 * 1024 * 1024
_MAX_EXPANSION_RATIO = 200
_STREAM_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class _SnapshotEntry:
    path: str
    content_class: str
    source: Path


class ArchiveValidationError(ValueError):
    """Bounded archive-integrity failure; callers map it to a public-safe error."""


def canonical_json(value: Any) -> bytes:
    """V1 canonical UTF-8 JSON: sorted keys, no whitespace, finite values only."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def create_portable_archive(
    destination: Path,
    *,
    profile_portable: dict[str, Any],
    snapshot_root: Path,
    disclosure_acknowledged: bool,
) -> dict[str, Any]:
    """Build, reopen/revalidate, flush, then atomically publish one backup.

    The temporary file is created in the destination directory with exclusive,
    restrictive permissions.  Nothing replaces an existing destination until
    ZIP central-directory and streamed entry validation succeeds.
    """

    if disclosure_acknowledged is not True:
        raise ArchiveValidationError("disclosure_not_acknowledged")
    destination = Path(destination)
    parent = destination.parent
    if not parent.is_dir():
        raise ArchiveValidationError("destination_parent_unavailable")
    profile = _portable_profile(profile_portable)
    source_entries = _snapshot_entries(Path(snapshot_root))
    profile_bytes = canonical_json(profile)
    entries = [
        {
            "path": "profile/profile.json",
            "kind": "regular_file",
            "content_class": "profile",
            "size": len(profile_bytes),
            "sha256": hashlib.sha256(profile_bytes).hexdigest(),
        }
    ]
    for source in source_entries:
        size, digest = _stream_stable(source.source)
        entries.append(
            {
                "path": source.path,
                "kind": "regular_file",
                "content_class": source.content_class,
                "size": size,
                "sha256": digest,
            }
        )
    entries.sort(key=lambda entry: str(entry["path"]))
    manifest = {
        "format": _FORMAT,
        "version": _VERSION,
        "profile_schema_version": profile["schema_version"],
        "created_at": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "profile_id": profile["profile_id"],
        "principal_id": profile["principal_id"],
        "disclosure": {"version": 1, "acknowledged": True},
        "totals": {
            "entries": len(entries),
            "compressed_bytes": sum(int(entry["size"]) for entry in entries),
            "uncompressed_bytes": sum(int(entry["size"]) for entry in entries),
        },
        "entries": entries,
    }
    manifest_bytes = canonical_json(manifest)

    temporary = _new_restrictive_temp(parent)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(_zip_info("manifest.json"), manifest_bytes)
            sources = {source.path: source for source in source_entries}
            for entry in entries:
                path = str(entry["path"])
                if path == "profile/profile.json":
                    archive.writestr(_zip_info(path), profile_bytes)
                    continue
                source = sources[path]
                with archive.open(_zip_info(path), "w") as target:
                    size, digest = _stream_stable(source.source, target.write)
                if size != entry["size"] or digest != entry["sha256"]:
                    raise ArchiveValidationError("snapshot_changed")
        # Reopen, inspect central/local metadata, and stream hashes before publish.
        validated = validate_archive(temporary)
        if validated != manifest:
            raise ArchiveValidationError("manifest_revalidation_failed")
        _flush_file(temporary)
        os.replace(temporary, destination)
        _flush_directory(parent)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return {
        "finalized": True,
        "format": _FORMAT,
        "entry_count": len(entries),
        "compressed_bytes": manifest["totals"]["compressed_bytes"],
        "uncompressed_bytes": manifest["totals"]["uncompressed_bytes"],
    }


def validate_archive(path: Path) -> dict[str, Any]:
    """Validate the V1 manifest and every declared ZIP member without staging."""

    path = Path(path)
    if not _regular_file(path) or path.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise ArchiveValidationError("archive_invalid")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _MAX_ENTRY_COUNT + 1:
                raise ArchiveValidationError("archive_limits")
            names = [info.filename for info in infos]
            if names.count("manifest.json") != 1 or names[0] != "manifest.json":
                raise ArchiveValidationError("manifest_missing")
            if len(names) != len(set(names)):
                raise ArchiveValidationError("archive_duplicate_entries")
            manifest_info = infos[0]
            _validate_info(manifest_info, allow_manifest=True)
            _validate_local_header(path, manifest_info)
            if manifest_info.file_size > _MAX_MANIFEST_BYTES:
                raise ArchiveValidationError("manifest_too_large")
            raw_manifest = archive.read(manifest_info)
            manifest = _parse_manifest(raw_manifest)
            entries = _validate_manifest_shape(manifest)
            declared = [str(entry["path"]) for entry in entries]
            if not {
                "profile/profile.json",
                "sessions/checkpoints.sqlite3",
            }.issubset(declared):
                raise ArchiveValidationError("archive_required_member_missing")
            actual = names[1:]
            if actual != declared:
                raise ArchiveValidationError("archive_declaration_mismatch")
            _validate_path_collisions(declared)
            total_size = 0
            total_compressed = 0
            for info, entry in zip(infos[1:], entries, strict=True):
                _validate_info(info)
                _validate_local_header(path, info)
                _validate_path(info.filename, str(entry["content_class"]))
                if info.file_size != entry["size"]:
                    raise ArchiveValidationError("archive_size_mismatch")
                total_size += info.file_size
                total_compressed += info.compress_size
                digest, actual_size = _stream_digest(archive, info)
                if actual_size != info.file_size or digest != entry["sha256"]:
                    raise ArchiveValidationError("archive_integrity_failed")
            totals = manifest["totals"]
            if (
                total_size != totals["uncompressed_bytes"]
                or total_compressed != totals["compressed_bytes"]
                or len(entries) != totals["entries"]
            ):
                raise ArchiveValidationError("archive_totals_mismatch")
            if total_size and (
                total_compressed == 0
                or total_size > total_compressed * _MAX_EXPANSION_RATIO
            ):
                raise ArchiveValidationError("archive_expansion_ratio")
            return manifest
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, ArchiveValidationError):
            raise
        raise ArchiveValidationError("archive_invalid") from exc


def _new_restrictive_temp(parent: Path) -> Path:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    for _ in range(16):
        candidate = parent / f".{uuid.uuid4().hex}.loopplane-backup.tmp"
        try:
            descriptor = os.open(candidate, flags, 0o600)
        except FileExistsError:
            continue
        else:
            os.close(descriptor)
            return candidate
    raise ArchiveValidationError("temporary_creation_failed")


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = stat.S_IFREG << 16
    return info


def _portable_profile(data: dict[str, Any]) -> dict[str, Any]:
    profile_id = data.get("profile_id")
    principal_id = data.get("principal_id")
    schema_version = data.get("schema_version", 1)
    if (
        not isinstance(profile_id, str)
        or not profile_id
        or not isinstance(principal_id, str)
        or not principal_id
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        raise ArchiveValidationError("profile_invalid")
    projects = []
    for item in data.get("projects", []):
        if not isinstance(item, dict):
            raise ArchiveValidationError("profile_invalid")
        project_id = item.get("id")
        label = item.get("label")
        session_ids = item.get("session_ids", [])
        workspace_id = item.get("workspace_id")
        if (
            not isinstance(project_id, str)
            or not isinstance(label, str)
            or not isinstance(session_ids, list)
            or not all(isinstance(value, str) for value in session_ids)
            or workspace_id is not None
            and not isinstance(workspace_id, str)
        ):
            raise ArchiveValidationError("profile_invalid")
        projects.append(
            {
                "id": project_id,
                "label": label,
                "session_ids": session_ids,
                "workspace_id": workspace_id,
            }
        )
    references = []
    for item in data.get("workspace_references", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ArchiveValidationError("profile_invalid")
        label = item.get("label")
        if not isinstance(label, str):
            raise ArchiveValidationError("profile_invalid")
        references.append(
            {
                "id": item["id"],
                "label": label,
                "availability": "relink_required",
                "actions": ["open", "relink", "remove"],
            }
        )
    preferences = _safe_preferences(data.get("preferences", {}))
    return {
        "principal_id": principal_id,
        "profile_id": profile_id,
        "projects": projects,
        "preferences": preferences,
        "schema_version": schema_version,
        "workspace_references": references,
    }


def _safe_preferences(value: Any) -> Any:
    """Keep safe UI state and drop drafts/private configuration recursively."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_safe_preferences(item) for item in value]
    if not isinstance(value, dict):
        raise ArchiveValidationError("profile_invalid")
    excluded = ("draft", "credential", "token", "secret", "private", "path")
    return {
        str(key): _safe_preferences(item)
        for key, item in value.items()
        if isinstance(key, str) and not any(term in key.lower() for term in excluded)
    }


def _snapshot_entries(root: Path) -> list[_SnapshotEntry]:
    """Describe the Host snapshot allowlist without materializing its files."""

    checkpoint = root / "sessions" / "checkpoints.sqlite3"
    if not _regular_directory(root) or not _regular_file(checkpoint):
        raise ArchiveValidationError("snapshot_invalid")
    found = {"sessions/checkpoints.sqlite3"}
    result = [_SnapshotEntry("sessions/checkpoints.sqlite3", "checkpoint", checkpoint)]
    artifacts = root / "artifacts"
    if artifacts.exists():
        if not _regular_directory(artifacts):
            raise ArchiveValidationError("snapshot_invalid")
        for session_dir in artifacts.iterdir():
            if not _regular_directory(session_dir):
                raise ArchiveValidationError("snapshot_invalid")
            for member in session_dir.iterdir():
                if not _regular_file(member) or not (
                    member.name.endswith(".txt") or member.name.endswith(".meta.json")
                ):
                    raise ArchiveValidationError("snapshot_invalid")
                rel = member.relative_to(root).as_posix()
                content_class = (
                    "artifact" if rel.endswith(".txt") else "artifact_metadata"
                )
                _validate_path(rel, content_class)
                found.add(rel)
                result.append(_SnapshotEntry(rel, content_class, member))
    actual = {
        member.relative_to(root).as_posix()
        for member in root.rglob("*")
        if member.is_file() or member.is_symlink()
    }
    if actual != found:
        raise ArchiveValidationError("snapshot_invalid")
    return sorted(result, key=lambda item: item.path)


def _parse_manifest(raw: bytes) -> dict[str, Any]:
    try:
        decoded = raw.decode("utf-8")
        value = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ArchiveValidationError) as exc:
        raise ArchiveValidationError("manifest_invalid") from exc
    if not isinstance(value, dict) or canonical_json(value) != raw:
        raise ArchiveValidationError("manifest_not_canonical")
    _validate_json_depth(value)
    return value


def _validate_json_depth(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise ArchiveValidationError("manifest_too_deep")
    if isinstance(value, dict):
        for child in value.values():
            _validate_json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _validate_json_depth(child, depth + 1)


def _reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ArchiveValidationError("manifest_duplicate_key")
        result[key] = value
    return result


def _validate_manifest_shape(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    required = {
        "format",
        "version",
        "profile_schema_version",
        "created_at",
        "profile_id",
        "principal_id",
        "disclosure",
        "totals",
        "entries",
    }
    if set(manifest) != required or manifest.get("format") != _FORMAT:
        raise ArchiveValidationError("manifest_incompatible")
    if (
        manifest.get("version") != _VERSION
        or manifest.get("profile_schema_version") != 1
    ):
        raise ArchiveValidationError("manifest_incompatible")
    if not isinstance(manifest["profile_id"], str) or not isinstance(
        manifest["principal_id"], str
    ):
        raise ArchiveValidationError("manifest_invalid")
    if manifest.get("disclosure") != {"version": 1, "acknowledged": True}:
        raise ArchiveValidationError("manifest_disclosure_invalid")
    totals = manifest.get("totals")
    entries = manifest.get("entries")
    if (
        not isinstance(totals, dict)
        or set(totals) != {"entries", "compressed_bytes", "uncompressed_bytes"}
        or not all(isinstance(value, int) and value >= 0 for value in totals.values())
        or not isinstance(entries, list)
        or totals["entries"] != len(entries)
        or len(entries) > _MAX_ENTRY_COUNT
        or totals["uncompressed_bytes"] > _MAX_UNCOMPRESSED_BYTES
    ):
        raise ArchiveValidationError("manifest_limits")
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "kind",
            "content_class",
            "size",
            "sha256",
        }:
            raise ArchiveValidationError("manifest_entry_invalid")
        path = entry["path"]
        if (
            not isinstance(path, str)
            or entry["kind"] != "regular_file"
            or not isinstance(entry["content_class"], str)
            or not isinstance(entry["size"], int)
            or entry["size"] < 0
            or not isinstance(entry["sha256"], str)
            or len(entry["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in entry["sha256"])
        ):
            raise ArchiveValidationError("manifest_entry_invalid")
        if entry["size"] > _MAX_SINGLE_ENTRY_BYTES:
            raise ArchiveValidationError("manifest_limits")
        _validate_path(path, entry["content_class"])
        normalized.append(entry)
    names = [str(entry["path"]) for entry in normalized]
    if names != sorted(names) or len(names) != len(set(names)):
        raise ArchiveValidationError("manifest_entry_order")
    return normalized


def _validate_path(path: str, content_class: str) -> None:
    if (
        not path
        or path.startswith("/")
        or "\\" in path
        or ":" in path
        or len(path.encode("utf-8")) > 1024
        or path != unicodedata.normalize("NFC", path)
        or any(unicodedata.category(char) == "Cc" for char in path)
        or any(
            not segment or segment in {".", ".."} or segment.endswith((".", " "))
            for segment in path.split("/")
        )
    ):
        raise ArchiveValidationError("archive_path_invalid")
    allowed = (
        (content_class == "profile" and path == "profile/profile.json")
        or (content_class == "checkpoint" and path == "sessions/checkpoints.sqlite3")
        or (
            content_class == "artifact"
            and len(path.split("/")) == 3
            and path.startswith("artifacts/")
            and path.endswith(".txt")
        )
        or (
            content_class == "artifact_metadata"
            and len(path.split("/")) == 3
            and path.startswith("artifacts/")
            and path.endswith(".meta.json")
        )
    )
    if not allowed:
        raise ArchiveValidationError("archive_path_invalid")


def _validate_path_collisions(paths: list[str]) -> None:
    normalized: set[str] = set()
    casefolded: set[str] = set()
    for path in paths:
        nfc = unicodedata.normalize("NFC", path)
        folded = nfc.casefold()
        if nfc in normalized or folded in casefolded:
            raise ArchiveValidationError("archive_path_collision")
        normalized.add(nfc)
        casefolded.add(folded)


def _validate_info(info: zipfile.ZipInfo, *, allow_manifest: bool = False) -> None:
    external_mode = (info.external_attr >> 16) & 0xFFFF
    if (
        info.is_dir()
        or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
        or stat.S_IFMT(external_mode) != stat.S_IFREG
    ):
        raise ArchiveValidationError("archive_entry_type_invalid")
    if info.flag_bits & 0x1:
        raise ArchiveValidationError("archive_encrypted")
    # A descriptor leaves local-header sizes indeterminate.  V1 rejects it so
    # the bounded local-header parity check below can prove exact agreement.
    if info.flag_bits & 0x8:
        raise ArchiveValidationError("archive_descriptor_unsupported")
    limit = _MAX_MANIFEST_BYTES if allow_manifest else _MAX_SINGLE_ENTRY_BYTES
    if info.file_size > limit:
        raise ArchiveValidationError("archive_limits")


def _validate_local_header(path: Path, info: zipfile.ZipInfo) -> None:
    """Boundedly compare central metadata with the matching local header.

    ``zipfile`` exposes central-directory data but no public local-header parity
    API.  This parser reads only the fixed header plus bounded filename/extra
    area and rejects descriptors, so V1 can compare names, method, flags and
    sizes without claiming a stdlib guarantee it does not provide.
    """

    try:
        with path.open("rb") as source:
            source.seek(info.header_offset)
            fixed = source.read(30)
            if len(fixed) != 30:
                raise ArchiveValidationError("archive_local_header_invalid")
            (
                signature,
                _version,
                flags,
                method,
                _mtime,
                _mdate,
                crc,
                compressed_size,
                uncompressed_size,
                name_length,
                extra_length,
            ) = struct.unpack("<IHHHHHIIIHH", fixed)
            if signature != 0x04034B50 or name_length > 1024 or extra_length > 65535:
                raise ArchiveValidationError("archive_local_header_invalid")
            raw_name = source.read(name_length)
            if (
                len(raw_name) != name_length
                or len(source.read(extra_length)) != extra_length
            ):
                raise ArchiveValidationError("archive_local_header_invalid")
    except OSError as exc:
        raise ArchiveValidationError("archive_local_header_invalid") from exc
    encoding = "utf-8" if info.flag_bits & 0x800 else "cp437"
    try:
        expected_name = info.filename.encode(encoding)
    except UnicodeEncodeError as exc:
        raise ArchiveValidationError("archive_local_header_invalid") from exc
    if (
        raw_name != expected_name
        or flags != info.flag_bits
        or method != info.compress_type
        or crc != info.CRC
        or compressed_size != info.compress_size
        or uncompressed_size != info.file_size
    ):
        raise ArchiveValidationError("archive_local_header_mismatch")


def _stream_digest(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with archive.open(info, "r") as member:
        while chunk := member.read(1024 * 1024):
            size += len(chunk)
            if size > _MAX_SINGLE_ENTRY_BYTES:
                raise ArchiveValidationError("archive_limits")
            digest.update(chunk)
    return digest.hexdigest(), size


def _regular_file(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode):
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    return not bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _regular_directory(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    return not bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _stream_stable(
    path: Path, consumer: Callable[[bytes], object] | None = None
) -> tuple[int, str]:
    """Stream a stable snapshot member without materializing its bytes."""

    before = os.lstat(path)
    if not _regular_file(path):
        raise ArchiveValidationError("snapshot_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    size = 0
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or opened.st_ino != before.st_ino
            or opened.st_dev != before.st_dev
        ):
            raise ArchiveValidationError("snapshot_changed")
        while chunk := os.read(descriptor, _STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > before.st_size or size > _MAX_SINGLE_ENTRY_BYTES:
                raise ArchiveValidationError("snapshot_changed")
            digest.update(chunk)
            if consumer is not None:
                consumer(chunk)
    finally:
        os.close(descriptor)
    after = os.lstat(path)
    if (
        size != before.st_size
        or after.st_size != before.st_size
        or after.st_ino != before.st_ino
        or after.st_dev != before.st_dev
        or not stat.S_ISREG(after.st_mode)
    ):
        raise ArchiveValidationError("snapshot_changed")
    return size, digest.hexdigest()


def _read_stable(_path: Path) -> bytes:
    """Retained sentinel: snapshot members must never use unbounded reads."""

    raise ArchiveValidationError("unbounded_snapshot_read_forbidden")


def _flush_file(path: Path) -> None:
    # Windows requires a writable descriptor for the documented file flush.
    descriptor = os.open(path, os.O_RDWR | getattr(os, "O_BINARY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _flush_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
