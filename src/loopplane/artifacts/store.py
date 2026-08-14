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
from typing import Any, Literal, cast

from loopplane.context import RunContext
from loopplane.gateway.gateway import ArtifactHandoff
from loopplane.model.boundary import ToolCallRequest
from loopplane.model.content import OutputBlock, TextBlock

_ARTIFACT_DIR = "artifacts"
_DELETION_DIR = ".d"


def _windows_ctypes() -> Any:
    import ctypes

    return cast(Any, ctypes)


class _DirectoryAnchor:
    def __init__(
        self,
        path: Path,
        *,
        movable: bool = False,
        protect_rename: bool = False,
    ) -> None:
        self.path = path
        self.identity = _directory_identity(path)
        self._descriptor: int | None = None
        self._handle: int | None = None
        if os.name == "nt":
            self._handle = _windows_open_directory_anchor(
                path,
                movable=movable,
                protect_rename=protect_rename,
            )
        else:
            self._descriptor = _posix_open_directory_anchor(path)
            opened = os.fstat(self._descriptor)
            if (opened.st_dev, opened.st_ino) != self.identity:
                self.close()
                raise RuntimeError("artifact session layout changed")

    def close(self) -> None:
        first_error: OSError | None = None
        if self._handle is not None:
            try:
                _windows_close_directory_anchor(self._handle)
                self._handle = None
            except OSError as exc:
                first_error = exc
        if self._descriptor is not None:
            try:
                os.close(self._descriptor)
                self._descriptor = None
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


@dataclass(frozen=True)
class ArtifactSessionDeletion:
    original: Path
    staged: Path
    shared_session_directory: bool
    original_parent_anchor: _DirectoryAnchor
    quarantine_root_anchor: _DirectoryAnchor
    staged_parent_anchor: _DirectoryAnchor
    detached_anchor: _DirectoryAnchor
    artifacts_anchor: _DirectoryAnchor
    member_identities: tuple[tuple[str, tuple[int, int]], ...]
    member_descriptors: tuple[int, ...]
    member_handles: tuple[int, ...] = ()
    rollback_applied: bool = False
    rollback_original_pending: bool = False
    members_delete_pending: bool = False
    artifacts_delete_pending: bool = False
    session_delete_pending: bool = False
    rollback_required: bool = False
    rollback_completed: bool = False
    erased: bool = False
    posix_members_pending: tuple[tuple[str, tuple[int, int], bool], ...] = ()
    posix_artifacts_cleanup_name: str | None = None
    posix_session_cleanup_name: str | None = None

    @property
    def shared_parent_anchor(self) -> _DirectoryAnchor | None:
        return self.original_parent_anchor if self.shared_session_directory else None

    @property
    def has_retained_authority(self) -> bool:
        anchors = (
            self.original_parent_anchor,
            self.quarantine_root_anchor,
            self.staged_parent_anchor,
            self.detached_anchor,
            self.artifacts_anchor,
        )
        return bool(
            self.member_descriptors
            or self.member_handles
            or self.members_delete_pending
            or self.artifacts_delete_pending
            or self.session_delete_pending
            or self.posix_members_pending
            or self.posix_artifacts_cleanup_name is not None
            or self.posix_session_cleanup_name is not None
        ) or any(
            anchor._handle is not None or anchor._descriptor is not None
            for anchor in anchors
        )


@dataclass
class _PendingArtifactAuthorityCleanup:
    member_descriptors: tuple[int, ...]
    anchors: tuple[_DirectoryAnchor, ...]
    rollback: ArtifactSessionDeletion | None = None

    @property
    def has_retained_authority(self) -> bool:
        return (
            self.rollback is not None
            or bool(self.member_descriptors)
            or any(
                anchor._handle is not None or anchor._descriptor is not None
                for anchor in self.anchors
            )
        )


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
        self._pending_authority_cleanups: list[_PendingArtifactAuthorityCleanup] = []

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
        try:
            return path.read_bytes().decode("utf-8")
        except FileNotFoundError:
            return None

    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None:
        path = self._directory(session_id) / f"{reference}.meta.json"
        try:
            document = json.loads(path.read_text("utf-8"))
        except FileNotFoundError:
            return None
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
        """Atomically detach validated artifacts before record deletion."""

        self.retry_pending_authority_cleanups()
        session_dir, artifacts, members = self._deletion_members(session_id)
        if session_dir is None or artifacts is None:
            return None
        deletion_root = self._deletion_root()
        staged = deletion_root / uuid.uuid4().hex[:16]
        shared_session_directory = (session_dir / "records.jsonl").is_file()
        member_identities = tuple(
            sorted((member.name, _file_identity(member)) for member in members)
        )
        member_descriptors: tuple[int, ...] = ()
        original_parent_anchor: _DirectoryAnchor | None = None
        quarantine_root_anchor: _DirectoryAnchor | None = None
        staged_parent_anchor: _DirectoryAnchor | None = None
        detached_anchor: _DirectoryAnchor | None = None
        artifacts_anchor: _DirectoryAnchor | None = None
        moved = False
        try:
            quarantine_root_anchor = _DirectoryAnchor(
                deletion_root, protect_rename=True
            )
            if shared_session_directory:
                original_parent_anchor = _DirectoryAnchor(
                    session_dir, protect_rename=True
                )
                detached_anchor = _DirectoryAnchor(artifacts, movable=True)
                artifacts_anchor = detached_anchor
                staged.mkdir()
                staged_parent_anchor = _DirectoryAnchor(staged, movable=True)
                self._move_anchored_directory(
                    source_name=_ARTIFACT_DIR,
                    source_parent=original_parent_anchor,
                    destination_name=_ARTIFACT_DIR,
                    destination_parent=staged_parent_anchor,
                    moved_directory=detached_anchor,
                )
                detached_anchor.path = staged / _ARTIFACT_DIR
                moved = True
            else:
                original_parent_anchor = _DirectoryAnchor(session_dir.parent)
                detached_anchor = _DirectoryAnchor(session_dir, movable=True)
                self._move_anchored_directory(
                    source_name=session_dir.name,
                    source_parent=original_parent_anchor,
                    destination_name=staged.name,
                    destination_parent=quarantine_root_anchor,
                    moved_directory=detached_anchor,
                )
                detached_anchor.path = staged
                moved = True
                staged_parent_anchor = detached_anchor
                artifacts_anchor = _DirectoryAnchor(
                    staged / _ARTIFACT_DIR, movable=True
                )

            assert staged_parent_anchor is not None
            assert artifacts_anchor is not None
            self._validate_staged_tree(
                staged,
                expected_session_identity=staged_parent_anchor.identity,
                expected_artifacts_identity=artifacts_anchor.identity,
                expected_members=member_identities,
            )
            if os.name != "nt":
                member_descriptors = _posix_open_artifact_members(
                    artifacts_anchor,
                    member_identities,
                )
        except Exception as exc:
            rollback_error: Exception | None = None
            try:
                if moved:
                    assert original_parent_anchor is not None
                    assert quarantine_root_anchor is not None
                    assert detached_anchor is not None
                    if shared_session_directory:
                        assert staged_parent_anchor is not None
                        self._move_anchored_directory(
                            source_name=_ARTIFACT_DIR,
                            source_parent=staged_parent_anchor,
                            destination_name=_ARTIFACT_DIR,
                            destination_parent=original_parent_anchor,
                            moved_directory=detached_anchor,
                        )
                    else:
                        self._move_anchored_directory(
                            source_name=staged.name,
                            source_parent=quarantine_root_anchor,
                            destination_name=session_dir.name,
                            destination_parent=original_parent_anchor,
                            moved_directory=detached_anchor,
                        )
            except Exception as rollback_exc:
                rollback_error = rollback_exc
            finally:
                # A failure while acquiring the anchors leaves some of them
                # unset, so the retained-authority record below cannot be built.
                # The close-everything branch already tolerates the gaps, and
                # `rollback_error` still surfaces the failure to the caller.
                if (
                    rollback_error is not None
                    and moved
                    and original_parent_anchor is not None
                    and quarantine_root_anchor is not None
                    and staged_parent_anchor is not None
                    and detached_anchor is not None
                    and artifacts_anchor is not None
                ):
                    cleanup = _PendingArtifactAuthorityCleanup(
                        member_descriptors=(),
                        anchors=(),
                        rollback=ArtifactSessionDeletion(
                            original=(
                                artifacts if shared_session_directory else session_dir
                            ),
                            staged=staged,
                            shared_session_directory=shared_session_directory,
                            original_parent_anchor=original_parent_anchor,
                            quarantine_root_anchor=quarantine_root_anchor,
                            staged_parent_anchor=staged_parent_anchor,
                            detached_anchor=detached_anchor,
                            artifacts_anchor=artifacts_anchor,
                            member_identities=member_identities,
                            member_descriptors=member_descriptors,
                            rollback_required=True,
                        ),
                    )
                    self._pending_authority_cleanups.append(cleanup)
                    member_descriptors = ()
                else:
                    seen: set[int] = set()
                    anchors: list[_DirectoryAnchor] = []
                    for anchor in (
                        artifacts_anchor
                        if artifacts_anchor is not detached_anchor
                        else None,
                        detached_anchor,
                        staged_parent_anchor
                        if staged_parent_anchor is not detached_anchor
                        else None,
                        quarantine_root_anchor,
                        original_parent_anchor,
                    ):
                        if anchor is None or id(anchor) in seen:
                            continue
                        seen.add(id(anchor))
                        anchors.append(anchor)
                    cleanup = _PendingArtifactAuthorityCleanup(
                        member_descriptors=member_descriptors,
                        anchors=tuple(anchors),
                    )
                    try:
                        self._close_pending_authority_cleanup(cleanup)
                    except OSError as close_exc:
                        if cleanup.has_retained_authority:
                            self._pending_authority_cleanups.append(cleanup)
                        if rollback_error is None:
                            rollback_error = close_exc
                    member_descriptors = ()
            if shared_session_directory:
                try:
                    staged.rmdir()
                except OSError:
                    pass
            self._remove_empty_deletion_root()
            if rollback_error is not None:
                raise RuntimeError(
                    "artifact deletion rollback blocked"
                ) from rollback_error
            raise RuntimeError("artifact deletion prepare blocked") from exc

        assert original_parent_anchor is not None
        assert quarantine_root_anchor is not None
        assert staged_parent_anchor is not None
        assert detached_anchor is not None
        assert artifacts_anchor is not None
        return ArtifactSessionDeletion(
            original=artifacts if shared_session_directory else session_dir,
            staged=staged,
            shared_session_directory=shared_session_directory,
            original_parent_anchor=original_parent_anchor,
            quarantine_root_anchor=quarantine_root_anchor,
            staged_parent_anchor=staged_parent_anchor,
            detached_anchor=detached_anchor,
            artifacts_anchor=artifacts_anchor,
            member_identities=member_identities,
            member_descriptors=member_descriptors,
        )

    def rollback_session_deletion(self, deletion: ArtifactSessionDeletion) -> None:
        """Restore a detached tree when durable record deletion did not apply."""

        if deletion.rollback_applied or deletion.rollback_original_pending:
            if not _directory_path_matches_anchor(deletion.original_parent_anchor):
                raise RuntimeError("artifact deletion rollback blocked")
            destination_name = (
                _ARTIFACT_DIR
                if deletion.shared_session_directory
                else deletion.original.name
            )
            if not _anchored_name_matches(
                deletion.original_parent_anchor,
                destination_name,
                deletion.detached_anchor.identity,
            ):
                raise RuntimeError("artifact deletion rollback blocked")
            object.__setattr__(deletion, "rollback_completed", True)
            object.__setattr__(deletion, "rollback_applied", True)
            object.__setattr__(deletion, "rollback_original_pending", False)
            self._close_deletion_anchors(deletion)
            object.__setattr__(deletion, "rollback_required", False)
            self._remove_empty_deletion_root()
            return
        moved = False
        try:
            self._require_root()
            self._validate_deletion_paths(deletion)
            if not _directory_path_matches_anchor(deletion.original_parent_anchor):
                raise RuntimeError("artifact deletion rollback blocked")
            destination_name = (
                _ARTIFACT_DIR
                if deletion.shared_session_directory
                else deletion.original.name
            )
            if _anchored_name_exists(deletion.original_parent_anchor, destination_name):
                # A foreign object owns the destination name. Nothing has moved,
                # so the detached tree is still retained and a caller that clears
                # the obstruction can roll back again; releasing the authority
                # here would make that retry impossible. An unusable store is a
                # different case and still releases below.
                object.__setattr__(deletion, "rollback_required", True)
                raise RuntimeError("artifact deletion rollback blocked")
            if os.name == "nt" and not deletion.shared_session_directory:
                deletion.artifacts_anchor.close()
                deletion.detached_anchor.close()
            self._move_anchored_directory(
                source_name=(
                    _ARTIFACT_DIR
                    if deletion.shared_session_directory
                    else deletion.staged.name
                ),
                source_parent=(
                    deletion.staged_parent_anchor
                    if deletion.shared_session_directory
                    else deletion.quarantine_root_anchor
                ),
                destination_name=(
                    _ARTIFACT_DIR
                    if deletion.shared_session_directory
                    else deletion.original.name
                ),
                destination_parent=deletion.original_parent_anchor,
                moved_directory=deletion.detached_anchor,
            )
            moved = True
            if not _directory_path_matches_anchor(deletion.original_parent_anchor):
                raise RuntimeError("artifact deletion rollback blocked")
            if deletion.shared_session_directory:
                deletion.staged_parent_anchor.close()
                deletion.staged.rmdir()
            object.__setattr__(deletion, "rollback_completed", True)
            object.__setattr__(deletion, "rollback_applied", True)
        except Exception:
            if moved:
                compensation_error: Exception | None = None
                try:
                    self._move_anchored_directory(
                        source_name=(
                            _ARTIFACT_DIR
                            if deletion.shared_session_directory
                            else deletion.original.name
                        ),
                        source_parent=deletion.original_parent_anchor,
                        destination_name=(
                            _ARTIFACT_DIR
                            if deletion.shared_session_directory
                            else deletion.staged.name
                        ),
                        destination_parent=(
                            deletion.staged_parent_anchor
                            if deletion.shared_session_directory
                            else deletion.quarantine_root_anchor
                        ),
                        moved_directory=deletion.detached_anchor,
                    )
                except Exception as compensation_exc:
                    compensation_error = compensation_exc
                if compensation_error is not None:
                    object.__setattr__(
                        deletion,
                        "rollback_original_pending",
                        True,
                    )
                    raise RuntimeError(
                        "artifact deletion rollback compensation blocked"
                    ) from compensation_error
                raise
            if not deletion.rollback_required:
                self._close_deletion_anchors(deletion)
            raise
        self._close_deletion_anchors(deletion)
        object.__setattr__(deletion, "rollback_required", False)
        self._remove_empty_deletion_root()

    def commit_session_deletion(self, deletion: ArtifactSessionDeletion) -> None:
        """Erase retained artifacts and release deletion authority."""

        try:
            self._require_root()
        except Exception:
            self._close_deletion_anchors(deletion)
            raise
        if not deletion.erased:
            self._delete_anchored_tree(deletion)
            object.__setattr__(deletion, "erased", True)
        if os.name != "nt":
            self._remove_erased_posix_tree(deletion)
        self._close_deletion_anchors(deletion)
        self._remove_empty_deletion_root()

    def retry_session_deletion(self, deletion: ArtifactSessionDeletion) -> None:
        """Retry retained rollback or post-checkpoint artifact erasure."""

        if deletion.rollback_required:
            if deletion.rollback_completed:
                self._close_deletion_anchors(deletion)
                object.__setattr__(deletion, "rollback_required", False)
                self._remove_empty_deletion_root()
            else:
                self.rollback_session_deletion(deletion)
            return
        self.commit_session_deletion(deletion)

    def retry_pending_authority_cleanups(self) -> None:
        """Release retained authority from failed prepare cleanup."""

        had_pending_cleanup = bool(self._pending_authority_cleanups)
        while self._pending_authority_cleanups:
            cleanup = self._pending_authority_cleanups[0]
            if cleanup.rollback is not None:
                self.rollback_session_deletion(cleanup.rollback)
                cleanup.rollback = None
            self._close_pending_authority_cleanup(cleanup)
            self._pending_authority_cleanups.pop(0)
        if had_pending_cleanup:
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
            session_info = os.lstat(session_dir)
        except FileNotFoundError:
            return None, None, []
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(session_info.st_mode) or (
            getattr(session_info, "st_file_attributes", 0) & reparse
        ):
            raise RuntimeError("artifact session layout invalid")
        artifacts = session_dir / _ARTIFACT_DIR
        try:
            artifact_info = os.lstat(artifacts)
        except FileNotFoundError:
            children = list(session_dir.iterdir())
            if not children:
                return session_dir, None, []
            if all(child.name == "records.jsonl" for child in children):
                for child in children:
                    info = os.lstat(child)
                    if not stat.S_ISREG(info.st_mode) or (
                        getattr(info, "st_file_attributes", 0) & reparse
                    ):
                        raise RuntimeError("artifact session layout invalid") from None
                return session_dir, None, []
            raise RuntimeError("artifact session layout invalid") from None
        if not stat.S_ISDIR(artifact_info.st_mode) or (
            getattr(artifact_info, "st_file_attributes", 0) & reparse
        ):
            raise RuntimeError("artifact session layout invalid")
        children = list(session_dir.iterdir())
        allowed_children = {artifacts, session_dir / "records.jsonl"}
        if any(child not in allowed_children for child in children):
            raise RuntimeError("artifact session layout invalid")
        records = session_dir / "records.jsonl"
        if records in children:
            records_info = os.lstat(records)
            if not stat.S_ISREG(records_info.st_mode) or (
                getattr(records_info, "st_file_attributes", 0) & reparse
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

    def _move_anchored_directory(
        self,
        *,
        source_name: str,
        source_parent: _DirectoryAnchor,
        destination_name: str,
        destination_parent: _DirectoryAnchor,
        moved_directory: _DirectoryAnchor,
    ) -> None:
        if os.name == "nt":
            if (
                _directory_identity(source_parent.path) != source_parent.identity
                or _directory_identity(destination_parent.path)
                != destination_parent.identity
                or _directory_identity(source_parent.path / source_name)
                != moved_directory.identity
            ):
                raise RuntimeError("artifact deletion authority changed")
            os.replace(
                source_parent.path / source_name,
                destination_parent.path / destination_name,
            )
            if (
                _directory_identity(source_parent.path) != source_parent.identity
                or _directory_identity(destination_parent.path)
                != destination_parent.identity
                or _directory_identity(destination_parent.path / destination_name)
                != moved_directory.identity
            ):
                raise RuntimeError("artifact deletion authority changed")
            return

        assert source_parent._descriptor is not None
        assert destination_parent._descriptor is not None
        info = os.stat(
            source_name,
            dir_fd=source_parent._descriptor,
            follow_symlinks=False,
        )
        if (info.st_dev, info.st_ino) != moved_directory.identity:
            raise RuntimeError("artifact deletion authority changed")
        _posix_rename_noreplace(
            source_name=source_name,
            destination_name=destination_name,
            source_parent_descriptor=source_parent._descriptor,
            destination_parent_descriptor=destination_parent._descriptor,
        )
        # renameat2 resolves the source name in the kernel, so a replacement
        # installed after the check above would be moved instead of the validated
        # directory. Re-prove the identity at the destination, as the Windows
        # branch already does.
        moved = os.stat(
            destination_name,
            dir_fd=destination_parent._descriptor,
            follow_symlinks=False,
        )
        if (moved.st_dev, moved.st_ino) != moved_directory.identity:
            raise RuntimeError("artifact deletion authority changed")

    def _delete_anchored_tree(self, deletion: ArtifactSessionDeletion) -> None:
        if os.name == "nt":
            _delete_tree_anchored_windows(deletion)
            return
        _erase_tree_anchored_posix(
            deletion.staged_parent_anchor,
            deletion.artifacts_anchor,
            member_identities=deletion.member_identities,
            member_descriptors=deletion.member_descriptors,
        )

    @staticmethod
    def _validate_staged_tree(
        staged: Path,
        *,
        expected_session_identity: tuple[int, int],
        expected_artifacts_identity: tuple[int, int],
        expected_members: tuple[tuple[str, tuple[int, int]], ...],
    ) -> None:
        if _directory_identity(staged) != expected_session_identity:
            raise RuntimeError("artifact deletion authority changed")
        artifacts = staged / _ARTIFACT_DIR
        if _directory_identity(artifacts) != expected_artifacts_identity:
            raise RuntimeError("artifact deletion authority changed")
        members = tuple(
            sorted(
                (member.name, _file_identity(member)) for member in artifacts.iterdir()
            )
        )
        if members != expected_members:
            raise RuntimeError("artifact deletion authority changed")

    @classmethod
    def _validate_deletion_paths(cls, deletion: ArtifactSessionDeletion) -> None:
        cls._validate_staged_tree(
            deletion.staged,
            expected_session_identity=deletion.staged_parent_anchor.identity,
            expected_artifacts_identity=deletion.artifacts_anchor.identity,
            expected_members=deletion.member_identities,
        )

    def _remove_erased_posix_tree(self, deletion: ArtifactSessionDeletion) -> None:
        if not deletion.erased:
            raise RuntimeError("artifact deletion authority changed")
        staged_anchor = deletion.staged_parent_anchor
        artifacts_anchor = deletion.artifacts_anchor
        if staged_anchor._descriptor is None and artifacts_anchor._descriptor is None:
            # A retry after a pass that removed the tree and then failed while
            # releasing authority. The anchors are already closed, so redoing the
            # removal would assert on them; the only work left is that release.
            if (
                not deletion.posix_members_pending
                and deletion.posix_artifacts_cleanup_name is None
                and deletion.posix_session_cleanup_name is None
            ):
                return
            raise RuntimeError("artifact deletion authority changed")
        assert staged_anchor._descriptor is not None
        assert artifacts_anchor._descriptor is not None
        if not deletion.posix_members_pending:
            pending = tuple(
                (name, identity, False) for name, identity in deletion.member_identities
            )
            object.__setattr__(deletion, "posix_members_pending", pending)
        while deletion.posix_members_pending:
            name, identity, quarantined = deletion.posix_members_pending[0]
            cleanup_name = name
            if not quarantined:
                cleanup_name = f".erase-{uuid.uuid4().hex}"
                _posix_rename_exact_entry(
                    source_name=name,
                    destination_name=cleanup_name,
                    parent_anchor=artifacts_anchor,
                    expected_identity=identity,
                )
                pending = (
                    (cleanup_name, identity, True),
                    *deletion.posix_members_pending[1:],
                )
                object.__setattr__(deletion, "posix_members_pending", pending)
            _posix_unlink_exact_entry(
                name=cleanup_name,
                parent_anchor=artifacts_anchor,
                expected_identity=identity,
            )
            object.__setattr__(
                deletion,
                "posix_members_pending",
                deletion.posix_members_pending[1:],
            )
        if deletion.posix_artifacts_cleanup_name is None:
            artifacts_cleanup = f".erase-{uuid.uuid4().hex}"
            _posix_rename_exact_entry(
                source_name=_ARTIFACT_DIR,
                destination_name=artifacts_cleanup,
                parent_anchor=staged_anchor,
                expected_identity=artifacts_anchor.identity,
            )
            object.__setattr__(
                deletion,
                "posix_artifacts_cleanup_name",
                artifacts_cleanup,
            )
        current_artifacts_cleanup = deletion.posix_artifacts_cleanup_name
        assert current_artifacts_cleanup is not None
        _posix_unlink_exact_entry(
            name=current_artifacts_cleanup,
            parent_anchor=staged_anchor,
            expected_identity=artifacts_anchor.identity,
            directory=True,
        )
        object.__setattr__(deletion, "posix_artifacts_cleanup_name", None)
        quarantine_anchor = deletion.quarantine_root_anchor
        assert quarantine_anchor._descriptor is not None
        if deletion.posix_session_cleanup_name is None:
            session_cleanup = f".erase-{uuid.uuid4().hex}"
            _posix_rename_exact_entry(
                source_name=deletion.staged.name,
                destination_name=session_cleanup,
                parent_anchor=quarantine_anchor,
                expected_identity=staged_anchor.identity,
            )
            object.__setattr__(
                deletion,
                "posix_session_cleanup_name",
                session_cleanup,
            )
        current_session_cleanup = deletion.posix_session_cleanup_name
        assert current_session_cleanup is not None
        _posix_unlink_exact_entry(
            name=current_session_cleanup,
            parent_anchor=quarantine_anchor,
            expected_identity=staged_anchor.identity,
            directory=True,
        )
        object.__setattr__(deletion, "posix_session_cleanup_name", None)

    @staticmethod
    def _close_pending_authority_cleanup(
        cleanup: _PendingArtifactAuthorityCleanup,
    ) -> None:
        first_error: OSError | None = None
        remaining_descriptors: list[int] = []
        for descriptor in reversed(cleanup.member_descriptors):
            try:
                os.close(descriptor)
            except OSError as exc:
                remaining_descriptors.append(descriptor)
                if first_error is None:
                    first_error = exc
        cleanup.member_descriptors = tuple(reversed(remaining_descriptors))
        for anchor in cleanup.anchors:
            try:
                anchor.close()
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    @staticmethod
    def _close_deletion_anchors(deletion: ArtifactSessionDeletion) -> None:
        first_error: OSError | None = None
        remaining_handles: list[int] = []
        for handle in reversed(deletion.member_handles):
            try:
                _windows_close_directory_anchor(handle)
            except OSError as exc:
                remaining_handles.append(handle)
                if first_error is None:
                    first_error = exc
        object.__setattr__(
            deletion,
            "member_handles",
            tuple(reversed(remaining_handles)),
        )
        remaining_descriptors: list[int] = []
        for descriptor in reversed(deletion.member_descriptors):
            try:
                os.close(descriptor)
            except OSError as exc:
                remaining_descriptors.append(descriptor)
                if first_error is None:
                    first_error = exc
        object.__setattr__(
            deletion,
            "member_descriptors",
            tuple(reversed(remaining_descriptors)),
        )
        seen: set[int] = set()
        anchors = (
            deletion.artifacts_anchor,
            deletion.detached_anchor,
            deletion.staged_parent_anchor,
            deletion.quarantine_root_anchor,
            deletion.original_parent_anchor,
        )
        for anchor in anchors:
            if anchor is None or id(anchor) in seen:
                continue
            seen.add(id(anchor))
            try:
                anchor.close()
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

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


def _directory_path_matches_anchor(anchor: _DirectoryAnchor) -> bool:
    try:
        return _directory_identity(anchor.path) == anchor.identity
    except (FileNotFoundError, NotADirectoryError, RuntimeError):
        return False


def _anchored_name_exists(anchor: _DirectoryAnchor, name: str) -> bool:
    if os.name == "nt":
        try:
            os.lstat(anchor.path / name)
        except FileNotFoundError:
            return False
        return True
    assert anchor._descriptor is not None
    try:
        os.stat(name, dir_fd=anchor._descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _anchored_name_matches(
    anchor: _DirectoryAnchor,
    name: str,
    expected_identity: tuple[int, int],
) -> bool:
    try:
        if os.name == "nt":
            current = _directory_identity(anchor.path / name)
        else:
            assert anchor._descriptor is not None
            info = os.stat(name, dir_fd=anchor._descriptor, follow_symlinks=False)
            current = (info.st_dev, info.st_ino)
    except (FileNotFoundError, NotADirectoryError, RuntimeError):
        return False
    return current == expected_identity


def _file_identity(path: Path) -> tuple[int, int]:
    info = os.lstat(path)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & reparse
    ):
        raise RuntimeError("artifact session layout invalid")
    return info.st_dev, info.st_ino


def _retained_descriptor_root(path: Path) -> bool:
    """Report an exact ``/proc/self/fd/<fd>`` or ``/dev/fd/<fd>`` store root.

    The desktop storage authority hands the store a root that *is* one open
    directory descriptor of this process, so its final component is a magic
    link. That link is an already-validated capability and the descriptor table
    is process-private, so this exact root may be followed; every child anchor
    stays no-follow checked. ``loopplane.host.snapshot`` applies the same rule.
    """

    name = path.name
    return (
        os.name != "nt"
        and path.is_absolute()
        and path.parent in {Path("/proc/self/fd"), Path("/dev/fd")}
        and name.isascii()
        and name.isdecimal()
    )


def _directory_identity(path: Path) -> tuple[int, int]:
    info = os.stat(path) if _retained_descriptor_root(path) else os.lstat(path)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & reparse
    ):
        raise RuntimeError("artifact session layout invalid")
    return info.st_dev, info.st_ino


def _posix_rename_noreplace(
    *,
    source_name: str,
    destination_name: str,
    source_parent_descriptor: int,
    destination_parent_descriptor: int,
) -> None:
    import ctypes
    import errno

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RuntimeError("artifact deletion no-replace unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    rename_noreplace = 1
    result = renameat2(
        source_parent_descriptor,
        os.fsencode(source_name),
        destination_parent_descriptor,
        os.fsencode(destination_name),
        rename_noreplace,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise RuntimeError("artifact deletion rollback blocked")
    if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
        raise RuntimeError("artifact deletion no-replace unavailable")
    raise OSError(error, os.strerror(error))


def _posix_rename_exact_entry(
    *,
    source_name: str,
    destination_name: str,
    parent_anchor: _DirectoryAnchor,
    expected_identity: tuple[int, int],
) -> None:
    assert parent_anchor._descriptor is not None
    parent_fd = parent_anchor._descriptor
    try:
        os.stat(destination_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError("artifact deletion authority changed")
    current = os.stat(source_name, dir_fd=parent_fd, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != expected_identity:
        raise RuntimeError("artifact deletion authority changed")
    _posix_rename_noreplace(
        source_name=source_name,
        destination_name=destination_name,
        source_parent_descriptor=parent_fd,
        destination_parent_descriptor=parent_fd,
    )


def _posix_unlink_exact_entry(
    *,
    name: str,
    parent_anchor: _DirectoryAnchor,
    expected_identity: tuple[int, int],
    directory: bool = False,
) -> None:
    assert parent_anchor._descriptor is not None
    parent_fd = parent_anchor._descriptor
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != expected_identity:
        raise RuntimeError("artifact deletion authority changed")
    if directory:
        os.rmdir(name, dir_fd=parent_fd)
    else:
        os.unlink(name, dir_fd=parent_fd)


def _posix_open_artifact_members(
    artifacts_anchor: _DirectoryAnchor,
    member_identities: tuple[tuple[str, tuple[int, int]], ...],
) -> tuple[int, ...]:
    assert artifacts_anchor._descriptor is not None
    flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    opened: list[int] = []
    try:
        for name, identity in member_identities:
            descriptor = os.open(name, flags, dir_fd=artifacts_anchor._descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != identity:
                os.close(descriptor)
                raise RuntimeError("artifact deletion authority changed")
            opened.append(descriptor)
    except Exception:
        for descriptor in reversed(opened):
            os.close(descriptor)
        raise
    return tuple(opened)


def _posix_open_directory_anchor(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    if not _retained_descriptor_root(path):
        # Every anchor but the process-private capability root must refuse a
        # link at its final component. O_NOFOLLOW would fail that root outright:
        # a procfs descriptor link reports ENOTDIR rather than opening.
        flags |= getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags)


def _windows_open_directory_anchor(
    path: Path,
    *,
    movable: bool = False,
    protect_rename: bool = False,
) -> int:
    import ctypes
    from ctypes import wintypes

    windows_ctypes = _windows_ctypes()
    delete_access = 0x00010000
    file_read_attributes = 0x00000080
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    file_flag_open_reparse_point = 0x00200000
    invalid_handle = ctypes.c_void_p(-1).value
    kernel32 = windows_ctypes.WinDLL("kernel32", use_last_error=True)
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
    if movable and protect_rename:
        raise ValueError("directory anchor modes conflict")
    delete_authority = movable or protect_rename
    handle = create_file(
        str(path),
        (delete_access if delete_authority else 0) | file_read_attributes,
        file_share_read | file_share_write | (file_share_delete if movable else 0),
        None,
        open_existing,
        file_flag_backup_semantics | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle:
        raise windows_ctypes.WinError(windows_ctypes.get_last_error())
    return int(handle)


def _windows_close_directory_anchor(handle: int) -> None:
    from ctypes import wintypes

    windows_ctypes = _windows_ctypes()
    kernel32 = windows_ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    if not close_handle(wintypes.HANDLE(handle)):
        raise windows_ctypes.WinError(windows_ctypes.get_last_error())


def _erase_tree_anchored_posix(
    session_anchor: _DirectoryAnchor,
    artifacts_anchor: _DirectoryAnchor,
    *,
    member_identities: tuple[tuple[str, tuple[int, int]], ...],
    member_descriptors: tuple[int, ...],
) -> None:
    assert session_anchor._descriptor is not None
    assert artifacts_anchor._descriptor is not None
    session_fd = session_anchor._descriptor
    if os.listdir(session_fd) != [_ARTIFACT_DIR]:
        raise RuntimeError("artifact session layout invalid")
    child = os.stat(_ARTIFACT_DIR, dir_fd=session_fd, follow_symlinks=False)
    if (child.st_dev, child.st_ino) != artifacts_anchor.identity:
        raise RuntimeError("artifact deletion authority changed")
    _erase_anchored_posix_members(
        artifacts_anchor,
        member_identities=member_identities,
        member_descriptors=member_descriptors,
    )


def _erase_anchored_posix_members(
    artifacts_anchor: _DirectoryAnchor,
    *,
    member_identities: tuple[tuple[str, tuple[int, int]], ...],
    member_descriptors: tuple[int, ...],
) -> None:
    assert artifacts_anchor._descriptor is not None
    artifacts_fd = artifacts_anchor._descriptor
    members = os.listdir(artifacts_fd)
    expected = dict(member_identities)
    if set(members) != set(expected):
        raise RuntimeError("artifact deletion authority changed")
    opened_here: list[int] = []
    descriptors = member_descriptors
    if not descriptors:
        descriptors = _posix_open_artifact_members(
            artifacts_anchor,
            member_identities,
        )
        opened_here.extend(descriptors)
    if len(descriptors) != len(members):
        raise RuntimeError("artifact deletion authority changed")
    try:
        for descriptor, (_name, identity) in zip(
            descriptors, member_identities, strict=True
        ):
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != identity
            ):
                raise RuntimeError("artifact deletion authority changed")
        for descriptor in descriptors:
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
    finally:
        for descriptor in reversed(opened_here):
            os.close(descriptor)


def _delete_tree_anchored_windows(deletion: ArtifactSessionDeletion) -> None:
    session_anchor = deletion.staged_parent_anchor
    artifacts_anchor = deletion.artifacts_anchor
    member_identities = deletion.member_identities
    import ctypes
    from ctypes import wintypes

    windows_ctypes = _windows_ctypes()
    delete_access = 0x00010000
    file_read_attributes = 0x00000080
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
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

    kernel32 = windows_ctypes.WinDLL("kernel32", use_last_error=True)
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

    def handle_identity(handle: int, *, directory: bool) -> tuple[int, int]:
        information = _ByHandleFileInformation()
        if not get_information(wintypes.HANDLE(handle), ctypes.byref(information)):
            raise windows_ctypes.WinError(windows_ctypes.get_last_error())
        is_directory = bool(information.file_attributes & file_attribute_directory)
        if is_directory != directory or (
            information.file_attributes & file_attribute_reparse_point
        ):
            raise RuntimeError("artifact session layout invalid")
        file_index = (information.file_index_high << 32) | information.file_index_low
        return information.volume_serial_number, file_index

    def open_member(path: Path, identity: tuple[int, int]) -> int:
        handle = create_file(
            str(path),
            delete_access | file_read_attributes,
            file_share_read | file_share_write | file_share_delete,
            None,
            open_existing,
            file_flag_open_reparse_point,
            None,
        )
        if handle == invalid_handle:
            raise windows_ctypes.WinError(windows_ctypes.get_last_error())
        try:
            _volume, file_index = handle_identity(int(handle), directory=False)
            _device, expected_inode = identity
            if expected_inode and file_index != expected_inode:
                raise RuntimeError("artifact deletion authority changed")
        except Exception:
            close_handle(handle)
            raise
        return int(handle)

    def mark_delete(handle: int) -> None:
        disposition = _FileDispositionInfo(True)
        if not set_information(
            wintypes.HANDLE(handle),
            file_disposition_info,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        ):
            raise windows_ctypes.WinError(windows_ctypes.get_last_error())

    def close_members() -> None:
        first_error: OSError | None = None
        remaining: list[int] = []
        for handle in reversed(deletion.member_handles):
            if not close_handle(wintypes.HANDLE(handle)):
                remaining.append(handle)
                if first_error is None:
                    first_error = windows_ctypes.WinError(
                        windows_ctypes.get_last_error()
                    )
        object.__setattr__(deletion, "member_handles", tuple(reversed(remaining)))
        if first_error is not None:
            raise first_error

    session_path = session_anchor.path
    artifacts_path = artifacts_anchor.path
    if deletion.session_delete_pending:
        if session_anchor._handle is None:
            raise RuntimeError("artifact deletion authority changed")
        mark_delete(session_anchor._handle)
        session_anchor.close()
        object.__setattr__(deletion, "session_delete_pending", False)
        return
    if deletion.artifacts_delete_pending:
        if artifacts_anchor._handle is None or session_anchor._handle is None:
            raise RuntimeError("artifact deletion authority changed")
        mark_delete(artifacts_anchor._handle)
        artifacts_anchor.close()
        object.__setattr__(deletion, "artifacts_delete_pending", False)
        object.__setattr__(deletion, "session_delete_pending", True)
        if session_anchor is artifacts_anchor:
            object.__setattr__(deletion, "session_delete_pending", False)
            return
        mark_delete(session_anchor._handle)
        session_anchor.close()
        object.__setattr__(deletion, "session_delete_pending", False)
        return
    if deletion.members_delete_pending:
        if not deletion.member_handles:
            raise RuntimeError("artifact deletion authority changed")
        for handle in deletion.member_handles:
            mark_delete(handle)
        close_members()
        object.__setattr__(deletion, "members_delete_pending", False)
        object.__setattr__(deletion, "artifacts_delete_pending", True)
        if artifacts_anchor._handle is None or session_anchor._handle is None:
            raise RuntimeError("artifact deletion authority changed")
        mark_delete(artifacts_anchor._handle)
        artifacts_anchor.close()
        object.__setattr__(deletion, "artifacts_delete_pending", False)
        object.__setattr__(deletion, "session_delete_pending", True)
        if session_anchor is artifacts_anchor:
            object.__setattr__(deletion, "session_delete_pending", False)
            return
        mark_delete(session_anchor._handle)
        session_anchor.close()
        object.__setattr__(deletion, "session_delete_pending", False)
        return

    if list(session_path.iterdir()) != [artifacts_path]:
        raise RuntimeError("artifact session layout invalid")
    members = list(artifacts_path.iterdir())
    expected = dict(member_identities)
    if {member.name for member in members} != set(expected):
        raise RuntimeError("artifact deletion authority changed")
    opened_members: list[int] = []
    try:
        for member in members:
            opened_members.append(open_member(member, expected[member.name]))
    except Exception:
        for handle in reversed(opened_members):
            close_handle(wintypes.HANDLE(handle))
        raise
    object.__setattr__(deletion, "member_handles", tuple(opened_members))
    object.__setattr__(deletion, "members_delete_pending", True)
    for handle in deletion.member_handles:
        mark_delete(handle)
    close_members()
    object.__setattr__(deletion, "members_delete_pending", False)
    object.__setattr__(deletion, "artifacts_delete_pending", True)
    if artifacts_anchor._handle is None or session_anchor._handle is None:
        raise RuntimeError("artifact deletion authority changed")
    mark_delete(artifacts_anchor._handle)
    artifacts_anchor.close()
    object.__setattr__(deletion, "artifacts_delete_pending", False)
    object.__setattr__(deletion, "session_delete_pending", True)
    if session_anchor is artifacts_anchor:
        object.__setattr__(deletion, "session_delete_pending", False)
        return
    mark_delete(session_anchor._handle)
    session_anchor.close()
    object.__setattr__(deletion, "session_delete_pending", False)


def make_artifact_handoff(store: ArtifactStore) -> ArtifactHandoff:
    """Bind an ArtifactStore as the Gateway's offload seam (FR-090)."""

    async def handoff(
        call: ToolCallRequest, outputs: list[OutputBlock], context: RunContext
    ) -> tuple[str, str]:
        return await store.offload(
            session_id=context.session_id, call_id=call.call_id, outputs=outputs
        )

    return handoff
