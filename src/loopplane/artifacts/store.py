"""Artifact Storage: oversized tool output preserved in full as sidecar
files, retrievable by a stable reference after the run (contracts/artifacts.md;
FR-090, FR-091, FR-093).
"""

from __future__ import annotations

import json
import os
import stat
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loopplane.context import RunContext
from loopplane.gateway.gateway import ArtifactHandoff
from loopplane.model.boundary import ToolCallRequest
from loopplane.model.content import OutputBlock, TextBlock

_ARTIFACT_DIR = "artifacts"
_DELETION_DIR = ".d"


@dataclass(frozen=True)
class ArtifactSessionDeletion:
    original: Path
    staged: Path


@dataclass(frozen=True)
class ArtifactMeta:
    reference: str
    session_id: str
    call_id: str
    size: int
    media_kind: Literal["text", "image", "binary"]
    created_at: datetime


class ArtifactStore:
    def __init__(
        self,
        base_dir: Path,
        *,
        preview_chars: int = 1024,
        validate_root: Callable[[], None] | None = None,
    ) -> None:
        self._base = base_dir
        self._preview_chars = preview_chars
        self._validate_root = validate_root

    def _require_root(self) -> None:
        if self._validate_root is not None:
            self._validate_root()

    def _directory(self, session_id: str) -> Path:
        self._require_root()
        return self._base / session_id / _ARTIFACT_DIR

    async def offload(
        self, *, session_id: str, call_id: str, outputs: Sequence[OutputBlock]
    ) -> tuple[str, str]:
        """Persist the full content; return (stable reference, bounded
        preview) for the in-conversation representation (FR-090, FR-091).
        """
        content = "\n".join(
            block.text for block in outputs if isinstance(block, TextBlock)
        )
        data = content.encode("utf-8")
        reference = uuid.uuid4().hex
        directory = self._directory(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{reference}.txt").write_bytes(data)
        metadata = {
            "reference": reference,
            "session_id": session_id,
            "call_id": call_id,
            "size": len(data),
            "media_kind": "text",
            "created_at": datetime.now(UTC).isoformat(),
        }
        (directory / f"{reference}.meta.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        preview = content[: self._preview_chars]
        if len(content) > self._preview_chars:
            preview += (
                f"\n[preview only: the full {len(data)}-byte output is stored "
                f"as artifact {reference}]"
            )
        return reference, preview

    def retrieve(self, session_id: str, reference: str) -> str | None:
        """Content by reference; unknown references are a normal not-found,
        never a crash (FR-093).
        """
        path = self._directory(session_id) / f"{reference}.txt"
        if not path.is_file():
            return None
        return path.read_bytes().decode("utf-8")

    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None:
        path = self._directory(session_id) / f"{reference}.meta.json"
        if not path.is_file():
            return None
        document = json.loads(path.read_text("utf-8"))
        return ArtifactMeta(
            reference=document["reference"],
            session_id=document["session_id"],
            call_id=document["call_id"],
            size=document["size"],
            media_kind=document["media_kind"],
            created_at=datetime.fromisoformat(document["created_at"]),
        )

    def validate_session_deletion(self, session_id: str) -> None:
        """Reject deletion unless the session tree is entirely store-owned."""

        self._deletion_members(session_id)

    def prepare_session_deletion(
        self, session_id: str
    ) -> ArtifactSessionDeletion | None:
        """Atomically detach a validated tree before durable record deletion."""

        session_dir, _artifacts, _members = self._deletion_members(session_id)
        if session_dir is None:
            return None
        deletion_root = self._deletion_root()
        staged = deletion_root / uuid.uuid4().hex[:16]
        os.replace(session_dir, staged)
        try:
            try:
                self._validated_tree(staged)
            except FileNotFoundError:
                # Windows can briefly report a moved child as unavailable even
                # though the directory rename has completed. Reopen once; a
                # genuinely missing member still fails closed.
                self._validated_tree(staged)
        except Exception as exc:
            if session_dir.exists():
                raise RuntimeError("artifact deletion rollback blocked") from exc
            os.replace(staged, session_dir)
            raise
        return ArtifactSessionDeletion(original=session_dir, staged=staged)

    def rollback_session_deletion(self, deletion: ArtifactSessionDeletion) -> None:
        """Restore a detached tree when durable record deletion did not apply."""

        self._require_root()
        self._validated_tree(deletion.staged)
        if deletion.original.exists():
            raise RuntimeError("artifact deletion rollback blocked")
        os.replace(deletion.staged, deletion.original)
        self._remove_empty_deletion_root()

    def commit_session_deletion(self, deletion: ArtifactSessionDeletion) -> None:
        """Best-effort cleanup after durable record deletion has committed."""

        self._require_root()
        try:
            self._delete_validated_tree(deletion.staged)
        except (OSError, RuntimeError):
            # The active path is already detached. Never follow or delete a tree
            # that changed after preparation; leave it quarantined and keep the
            # checkpoint deletion authoritative.
            return
        self._remove_empty_deletion_root()

    def delete_session(self, session_id: str) -> None:
        """Delete one store-owned session tree without following links."""

        deletion = self.prepare_session_deletion(session_id)
        if deletion is not None:
            self.commit_session_deletion(deletion)

    def _deletion_members(
        self, session_id: str
    ) -> tuple[Path | None, Path | None, list[Path]]:
        self._require_root()
        if not session_id or Path(session_id).name != session_id:
            raise ValueError("invalid artifact session")
        session_dir = self._base / session_id
        try:
            return self._validated_tree(session_dir)
        except FileNotFoundError:
            return None, None, []

    def _validated_tree(self, session_dir: Path) -> tuple[Path, Path, list[Path]]:
        session_info = os.lstat(session_dir)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(session_info.st_mode) or (
            getattr(session_info, "st_file_attributes", 0) & reparse
        ):
            raise RuntimeError("artifact session layout invalid")
        artifacts = session_dir / _ARTIFACT_DIR
        children = list(session_dir.iterdir())
        if children != [artifacts]:
            raise RuntimeError("artifact session layout invalid")
        artifact_info = os.lstat(artifacts)
        if not stat.S_ISDIR(artifact_info.st_mode) or (
            getattr(artifact_info, "st_file_attributes", 0) & reparse
        ):
            raise RuntimeError("artifact session layout invalid")
        members = list(artifacts.iterdir())
        for member in members:
            info = os.lstat(member)
            if not stat.S_ISREG(info.st_mode) or (
                getattr(info, "st_file_attributes", 0) & reparse
            ):
                raise RuntimeError("artifact session layout invalid")
        return session_dir, artifacts, members

    def _delete_validated_tree(self, session_dir: Path) -> None:
        if os.name == "nt":
            _delete_tree_anchored_windows(session_dir)
        else:
            _delete_tree_anchored_posix(session_dir)

    def _deletion_root(self) -> Path:
        self._require_root()
        root = self._base / _DELETION_DIR
        try:
            os.mkdir(root, 0o700)
        except FileExistsError:
            pass
        info = os.lstat(root)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & reparse
        ):
            raise RuntimeError("artifact deletion quarantine invalid")
        return root

    def _remove_empty_deletion_root(self) -> None:
        self._require_root()
        root = self._base / _DELETION_DIR
        try:
            root.rmdir()
        except (FileNotFoundError, OSError):
            pass


def _delete_tree_anchored_posix(session_dir: Path) -> None:
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    parent_fd = os.open(session_dir.parent, directory_flags)
    session_fd = -1
    artifacts_fd = -1
    try:
        session_fd = os.open(session_dir.name, directory_flags, dir_fd=parent_fd)
        if not stat.S_ISDIR(os.fstat(session_fd).st_mode) or os.listdir(session_fd) != [
            _ARTIFACT_DIR
        ]:
            raise RuntimeError("artifact session layout invalid")
        artifacts_fd = os.open(
            _ARTIFACT_DIR,
            directory_flags,
            dir_fd=session_fd,
        )
        if not stat.S_ISDIR(os.fstat(artifacts_fd).st_mode):
            raise RuntimeError("artifact session layout invalid")
        members = os.listdir(artifacts_fd)
        for member in members:
            info = os.stat(member, dir_fd=artifacts_fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise RuntimeError("artifact session layout invalid")
        for member in members:
            os.unlink(member, dir_fd=artifacts_fd)
        os.rmdir(_ARTIFACT_DIR, dir_fd=session_fd)
        os.rmdir(session_dir.name, dir_fd=parent_fd)
    finally:
        if artifacts_fd >= 0:
            os.close(artifacts_fd)
        if session_fd >= 0:
            os.close(session_fd)
        os.close(parent_fd)


def _delete_tree_anchored_windows(session_dir: Path) -> None:
    import ctypes
    from ctypes import wintypes

    delete_access = 0x00010000
    file_read_attributes = 0x00000080
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    file_flag_open_reparse_point = 0x00200000
    file_attribute_directory = 0x00000010
    file_attribute_reparse_point = 0x00000400
    file_disposition_info = 4
    invalid_handle = ctypes.c_void_p(-1).value

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

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOL)]

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
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    def open_directory(path: Path) -> int:
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
        information = _ByHandleFileInformation()
        if not get_information(handle, ctypes.byref(information)):
            error = ctypes.WinError(ctypes.get_last_error())
            close_handle(handle)
            raise error
        if not (information.file_attributes & file_attribute_directory) or (
            information.file_attributes & file_attribute_reparse_point
        ):
            close_handle(handle)
            raise RuntimeError("artifact session layout invalid")
        return int(handle)

    def mark_delete(handle: int) -> None:
        disposition = _FileDispositionInfo(True)
        if not set_information(
            handle,
            file_disposition_info,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    parent_handle = open_directory(session_dir.parent)
    session_handle: int | None = None
    artifacts_handle: int | None = None
    try:
        session_handle = open_directory(session_dir)
        artifacts = session_dir / _ARTIFACT_DIR
        if list(session_dir.iterdir()) != [artifacts]:
            raise RuntimeError("artifact session layout invalid")
        artifacts_handle = open_directory(artifacts)
        members = list(artifacts.iterdir())
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        for member in members:
            info = os.lstat(member)
            if not stat.S_ISREG(info.st_mode) or (
                getattr(info, "st_file_attributes", 0) & reparse
            ):
                raise RuntimeError("artifact session layout invalid")
        for member in members:
            os.unlink(member)
        if any(artifacts.iterdir()):
            raise RuntimeError("artifact session layout changed")
        mark_delete(artifacts_handle)
        close_handle(artifacts_handle)
        artifacts_handle = None
        if any(session_dir.iterdir()):
            raise RuntimeError("artifact session layout changed")
        mark_delete(session_handle)
        close_handle(session_handle)
        session_handle = None
    finally:
        if artifacts_handle is not None:
            close_handle(artifacts_handle)
        if session_handle is not None:
            close_handle(session_handle)
        close_handle(parent_handle)


def make_artifact_handoff(store: ArtifactStore) -> ArtifactHandoff:
    """Bind an ArtifactStore as the Gateway's offload seam (FR-090)."""

    async def handoff(
        call: ToolCallRequest, outputs: list[OutputBlock], context: RunContext
    ) -> tuple[str, str]:
        return await store.offload(
            session_id=context.session_id, call_id=call.call_id, outputs=outputs
        )

    return handoff
