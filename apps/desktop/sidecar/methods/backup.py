"""backup.* / restore.* RPC methods (078 T076/T077 skeleton)."""

from __future__ import annotations

import errno
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from loopplane.host import LoopPlaneHost

try:
    from ..archive import ArchiveValidationError
    from ..backup import create_backup_archive, describe_backup
    from ..durability import (
        DurabilityUnsupported,
        PostProofCommitError,
        ProofEffectUncertain,
        RestorePublicationFailed,
        RestoreRecoveryLocked,
        RestoreRolledBack,
        commit_restore,
    )
    from ..interaction import InteractionLease
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..profile import ProfileState
    from ..protocol import RpcError
    from ..restore import RestoreManager
except ImportError:  # pragma: no cover
    from profile import ProfileState  # type: ignore[no-redef]

    from archive import ArchiveValidationError  # type: ignore[no-redef]
    from backup import create_backup_archive, describe_backup  # type: ignore[no-redef]
    from durability import (  # type: ignore[no-redef]
        DurabilityUnsupported,
        PostProofCommitError,
        ProofEffectUncertain,
        RestorePublicationFailed,
        RestoreRecoveryLocked,
        RestoreRolledBack,
        commit_restore,
    )
    from interaction import InteractionLease  # type: ignore[no-redef]
    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )
    from protocol import RpcError  # type: ignore[no-redef]
    from restore import RestoreManager  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]

_BUSY = RpcError(
    code=-32004,
    message="Busy",
    category="busy",
    retryable=True,
    message_key="backup.error.profile_busy",
    recovery="wait",
)
_INVALID = RpcError(
    code=-32602,
    message="Invalid params",
    category="invalid_params",
    retryable=False,
    message_key="desktop.error.invalid_params",
)
_UNSAFE_ARCHIVE = RpcError(
    code=-32007,
    message="Unsafe input",
    category="unsafe_input",
    retryable=False,
    message_key="backup.error.unsafe_archive",
)
_INCOMPATIBLE_BACKUP = RpcError(
    code=-32001,
    message="Incompatible backup",
    category="incompatible_protocol",
    retryable=False,
    message_key="backup.error.incompatible",
    recovery="contact_support",
)
_INTEGRITY_FAILED = RpcError(
    code=-32007,
    message="Unsafe input",
    category="unsafe_input",
    retryable=False,
    message_key="backup.error.integrity_failed",
)
_LIMIT_EXCEEDED = RpcError(
    code=-32007,
    message="Unsafe input",
    category="unsafe_input",
    retryable=False,
    message_key="backup.error.limit_exceeded",
)
_NOT_FOUND = RpcError(
    code=-32002,
    message="Not found",
    category="not_found",
    retryable=False,
    message_key="desktop.error.not_found",
)
_INSUFFICIENT_SPACE = RpcError(
    code=-32008,
    message="Unavailable",
    category="unavailable",
    retryable=True,
    message_key="backup.error.insufficient_space",
    recovery="retry",
)
_DURABILITY_UNSUPPORTED = RpcError(
    code=-32011,
    message="Durability unsupported",
    category="durability_unsupported",
    retryable=False,
    message_key="restore.error.durability_unsupported",
    recovery="contact_support",
)
_PUBLICATION_FAILED_RETRYABLE = RpcError(
    code=-32012,
    message="Publication failed",
    category="publication_failed",
    retryable=True,
    message_key="restore.error.publication_failed_retryable",
    recovery="retry",
)
_PUBLICATION_FAILED_RESTART = RpcError(
    code=-32012,
    message="Publication failed",
    category="publication_failed",
    retryable=False,
    message_key="restore.error.publication_failed_restart",
    recovery="restart_runtime",
)
_ROLLED_BACK = RpcError(
    code=-32012,
    message="Publication failed",
    category="publication_failed",
    retryable=True,
    message_key="restore.error.rolled_back",
    recovery="retry",
)
_ARCHIVE_INCOMPATIBLE_REASONS = frozenset({"manifest_incompatible"})
_ARCHIVE_INTEGRITY_REASONS = frozenset(
    {
        "archive_integrity_failed",
        "archive_size_mismatch",
        "archive_totals_mismatch",
        "manifest_not_canonical",
        "manifest_revalidation_failed",
    }
)
_ARCHIVE_LIMIT_REASONS = frozenset(
    {
        "archive_expansion_ratio",
        "archive_limits",
        "manifest_limits",
        "manifest_too_deep",
        "manifest_too_large",
    }
)
_ARCHIVE_UNSAFE_REASONS = frozenset(
    {
        "archive_declaration_mismatch",
        "archive_descriptor_unsupported",
        "archive_duplicate_entries",
        "archive_encrypted",
        "archive_entry_type_invalid",
        "archive_invalid",
        "archive_local_header_invalid",
        "archive_local_header_mismatch",
        "archive_path_collision",
        "archive_path_invalid",
        "archive_required_member_missing",
        "disclosure_not_acknowledged",
        "manifest_disclosure_invalid",
        "manifest_duplicate_key",
        "manifest_entry_invalid",
        "manifest_entry_order",
        "manifest_invalid",
        "manifest_missing",
        "profile_invalid",
        "snapshot_changed",
        "snapshot_invalid",
        "temporary_creation_failed",
        "unbounded_snapshot_read_forbidden",
    }
)
_RESTORE_INTEGRITY_REASONS = frozenset(
    {
        "archive_integrity_failed",
        "archive_size_mismatch",
        "profile_checkpoint_invalid",
        "profile_checkpoint_missing_metadata",
        "profile_identity_mismatch",
        "profile_invalid",
        "profile_principal_mismatch",
        "profile_project_inventory_mismatch",
    }
)
_RESTORE_UNSAFE_REASONS = frozenset(
    {
        "archive not found",
        "archive_changed",
        "archive_changed_during_validation",
        "archive_declaration_mismatch",
        "archive_stream_failed",
        "invalid_manifest",
        "unsafe_archive_path",
        "unsafe_or_invalid_archive",
    }
)


class _RestoreIntegrityError(ValueError):
    """A manifest-valid archive failed Host portable-snapshot validation."""


def _archive_validation_error(exc: BaseException) -> RpcError | None:
    if isinstance(exc, _RestoreIntegrityError):
        return _INTEGRITY_FAILED
    current: BaseException | None = exc
    for _ in range(8):
        if current is None:
            break
        if isinstance(current, ArchiveValidationError):
            reason = str(current)
            if reason in _ARCHIVE_INCOMPATIBLE_REASONS:
                return _INCOMPATIBLE_BACKUP
            if reason in _ARCHIVE_INTEGRITY_REASONS:
                return _INTEGRITY_FAILED
            if reason in _ARCHIVE_LIMIT_REASONS:
                return _LIMIT_EXCEEDED
            if reason in _ARCHIVE_UNSAFE_REASONS:
                return _UNSAFE_ARCHIVE
            return None
        current = current.__cause__ or current.__context__
    reason = str(exc)
    if reason in _RESTORE_INTEGRITY_REASONS:
        return _INTEGRITY_FAILED
    if reason in _RESTORE_UNSAFE_REASONS:
        return _UNSAFE_ARCHIVE
    return None


def _is_insufficient_space(exc: BaseException) -> bool:
    current: BaseException | None = exc
    for _ in range(8):
        if current is None:
            break
        if isinstance(current, OSError) and (
            current.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}
            or getattr(current, "winerror", None) == 112
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


class BackupMethods:
    def __init__(
        self,
        host: LoopPlaneHost,
        profile_state: ProfileState,
        mutation_lease: ProfileMutationLease,
        *,
        interaction_lease: InteractionLease | None = None,
        restore_manager: RestoreManager | None = None,
        candidate_ready: Callable[[Path], object] | None = None,
        close_previous: Callable[[], object] | None = None,
        install_candidate: Callable[[Path], object] | None = None,
        commit_candidate: Callable[[], object] | None = None,
        rollback_candidate: Callable[[], object] | None = None,
        lock_dispatch: Callable[[], object] | None = None,
        unlock_dispatch_after_rollback: Callable[[], object] | None = None,
    ) -> None:
        self._host = host
        self._state = profile_state
        self._lease = mutation_lease
        self._interaction = interaction_lease
        self._restore = restore_manager or RestoreManager(profile_state.root)
        self._candidate_ready = candidate_ready
        self._close_previous = close_previous
        self._install_candidate = install_candidate
        self._commit_candidate = commit_candidate
        self._rollback_candidate = rollback_candidate
        self._lock_dispatch = lock_dispatch
        self._unlock_dispatch_after_rollback = unlock_dispatch_after_rollback
        self._validated_mutations: dict[str, dict[str, Any]] = {}
        self._restore_lease_identities: dict[str, str] = {}
        self._startup_only_tokens: set[str] = set()
        self._lease.set_expiry_reaper(self._release_expired_restores)

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "backup.describe": self.describe,
            "backup.create": self.create,
            "restore.validate": self.restore_validate,
            "restore.commit": self.restore_commit,
            "restore.cancel": self.restore_cancel,
        }

    async def describe(self, _params: dict[str, Any]) -> dict[str, Any]:
        return describe_backup().to_public()

    async def create(self, params: dict[str, Any]) -> dict[str, Any]:
        mid = params.get("mutation_id")
        if not isinstance(mid, str) or not mid.strip():
            raise _INVALID
        if params.get("acknowledgement") is not True:
            raise _INVALID
        dest = params.get("destination_path") or params.get("path")
        if not isinstance(dest, str) or not dest.strip():
            raise _INVALID
        # Competing interactive open blocks backup.
        if self._interaction is not None and self._interaction.active is not None:
            raise _BUSY
        try:
            self._lease.require_free_or_owner("backup", mid)
            self._lease.acquire("backup", mid)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        try:
            # The caller-created directory is private staging.  A failed Host
            # snapshot never reaches archive construction or destination publish.
            with TemporaryDirectory(
                prefix=".loopplane-backup-snapshot-", dir=Path(dest).parent
            ) as temporary:
                snapshot_root = Path(temporary)
                snapshot = self._host.export_portable_snapshot(snapshot_root)
                if not snapshot.ok:
                    raise RuntimeError("portable snapshot unavailable")
                portable = self._state.load_portable()
                result = create_backup_archive(
                    Path(dest),
                    profile_portable=portable,
                    snapshot_root=snapshot_root,
                )
            return {
                "ok": True,
                "finalized": result["finalized"],
                "entry_count": result["entry_count"],
                "format": result["format"],
                "disclosure_applied": True,
            }
        except (OSError, RuntimeError, ValueError) as exc:
            # Never issue a finalized result when snapshot/archive validation
            # failed; the existing destination has not been replaced.
            if _is_insufficient_space(exc):
                raise _INSUFFICIENT_SPACE from exc
            raise
        finally:
            if self._lease.held_by("backup", mid):
                self._lease.release("backup", mid)

    async def restore_validate(self, params: dict[str, Any]) -> dict[str, Any]:
        mid = params.get("mutation_id")
        if not isinstance(mid, str) or not mid.strip():
            raise _INVALID
        cached = self._validated_mutations.get(mid)
        if cached is not None:
            return dict(cached)
        path = params.get("source_path") or params.get("path")
        if not isinstance(path, str) or not path.strip():
            raise _INVALID
        if self._interaction is not None and self._interaction.active is not None:
            raise _BUSY
        try:
            self._lease.require_free_or_owner("restore", mid)
            self._lease.acquire("restore", mid)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        # Reservation holds the lease until commit/cancel.  Host validation is
        # fail-closed: no token survives an unavailable or invalid snapshot.
        reservation: Any | None = None
        try:
            reservation = self._restore.validate_archive(Path(path))
            validation = self._host.validate_portable_snapshot(
                reservation.host_snapshot_dir
            )
            if not validation.ok:
                raise _RestoreIntegrityError
            result = {
                "restore_token": reservation.token,
                "summary": {
                    **reservation.summary,
                    "relink_required": True,
                },
            }
            self._validated_mutations[mid] = result
            self._restore_lease_identities[reservation.token] = mid
            return dict(result)
        except ValueError as exc:
            if reservation is not None:
                self._restore.cancel(reservation.token)
            if self._lease.held_by("restore", mid):
                self._lease.release("restore", mid)
            if _is_insufficient_space(exc):
                raise _INSUFFICIENT_SPACE from exc
            # Only a closed known-cause set selects a fixed public row. Unknown
            # validation causes escape to the dispatcher's sole fallback.
            mapped = _archive_validation_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        except Exception as exc:
            if reservation is not None:
                self._restore.cancel(reservation.token)
            if self._lease.held_by("restore", mid):
                self._lease.release("restore", mid)
            if _is_insufficient_space(exc):
                raise _INSUFFICIENT_SPACE from exc
            raise

    async def restore_commit(self, params: dict[str, Any]) -> dict[str, Any]:
        mid = params.get("mutation_id")
        if not isinstance(mid, str) or not mid.strip():
            raise _INVALID
        token = params.get("restore_token")
        if not isinstance(token, str) or not token.strip():
            raise _INVALID
        if params.get("confirmation") is not True:
            raise _INVALID
        if token in self._startup_only_tokens:
            raise _PUBLICATION_FAILED_RESTART
        identity = self._restore_lease_identities.get(token)
        if identity is None or not self._lease.held_by("restore", identity):
            raise _BUSY
        reservation = self._restore.get(token)
        if reservation is None:
            raise _NOT_FOUND
        if self._restore.expired(reservation):
            self._finish_restore(token, identity)
            raise _NOT_FOUND
        if not self._restore.revalidate_archive(reservation):
            self._finish_restore(token, identity)
            raise _INTEGRITY_FAILED
        try:
            committed = await commit_restore(
                self._state.root,
                reservation,
                self._restore,
                candidate_ready=self._candidate_ready,
                close_previous=self._close_previous,
                install_candidate=self._install_candidate,
                commit_candidate=self._commit_candidate,
                rollback_candidate=self._rollback_candidate,
                lock_dispatch=self._lock_dispatch,
                unlock_dispatch_after_rollback=self._unlock_dispatch_after_rollback,
            )
        except ProofEffectUncertain as exc:
            # The candidate runtime already owns dispatch. Keep its in-memory
            # profile authority aligned while leaving every recovery byte and the
            # lease untouched for startup-only adjudication.
            self._state.generation_id = exc.generation_id
            self._state.profile_id = reservation.profile_portable["profile_id"]
            self._state.principal_id = reservation.profile_portable["principal_id"]
            self._startup_only_tokens.add(token)
            raise _PUBLICATION_FAILED_RESTART from exc
        except RestoreRecoveryLocked as exc:
            # Recovery could not prove a safe mutation. Leave every recovery byte
            # and the lease untouched for startup-only adjudication.
            self._startup_only_tokens.add(token)
            raise _PUBLICATION_FAILED_RESTART from exc
        except PostProofCommitError as exc:
            # Candidate proof remains authority; align every in-memory owner before
            # releasing the lease even though startup must finish journal cleanup.
            self._state.generation_id = exc.generation_id
            self._state.profile_id = reservation.profile_portable["profile_id"]
            self._state.principal_id = reservation.profile_portable["principal_id"]
            self._finish_restore(token, identity)
            raise _PUBLICATION_FAILED_RESTART from exc
        except DurabilityUnsupported as exc:
            self._finish_restore(token, identity)
            raise _DURABILITY_UNSUPPORTED from exc
        except RestorePublicationFailed as exc:
            self._finish_restore(token, identity)
            raise _PUBLICATION_FAILED_RETRYABLE from exc
        except RestoreRolledBack as exc:
            self._finish_restore(token, identity)
            raise _ROLLED_BACK from exc
        except Exception:
            self._finish_restore(token, identity)
            raise

        self._state.generation_id = committed.generation_id
        self._state.profile_id = reservation.profile_portable["profile_id"]
        self._state.principal_id = reservation.profile_portable["principal_id"]
        self._finish_restore(token, identity)
        return {
            "ok": True,
            "committed": True,
            "relink_required": True,
        }

    async def restore_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        mid = params.get("mutation_id")
        if not isinstance(mid, str) or not mid.strip():
            raise _INVALID
        token = params.get("restore_token")
        if not isinstance(token, str) or not token.strip():
            raise _INVALID
        if token in self._startup_only_tokens:
            raise _PUBLICATION_FAILED_RESTART
        identity = self._restore_lease_identities.get(token)
        if identity is None or not self._lease.held_by("restore", identity):
            raise _BUSY
        reservation = self._restore.get(token)
        if reservation is None:
            raise _NOT_FOUND
        if self._restore.expired(reservation):
            self._finish_restore(token, identity)
            raise _NOT_FOUND
        ok = self._restore.cancel(token)
        if not ok:
            raise _NOT_FOUND
        self._discard_validated_token(token)
        self._restore_lease_identities.pop(token, None)
        self._lease.release("restore", identity)
        return {"cancelled": True, "restore_token": token}

    def _release_expired_restores(self) -> None:
        for token, identity in list(self._restore_lease_identities.items()):
            if token in self._startup_only_tokens:
                continue
            reservation = self._restore.get(token)
            if reservation is None or self._restore.expired(reservation):
                self._finish_restore(token, identity)

    def shutdown(self) -> None:
        """Bounded connection teardown; never begins durable restore work."""

        for token, identity in list(self._restore_lease_identities.items()):
            if token not in self._startup_only_tokens:
                self._finish_restore(token, identity)
        if not self._startup_only_tokens:
            self._restore.release_all()

    def _finish_restore(self, token: str, identity: str) -> None:
        try:
            self._restore.cancel(token)
        finally:
            self._discard_validated_token(token)
            self._restore_lease_identities.pop(token, None)
            if self._lease.held_by("restore", identity):
                self._lease.release("restore", identity)

    def _discard_validated_token(self, token: str) -> None:
        for mutation_id, result in list(self._validated_mutations.items()):
            if result.get("restore_token") == token:
                self._validated_mutations.pop(mutation_id, None)
