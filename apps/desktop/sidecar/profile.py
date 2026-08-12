"""OS-backed Profile Ownership Lock + portable ProfileState (078 T025/T039)."""

from __future__ import annotations

import json
import os
import stat
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .durability import (
        is_canonical_generation_id,
        is_link_or_reparse,
        owned_generation_directory,
    )
except ImportError:  # pragma: no cover
    from durability import (  # type: ignore[no-redef]
        is_canonical_generation_id,
        is_link_or_reparse,
        owned_generation_directory,
    )

PORTABLE_EXCLUDE_LOCK_NAME = "profile-owner.lock"
_DRAFT_KEYS = frozenset(
    {
        "draft",
        "composer_draft",
        "unsent_draft",
        "pane_draft",
        "transient_draft",
    }
)


class ProfileBusyError(RuntimeError):
    """Second process for the same canonical profile root."""

    def __init__(self) -> None:
        super().__init__("profile busy")
        self.public_code = "busy"


class ProfileLockUnsupportedError(RuntimeError):
    """Locking is unsupported on this volume/API."""

    def __init__(self, detail: str = "unsupported") -> None:
        super().__init__(detail)
        self.public_code = "durability_unsupported"


def _exact_lock_child(parent: Path, name: str) -> Path | None:
    try:
        parent_info = os.lstat(parent)
    except OSError as exc:
        raise ValueError("unsafe profile lock path") from exc
    if not stat.S_ISDIR(parent_info.st_mode) or is_link_or_reparse(parent_info):
        raise ValueError("unsafe profile lock path")
    try:
        with os.scandir(parent) as entries:
            exact = any(entry.name == name for entry in entries)
    except OSError as exc:
        raise ValueError("unsafe profile lock path") from exc
    child = parent / name
    if exact:
        return child
    try:
        os.lstat(child)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("unsafe profile lock path") from exc
    raise ValueError("unsafe profile lock path alias")


def _owned_lock_directory(root: Path) -> Path:
    lock_dir = _exact_lock_child(root, "device-private")
    if lock_dir is None:
        try:
            os.mkdir(root / "device-private", 0o700)
        except FileExistsError:
            pass
        lock_dir = _exact_lock_child(root, "device-private")
    if lock_dir is None:
        raise ValueError("unsafe profile lock path")
    info = os.lstat(lock_dir)
    if not stat.S_ISDIR(info.st_mode) or is_link_or_reparse(info):
        raise ValueError("unsafe profile lock path")
    return lock_dir


def _open_owned_lock_file(lock_dir: Path) -> tuple[object, Path]:
    parent_before = os.lstat(lock_dir)
    lock_path = _exact_lock_child(lock_dir, "profile-owner.lock")
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if lock_path is None:
        lock_path = lock_dir / "profile-owner.lock"
        try:
            descriptor = os.open(
                lock_path,
                flags | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            lock_path = _exact_lock_child(lock_dir, "profile-owner.lock")
            if lock_path is None:
                raise ValueError("unsafe profile lock path") from None
            descriptor = os.open(lock_path, flags)
    else:
        before = os.lstat(lock_path)
        if not stat.S_ISREG(before.st_mode) or is_link_or_reparse(before):
            raise ValueError("unsafe profile lock path")
        descriptor = os.open(lock_path, flags)

    try:
        opened = os.fstat(descriptor)
        after = os.lstat(lock_path)
        parent_after = os.lstat(lock_dir)
        exact = _exact_lock_child(lock_dir, "profile-owner.lock")
        if (
            exact != lock_path
            or parent_before.st_dev != parent_after.st_dev
            or parent_before.st_ino != parent_after.st_ino
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(after.st_mode)
            or is_link_or_reparse(after)
            or opened.st_dev != after.st_dev
            or opened.st_ino != after.st_ino
        ):
            raise ValueError("unsafe profile lock path")
        return os.fdopen(descriptor, "r+b"), lock_path
    except Exception:
        os.close(descriptor)
        raise


@dataclass
class ProfileOwnershipLock:
    """Exclusive OS lock for a canonical profile root (generation-external)."""

    root: Path
    _fh: object | None = None
    _lock_path: Path | None = None

    @classmethod
    def for_root(cls, root: Path) -> ProfileOwnershipLock:
        return cls(root=root.resolve())

    def acquire(self) -> None:
        root = self.root
        try:
            if not root.exists():
                root.mkdir(parents=True, exist_ok=True)
            root = root.resolve(strict=True)
            root_info = os.lstat(root)
            if not stat.S_ISDIR(root_info.st_mode) or is_link_or_reparse(root_info):
                raise ValueError("unsafe profile lock path")
            lock_dir = _owned_lock_directory(root)
            fh, lock_path = _open_owned_lock_file(lock_dir)
        except (OSError, ValueError) as exc:
            raise ProfileLockUnsupportedError("unsafe profile lock path") from exc
        self.root = root
        self._lock_path = lock_path
        self._fh = fh
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                if fh.read(1) == b"":
                    fh.write(b"\0")
                    fh.flush()
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            self._fh = None
            if (
                getattr(exc, "errno", None)
                in {
                    11,
                    13,
                    16,
                    35,
                    36,
                }
                or "locked" in str(exc).lower()
            ):
                raise ProfileBusyError from exc
            raise ProfileLockUnsupportedError(str(exc)) from exc

    def release(self) -> None:
        """Release the process-held ownership lock after Host/store teardown."""

        fh = self._fh
        if fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()
            self._fh = None

    def __enter__(self) -> ProfileOwnershipLock:
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


def same_canonical_root(a: Path, b: Path) -> bool:
    return a.resolve() == b.resolve()


@dataclass
class ProfileState:
    """Portable profile identity under the active generation (not device-private)."""

    root: Path
    generation_id: str = "g0"
    profile_id: str = field(default="")
    principal_id: str = field(default="")

    @classmethod
    def open(cls, root: Path, *, generation_id: str = "g0") -> ProfileState:
        if not is_canonical_generation_id(generation_id):
            raise ValueError("invalid generation id")
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        state = cls(root=root, generation_id=generation_id)
        data = state.load_portable()
        if not data.get("profile_id") or not data.get("principal_id"):
            data["profile_id"] = data.get("profile_id") or str(uuid.uuid4())
            data["principal_id"] = data.get("principal_id") or str(uuid.uuid4())
            data.setdefault("schema_version", 1)
            data.setdefault("projects", [])
            data.setdefault("workspace_references", [])
            data.setdefault("preferences", {})
            state.save_portable(data)
        state.profile_id = str(data["profile_id"])
        state.principal_id = str(data["principal_id"])
        return state

    def generation_dir(self) -> Path:
        return owned_generation_directory(
            self.root,
            "generations",
            self.generation_id,
            create=True,
        )

    def portable_path(self) -> Path:
        generation = self.generation_dir()
        restored_parent = generation / "profile"
        try:
            parent_info = os.lstat(restored_parent)
        except FileNotFoundError:
            parent_info = None
        if parent_info is not None and (
            not stat.S_ISDIR(parent_info.st_mode) or is_link_or_reparse(parent_info)
        ):
            raise ValueError("unsafe profile path")
        restored = restored_parent / "profile.json"
        if _regular_profile_path(restored):
            return restored
        # Restore candidates retain the Host-validator's canonical snapshot shape.
        # Existing pristine generations retain their original flat portable state.
        portable = generation / "profile.json"
        _regular_profile_path(portable)
        return portable

    def load_portable(self) -> dict[str, Any]:
        path = self.portable_path()
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def save_portable(self, data: dict[str, Any]) -> None:
        cleaned = _strip_drafts(dict(data))
        # Principal immutability: never allow overwrite to a different value once set.
        if self.principal_id and cleaned.get("principal_id") not in (
            None,
            self.principal_id,
        ):
            cleaned["principal_id"] = self.principal_id
        if self.profile_id and cleaned.get("profile_id") not in (None, self.profile_id):
            cleaned["profile_id"] = self.profile_id
        path = self.portable_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as destination:
                destination.write(
                    json.dumps(
                        cleaned,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                )
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        if cleaned.get("principal_id"):
            self.principal_id = str(cleaned["principal_id"])
        if cleaned.get("profile_id"):
            self.profile_id = str(cleaned["profile_id"])

    def set_preference(self, key: str, value: Any) -> None:
        if key.lower() in _DRAFT_KEYS or "draft" in key.lower():
            raise ValueError("draft preferences are renderer-transient only")
        data = self.load_portable()
        prefs = dict(data.get("preferences") or {})
        prefs[key] = value
        data["preferences"] = prefs
        self.save_portable(data)

    def portable_member_names(self) -> set[str]:
        """Names included in a portable export (excludes device-private)."""

        names: set[str] = set()
        portable = self.load_portable()
        names.update(portable.keys())
        # Explicitly never export lock / device-private.
        names.discard(PORTABLE_EXCLUDE_LOCK_NAME)
        return names


def _regular_profile_path(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode) or is_link_or_reparse(info):
        raise ValueError("unsafe profile path")
    return True


def _strip_drafts(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in _DRAFT_KEYS or "draft" in key.lower():
            continue
        if key == "preferences" and isinstance(value, dict):
            out[key] = {
                k: v
                for k, v in value.items()
                if k.lower() not in _DRAFT_KEYS and "draft" not in k.lower()
            }
        else:
            out[key] = value
    return out
