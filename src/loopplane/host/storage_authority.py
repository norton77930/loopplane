"""Optional retained storage authority for Desktop Host composition (078 T079)."""

from __future__ import annotations

import os
import stat
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_GENERATION_ID_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_WINDOWS_RESERVED_GENERATION_IDS = frozenset(
    {"aux", "con", "nul", "prn"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


class StorageAuthorityLease(Protocol):
    """One per-Host lease that validates and retains its configured root."""

    @property
    def root(self) -> Path: ...

    def validate(self) -> None: ...

    def close(self) -> None: ...


class StorageAuthorityFactory(Protocol):
    """Reusable factory that acquires one independent lease per Host."""

    def acquire(self, root: Path) -> StorageAuthorityLease: ...


@dataclass(frozen=True, slots=True)
class _DirectoryIdentity:
    device: int
    inode: int


class DesktopStorageAuthorityFactory:
    """Bind Desktop storage to one canonical profile-owned generation tree."""

    def __init__(self, profile_root: Path) -> None:
        self._profile_root = Path(profile_root)
        self._lock = threading.Lock()
        self._windows_ancestor_handles: list[int] = []
        self._windows_ancestor_paths: tuple[Path, Path] | None = None
        self._windows_ancestor_identities: tuple[_DirectoryIdentity, ...] | None = None
        self._windows_ancestor_users = 0
        self._windows_ancestor_close_failed = False

    def acquire(self, root: Path) -> StorageAuthorityLease:
        return _DesktopStorageAuthorityLease(self, self._profile_root, Path(root))

    def _acquire_windows_ancestors(
        self,
        paths: tuple[Path, Path],
        identities: tuple[_DirectoryIdentity, ...],
    ) -> None:
        with self._lock:
            if self._windows_ancestor_close_failed:
                raise RuntimeError("storage authority close retry is pending")
            if self._windows_ancestor_users:
                if (
                    self._windows_ancestor_paths != paths
                    or self._windows_ancestor_identities != identities
                ):
                    raise RuntimeError("storage authority identity changed")
                self._validate_windows_ancestors_unlocked(paths, identities)
                self._windows_ancestor_users += 1
                return
            opened: list[int] = []
            try:
                opened = [_windows_open_directory(path) for path in paths]
                self._windows_ancestor_handles = opened
                self._windows_ancestor_paths = paths
                self._windows_ancestor_identities = identities
                self._windows_ancestor_users = 1
                self._validate_windows_ancestors_unlocked(paths, identities)
            except Exception:
                for handle in reversed(opened):
                    try:
                        _windows_close_handle(handle)
                    except OSError:
                        pass
                self._windows_ancestor_handles = []
                self._windows_ancestor_paths = None
                self._windows_ancestor_identities = None
                self._windows_ancestor_users = 0
                raise

    def _validate_windows_ancestors(
        self,
        paths: tuple[Path, Path],
        identities: tuple[_DirectoryIdentity, ...],
    ) -> None:
        with self._lock:
            if self._windows_ancestor_close_failed:
                raise RuntimeError("storage authority close retry is pending")
            self._validate_windows_ancestors_unlocked(paths, identities)

    def _validate_windows_ancestors_unlocked(
        self,
        paths: tuple[Path, Path],
        identities: tuple[_DirectoryIdentity, ...],
    ) -> None:
        if (
            self._windows_ancestor_users < 1
            or self._windows_ancestor_paths != paths
            or self._windows_ancestor_identities != identities
            or len(self._windows_ancestor_handles) != len(identities)
        ):
            raise RuntimeError("storage authority identity changed")
        for handle, identity in zip(
            self._windows_ancestor_handles, identities, strict=True
        ):
            _validate_windows_identity(
                _windows_handle_identity(handle),
                (identity.device, identity.inode),
            )

    def _release_windows_ancestors(self) -> None:
        with self._lock:
            if self._windows_ancestor_users < 1:
                return
            if self._windows_ancestor_users > 1:
                self._windows_ancestor_users -= 1
                return
            first_error: OSError | None = None
            remaining: list[int] = []
            for handle in reversed(self._windows_ancestor_handles):
                try:
                    _windows_close_handle(handle)
                except OSError as exc:
                    remaining.append(handle)
                    if first_error is None:
                        first_error = exc
            if first_error is not None:
                self._windows_ancestor_handles = list(reversed(remaining))
                self._windows_ancestor_close_failed = True
                raise first_error
            self._windows_ancestor_handles = []
            self._windows_ancestor_paths = None
            self._windows_ancestor_identities = None
            self._windows_ancestor_users = 0
            self._windows_ancestor_close_failed = False


class _DesktopStorageAuthorityLease:
    def __init__(
        self,
        factory: DesktopStorageAuthorityFactory,
        profile_root: Path,
        root: Path,
    ) -> None:
        self._factory = factory
        self._profile_root = Path(profile_root)
        self._root = Path(root)
        self._generation_id = self._validate_textual_root()
        paths, identities = self._validated_paths()
        self._paths = paths
        self._identities = identities
        self._windows_handles: list[int] = []
        self._windows_ancestors_acquired = False
        self._posix_descriptors: list[int] = []
        self._operational_root = self._root
        try:
            if sys.platform == "win32":
                self._factory._acquire_windows_ancestors(paths[:2], identities[:2])
                self._windows_ancestors_acquired = True
                self._windows_handles = [_windows_open_directory(paths[-1])]
            else:
                self._posix_descriptors = [
                    _posix_open_directory(path) for path in paths
                ]
                self._operational_root = _posix_descriptor_root(
                    self._posix_descriptors[-1], self._identities[-1]
                )
            self.validate()
        except Exception:
            try:
                self.close()
            except OSError:
                pass
            raise

    @property
    def root(self) -> Path:
        """Return the retained operational root used by every storage owner."""

        return self._operational_root

    def validate(self) -> None:
        if (
            not self._windows_handles
            and not self._windows_ancestors_acquired
            and not self._posix_descriptors
        ):
            raise RuntimeError("storage authority is closed")
        paths, identities = self._validated_paths()
        if paths != self._paths or identities != self._identities:
            raise RuntimeError("storage authority identity changed")
        if self._windows_handles:
            if not self._windows_ancestors_acquired:
                raise RuntimeError("storage authority identity changed")
            self._factory._validate_windows_ancestors(paths[:2], identities[:2])
            _validate_windows_identity(
                _windows_handle_identity(self._windows_handles[0]),
                (self._identities[-1].device, self._identities[-1].inode),
            )
        else:
            for descriptor, identity in zip(
                self._posix_descriptors, self._identities, strict=True
            ):
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or _is_link_or_reparse(opened)
                    or opened.st_dev != identity.device
                    or opened.st_ino != identity.inode
                ):
                    raise RuntimeError("storage authority identity changed")
            if (
                _posix_descriptor_root(
                    self._posix_descriptors[-1], self._identities[-1]
                )
                != self._operational_root
            ):
                raise RuntimeError("storage authority identity changed")

    def close(self) -> None:
        first_error: OSError | None = None
        remaining_handles: list[int] = []
        for handle in reversed(self._windows_handles):
            try:
                _windows_close_handle(handle)
            except OSError as exc:
                remaining_handles.append(handle)
                if first_error is None:
                    first_error = exc
        self._windows_handles = list(reversed(remaining_handles))
        if not self._windows_handles and self._windows_ancestors_acquired:
            try:
                self._factory._release_windows_ancestors()
                self._windows_ancestors_acquired = False
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        remaining_descriptors: list[int] = []
        for descriptor in reversed(self._posix_descriptors):
            try:
                os.close(descriptor)
            except OSError as exc:
                remaining_descriptors.append(descriptor)
                if first_error is None:
                    first_error = exc
        self._posix_descriptors = list(reversed(remaining_descriptors))
        if first_error is not None:
            raise first_error

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _validate_textual_root(self) -> str:
        profile_parts = tuple(self._profile_root.parts)
        root_parts = tuple(self._root.parts)
        if (
            len(root_parts) != len(profile_parts) + 2
            or root_parts[: len(profile_parts)] != profile_parts
            or root_parts[-2] != "generation-storage"
            or not _is_canonical_generation_id(root_parts[-1])
        ):
            raise ValueError("unsafe Desktop storage authority")
        return root_parts[-1]

    def _validated_paths(
        self,
    ) -> tuple[tuple[Path, Path, Path], tuple[_DirectoryIdentity, ...]]:
        if self._validate_textual_root() != self._generation_id:
            raise RuntimeError("storage authority path changed")
        profile = self._profile_root
        collection = _exact_directory_child(profile, "generation-storage")
        generation = _exact_directory_child(collection, self._generation_id)
        paths = (profile, collection, generation)
        if tuple(generation.parts) != tuple(self._root.parts):
            raise RuntimeError("storage authority path changed")
        identities = tuple(_directory_identity(path) for path in paths)
        return paths, identities


def _is_canonical_generation_id(value: str) -> bool:
    return (
        1 <= len(value) <= 128
        and value[0] != "-"
        and value[-1] != "-"
        and "--" not in value
        and all(character in _GENERATION_ID_CHARACTERS for character in value)
        and value not in _WINDOWS_RESERVED_GENERATION_IDS
    )


def _is_link_or_reparse(info: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _directory_identity(path: Path) -> _DirectoryIdentity:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ValueError("unsafe Desktop storage authority") from exc
    if not stat.S_ISDIR(info.st_mode) or _is_link_or_reparse(info):
        raise ValueError("unsafe Desktop storage authority")
    return _DirectoryIdentity(device=info.st_dev, inode=info.st_ino)


def _exact_directory_child(parent: Path, name: str) -> Path:
    _directory_identity(parent)
    try:
        with os.scandir(parent) as entries:
            exact = any(entry.name == name for entry in entries)
    except OSError as exc:
        raise ValueError("unsafe Desktop storage authority") from exc
    candidate = parent / name
    if not exact:
        try:
            os.lstat(candidate)
        except FileNotFoundError:
            raise ValueError("unsafe Desktop storage authority") from None
        except OSError as exc:
            raise ValueError("unsafe Desktop storage authority") from exc
        raise ValueError("unsafe Desktop storage authority alias")
    _directory_identity(candidate)
    return candidate


def _posix_open_directory(path: Path) -> int:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    return os.open(path, flags)


def _posix_descriptor_root(descriptor: int, identity: _DirectoryIdentity) -> Path:
    """Expose one directory descriptor as a stable descendant-operation root."""

    candidates = [Path("/proc/self/fd") / str(descriptor)]
    if sys.platform == "darwin":
        candidates.insert(0, Path("/dev/fd") / str(descriptor))
    for candidate in candidates:
        try:
            opened = os.stat(candidate)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or opened.st_dev != identity.device
                or opened.st_ino != identity.inode
            ):
                continue
            with os.scandir(candidate):
                pass
        except OSError:
            continue
        return candidate
    raise RuntimeError("POSIX retained storage authority is unsupported")


def _windows_open_directory(path: Path) -> int:
    import ctypes
    from ctypes import wintypes

    delete_access = 0x00010000
    file_read_attributes = 0x00000080
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    file_flag_open_reparse_point = 0x00200000
    invalid_handle = ctypes.c_void_p(-1).value

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        delete_access | file_read_attributes,
        file_share_read | file_share_write,
        None,
        open_existing,
        file_flag_backup_semantics | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def _windows_handle_identity(handle: int) -> tuple[int, int, int]:
    import ctypes
    from ctypes import wintypes

    file_attribute_directory = 0x00000010
    file_attribute_reparse_point = 0x00000400

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("file_attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial_number", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    information = _ByHandleFileInformation()
    if not get_information(wintypes.HANDLE(handle), ctypes.byref(information)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not information.file_attributes & file_attribute_directory or (
        information.file_attributes & file_attribute_reparse_point
    ):
        raise RuntimeError("storage authority is not a regular directory")
    file_index = (information.file_index_high << 32) | information.file_index_low
    return information.volume_serial_number, file_index, information.file_attributes


def _validate_windows_identity(
    handle_identity: tuple[int, int, int], path_identity: tuple[int, int]
) -> None:
    _volume, file_index, _attributes = handle_identity
    _device, inode = path_identity
    if inode and file_index != inode:
        raise RuntimeError("storage authority identity changed")


def _windows_close_handle(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    if not close_handle(wintypes.HANDLE(handle)):
        raise ctypes.WinError(ctypes.get_last_error())
