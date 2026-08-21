"""Desktop runtime owner: lock + generation bootstrap before Host (078 T025)."""

from __future__ import annotations

import os
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from loopplane.host import (
    DesktopActiveGenerationProvider,
    DesktopRuntimeStorageInitializer,
    DesktopStorageAuthorityFactory,
    GenerationExpectation,
    LoopPlaneHost,
    RuntimeConfig,
    validate_active_generation,
)

try:
    from .durability import (
        RestoreRecoveryLocked,
        adjudicate_restore_recovery,
        complete_pointer,
        current_generation_pointer_exists,
        is_canonical_generation_id,
        is_link_or_reparse,
        owned_generation_directory,
        owned_generation_parent,
        publish_pristine_generation,
        publish_runtime_storage,
        read_current_generation,
        read_proof,
    )
    from .mutation_lease import ProfileMutationLease
    from .profile import ProfileOwnershipLock, ProfileState
except ImportError:  # pragma: no cover
    from profile import ProfileOwnershipLock, ProfileState  # type: ignore[no-redef]

    from durability import (  # type: ignore[no-redef]
        RestoreRecoveryLocked,
        adjudicate_restore_recovery,
        complete_pointer,
        current_generation_pointer_exists,
        is_canonical_generation_id,
        is_link_or_reparse,
        owned_generation_directory,
        owned_generation_parent,
        publish_pristine_generation,
        publish_runtime_storage,
        read_current_generation,
        read_proof,
    )
    from mutation_lease import ProfileMutationLease  # type: ignore[no-redef]


_CURRENT_GENERATION_PROVIDER = DesktopActiveGenerationProvider()


class RestoreJournalsPresent(RuntimeError):
    """Restore recovery cannot prove one active generation."""

    public_code = "durability_locked"


class RuntimeHostHandover:
    """One forwarding Host reference with candidate-only storage handover.

    Sidecar method objects receive this reference once.  After a candidate is
    ready, their ordinary public Host-facade calls resolve to the new Host rather
    than retaining a stale storage owner.
    """

    def __init__(
        self,
        host: LoopPlaneHost,
        *,
        profile_root: Path,
        config: RuntimeConfig | None = None,
        host_changed: Callable[[LoopPlaneHost | None], None] | None = None,
    ) -> None:
        self._host: LoopPlaneHost | None = host
        self._host_changed = host_changed
        self._profile_root = Path(profile_root)
        # Composition supplies an immutable RuntimeConfig; no Host internals are
        # read as a fallback. Non-restore dispatcher tests may omit it, but restore
        # then fails closed before candidate Host construction.
        self._config = config
        self._candidate: LoopPlaneHost | None = None
        self._candidate_config: RuntimeConfig | None = None
        self._previous: LoopPlaneHost | None = None
        self._pending_previous: LoopPlaneHost | None = None
        self._candidate_storage: Path | None = None
        self._discard_candidate_storage = False
        self._transaction_active = False
        self._candidate_installed = False
        self._previous_closed = False
        self._dispatch_locked = False
        self._closed_host_ids: set[int] = set()

    def __getattr__(self, name: str) -> Any:
        if self._dispatch_locked:
            raise RuntimeError("runtime Host authority is recovery-locked")
        if self._host is None:
            raise RuntimeError("runtime Host authority is closed")
        return getattr(self._host, name)

    def _replace_current_host(self, host: LoopPlaneHost | None) -> None:
        self._host = host
        if self._host_changed is not None:
            self._host_changed(host)

    def lock_dispatch(self) -> None:
        """Block public Host forwarding until startup or exact rollback decides."""

        self._dispatch_locked = True

    def unlock_dispatch_after_rollback(self) -> None:
        """Re-enable forwarding only after runtime and durable rollback complete."""

        if (
            self._transaction_active
            or self._candidate is not None
            or self._previous is not None
            or self._pending_previous is not None
            or self._candidate_installed
        ):
            raise RuntimeError("runtime Host rollback is incomplete")
        self._dispatch_locked = False

    async def candidate_ready(self, generation_dir: Path) -> None:
        if self._dispatch_locked:
            raise RuntimeError("runtime Host authority is recovery-locked")
        if self._config is None or self._config.storage is None:
            raise RuntimeError("candidate Host configuration unavailable")
        if self._previous is not None or self._pending_previous is not None:
            self._transaction_active = False
            raise RuntimeError("previous Host cleanup is pending")
        if self._transaction_active or self._candidate is not None:
            raise RuntimeError("candidate Host transaction already active")
        self._transaction_active = True
        self._candidate_installed = False
        self._previous_closed = False
        try:
            storage_root = self._materialize_candidate_storage(generation_dir)
            self._candidate_storage = storage_root
            candidate_config = replace(
                self._config,
                storage=replace(self._config.storage, root=storage_root),
            )
            self._candidate_config = candidate_config
            self._candidate = LoopPlaneHost(
                candidate_config, working_scope=self._profile_root
            )
            self._candidate.enable_desktop_portable_snapshot()
            # A normal public Host read opens/revalidates the restored SQLite state.
            self._candidate.list_sessions()
        except Exception:
            self._candidate_installed = False
            try:
                if self._candidate is not None:
                    await self._discard_candidate(self._candidate)
                else:
                    self._remove_candidate_storage()
            except Exception:
                self._dispatch_locked = True
                raise
            self._candidate_config = None
            self._transaction_active = False
            raise

    async def close_previous(self) -> None:
        """Close the quiescent previous Host before candidate installation/proof."""

        if not self._transaction_active or self._candidate is None:
            raise RuntimeError("candidate Host was not ready")
        if self._previous is None:
            if self._host is None:
                raise RuntimeError("current Host is unavailable")
            self._previous = self._host
        previous = self._previous
        try:
            await previous.aclose()
        except Exception:
            self._previous_closed = False
            raise
        if id(previous) not in self._closed_host_ids:
            self._closed_host_ids.add(id(previous))
        self._previous_closed = True

    def install_candidate(self, _generation_dir: Path) -> None:
        if not self._transaction_active or self._candidate is None:
            raise RuntimeError("candidate Host was not ready")
        if self._previous is None or not self._previous_closed:
            raise RuntimeError("previous Host is not closed")
        self._replace_current_host(self._candidate)
        self._candidate = None
        self._candidate_installed = True

    def commit_candidate(self) -> None:
        """Seal one proof-authorized candidate as the sole runtime owner."""

        if not self._transaction_active or not self._candidate_installed:
            raise RuntimeError("candidate Host was not installed")
        if self._previous is None or not self._previous_closed:
            raise RuntimeError("previous Host handover is incomplete")
        if self._candidate_config is None:
            raise RuntimeError("candidate Host configuration is unavailable")
        self._config = self._candidate_config
        self._candidate_config = None
        self._previous = None
        self._previous_closed = False
        self._transaction_active = False
        self._candidate_installed = False
        self._closed_host_ids.clear()

    async def rollback_candidate(self) -> None:
        """Close the candidate and recompose one usable previous Host."""

        if not self._transaction_active:
            return
        candidate = self._host if self._candidate_installed else self._candidate
        previous = self._previous
        try:
            if candidate is not None:
                await self._discard_candidate(candidate)
            else:
                self._remove_candidate_storage()
            if previous is not None:
                if not self._previous_closed:
                    await previous.aclose()
                    if id(previous) not in self._closed_host_ids:
                        self._closed_host_ids.add(id(previous))
                    self._previous_closed = True
                rebuilt = self._build_previous_host()
                self._replace_current_host(rebuilt)
                self._pending_previous = None
        except Exception:
            self._dispatch_locked = True
            raise
        self._previous = None
        self._previous_closed = False
        self._candidate = None
        self._candidate_config = None
        self._transaction_active = False
        self._candidate_installed = False
        self._closed_host_ids.clear()

    def _build_previous_host(self) -> LoopPlaneHost:
        if self._config is None or self._config.storage is None:
            raise RuntimeError("previous Host configuration unavailable")
        if self._pending_previous is not None:
            raise RuntimeError("previous Host readiness cleanup is pending")
        previous = LoopPlaneHost(self._config, working_scope=self._profile_root)
        self._pending_previous = previous
        previous.enable_desktop_portable_snapshot()
        previous.list_sessions()
        return previous

    async def _discard_candidate(self, candidate: LoopPlaneHost) -> None:
        """Retain a discarded Host and its storage until both cleanups succeed."""

        self._candidate = candidate
        self._discard_candidate_storage = True
        if id(candidate) not in self._closed_host_ids:
            await candidate.aclose()
            self._closed_host_ids.add(id(candidate))
        self._remove_candidate_storage()
        self._candidate = None
        self._closed_host_ids.discard(id(candidate))

    def _remove_candidate_storage(self) -> None:
        if self._candidate_storage is not None:
            _remove_owned_tree(self._candidate_storage)
            self._candidate_storage = None
        self._discard_candidate_storage = False

    async def aclose(self) -> None:
        """Close every retained candidate/previous owner exactly once."""

        hosts: list[LoopPlaneHost] = []
        for candidate in (
            self._candidate,
            self._previous,
            self._pending_previous,
            self._host,
        ):
            if candidate is not None and candidate not in hosts:
                hosts.append(candidate)
        first_error: Exception | None = None
        for candidate in hosts:
            try:
                if id(candidate) not in self._closed_host_ids:
                    await candidate.aclose()
                    self._closed_host_ids.add(id(candidate))
                if candidate is self._candidate and self._discard_candidate_storage:
                    self._remove_candidate_storage()
                    self._candidate = None
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
        self._candidate = None
        self._candidate_config = None
        self._replace_current_host(None)
        self._previous = None
        self._pending_previous = None
        self._transaction_active = False
        self._candidate_installed = False
        self._previous_closed = False
        self._closed_host_ids.clear()

    def _materialize_candidate_storage(self, generation_dir: Path) -> Path:
        safe_generation = owned_generation_directory(
            self._profile_root,
            "generations",
            generation_dir.name,
        )
        if Path(generation_dir) != safe_generation:
            raise RuntimeError("candidate generation path is not profile-owned")
        generation_dir = safe_generation
        parent = owned_generation_parent(
            self._profile_root,
            "generation-storage",
            create=True,
        )
        storage = owned_generation_directory(
            self._profile_root,
            "generation-storage",
            generation_dir.name,
            allow_missing=True,
        )
        temporary = parent / f".{generation_dir.name}.{uuid.uuid4().hex}.tmp"
        temporary.mkdir(exist_ok=False)
        try:
            checkpoint = generation_dir / "sessions" / "checkpoints.sqlite3"
            if not _regular_file(checkpoint):
                raise RuntimeError("candidate checkpoint missing")
            _stream_copy(checkpoint, temporary / "checkpoints.sqlite3")
            artifacts = generation_dir / "artifacts"
            if artifacts.exists():
                if not _regular_directory(artifacts):
                    raise RuntimeError("candidate artifact layout invalid")
                for session_dir in artifacts.iterdir():
                    if not _regular_directory(session_dir):
                        raise RuntimeError("candidate artifact layout invalid")
                    destination = temporary / session_dir.name / "artifacts"
                    destination.mkdir(parents=True)
                    for member in session_dir.iterdir():
                        if not _regular_file(member):
                            raise RuntimeError("candidate artifact layout invalid")
                        _stream_copy(member, destination / member.name)
            publish_runtime_storage(temporary, storage)
        except Exception:
            _remove_owned_tree(temporary)
            _remove_owned_tree(storage)
            raise
        return storage


def _remove_owned_tree(path: Path) -> None:
    """Remove an exclusively-created runtime storage tree without link traversal."""

    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if is_link_or_reparse(info):
        raise OSError("refusing runtime reparse-point cleanup")
    if not stat.S_ISDIR(info.st_mode):
        path.unlink(missing_ok=True)
        return
    for child in path.iterdir():
        _remove_owned_tree(child)
    path.rmdir()


def _regular_file(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISREG(info.st_mode) and not bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _regular_directory(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISDIR(info.st_mode) and not bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _stream_copy(source: Path, destination: Path) -> None:
    read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    write_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    source_fd = os.open(source, read_flags)
    try:
        target_fd = os.open(destination, write_flags, 0o600)
        try:
            while chunk := os.read(source_fd, 1024 * 1024):
                view = memoryview(chunk)
                while view:
                    written = os.write(target_fd, view)
                    view = view[written:]
            os.fsync(target_fd)
        finally:
            os.close(target_fd)
    finally:
        os.close(source_fd)


def _missing_pointer_pristine_proof(root: Path, generation_id: str) -> dict[str, Any]:
    """Recover only an exact proof-before-pointer pristine publication."""

    generation_parent = owned_generation_parent(root, "generations", allow_missing=True)
    storage_parent = owned_generation_parent(
        root, "generation-storage", allow_missing=True
    )
    generation = owned_generation_directory(
        root, "generations", generation_id, allow_missing=True
    )
    runtime_storage = owned_generation_directory(
        root,
        "generation-storage",
        generation_id,
        allow_missing=True,
    )

    try:
        generation_parent_info = os.lstat(generation_parent)
    except FileNotFoundError:
        generation_parent_info = None
    if generation_parent_info is not None:
        with os.scandir(generation_parent) as entries:
            names = {entry.name for entry in entries}
        if names not in (set(), {generation_id}):
            raise ValueError("unexpected generation authority")

    try:
        storage_parent_info = os.lstat(storage_parent)
    except FileNotFoundError:
        storage_parent_info = None
    if storage_parent_info is not None:
        with os.scandir(storage_parent) as entries:
            if any(entries):
                raise ValueError("mutable storage exists without a current pointer")
    try:
        os.lstat(runtime_storage)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("mutable storage exists without a current pointer")

    try:
        os.lstat(generation)
    except FileNotFoundError:
        publish_pristine_generation(root, generation_id)
    else:
        with os.scandir(generation) as entries:
            names = {entry.name for entry in entries}
        if names != {"proof.json"}:
            raise ValueError("mutable profile exists without a current pointer")

    proof = read_proof(root, generation_id)
    if set(proof) != {
        "artifact_state",
        "checkpoint_state",
        "generation_id",
        "schema_version",
    }:
        raise ValueError("invalid pristine generation proof")
    result = validate_active_generation(
        proof,
        GenerationExpectation(
            checkpoint_state="absent_uninitialized",
            artifact_state="absent_uninitialized",
            schema_version=1,
        ),
    )
    if not result.ok or proof.get("generation_id") != generation_id:
        raise ValueError("invalid pristine generation proof")
    return proof


def _current_generation_filesystem_is_valid(
    root: Path,
    generation_id: str,
    *,
    schema_version: int,
) -> bool:
    try:
        generation_root = owned_generation_directory(root, "generations", generation_id)
        runtime_storage = owned_generation_directory(
            root,
            "generation-storage",
            generation_id,
            allow_missing=True,
        )
    except ValueError:
        return False
    nested_profile = generation_root / "profile" / "profile.json"
    profile_path = (
        nested_profile if nested_profile.exists() else generation_root / "profile.json"
    )
    source = {
        "profile_path": str(profile_path),
        "runtime_storage_root": str(runtime_storage),
    }
    for checkpoint_state, artifact_state in (
        ("absent_uninitialized", "absent_uninitialized"),
        ("initialized", "absent_uninitialized"),
        ("initialized", "initialized"),
    ):
        result = validate_active_generation(
            source,
            GenerationExpectation(
                checkpoint_state=checkpoint_state,
                artifact_state=artifact_state,
                schema_version=schema_version,
            ),
            provider=_CURRENT_GENERATION_PROVIDER,
        )
        if result.ok:
            return True
    return False


@dataclass
class DesktopRuntimeOwner:
    """Acquire ownership, publish/validate generation, then allow Host build."""

    profile_root: Path
    _lock: ProfileOwnershipLock | None = field(default=None, init=False, repr=False)
    _host: LoopPlaneHost | None = field(default=None, init=False, repr=False)
    _profile_state: ProfileState | None = field(default=None, init=False, repr=False)
    mutation_lease: ProfileMutationLease = field(
        default_factory=ProfileMutationLease, init=False
    )
    generation_id: str = "g0"
    bootstrapped: bool = field(default=False, init=False)

    def acquire(self) -> None:
        if self._lock is not None:
            return
        lock = ProfileOwnershipLock.for_root(self.profile_root)
        lock.acquire()
        self.profile_root = lock.root
        self._lock = lock

    def bootstrap_generation(self) -> dict[str, Any]:
        """Proof-before-pointer pristine bootstrap; zero Host construction."""

        if self._lock is None:
            raise RuntimeError("profile ownership lock required before bootstrap")
        try:
            recovered_generation = adjudicate_restore_recovery(self.profile_root)
        except RestoreRecoveryLocked as exc:
            raise RestoreJournalsPresent("restore recovery locked") from exc
        if recovered_generation is not None:
            if not is_canonical_generation_id(recovered_generation):
                raise RestoreJournalsPresent("restore generation id is invalid")
            self.generation_id = recovered_generation
            self.bootstrapped = True
            self._profile_state = ProfileState.open(
                self.profile_root, generation_id=self.generation_id
            )
            return {"generation_id": self.generation_id, "ok": True}

        try:
            pointer_exists = current_generation_pointer_exists(self.profile_root)
        except ValueError as exc:
            raise RuntimeError("invalid current-generation pointer") from exc
        if not pointer_exists:
            if not is_canonical_generation_id(self.generation_id):
                raise RuntimeError("invalid generation id")
            try:
                _missing_pointer_pristine_proof(self.profile_root, self.generation_id)
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    "missing current-generation state is unsafe"
                ) from exc
            complete_pointer(self.profile_root, self.generation_id)
        else:
            try:
                gen_id = read_current_generation(self.profile_root)
            except (OSError, ValueError) as exc:
                raise RuntimeError("invalid current-generation pointer") from exc
            self.generation_id = gen_id
            try:
                proof = read_proof(self.profile_root, gen_id)
            except (OSError, ValueError) as exc:
                raise RuntimeError("unsafe generation path") from exc
            ck = proof.get("checkpoint_state", "absent_uninitialized")
            ak = proof.get("artifact_state", "absent_uninitialized")
            if ck not in ("absent_uninitialized", "initialized"):
                raise RuntimeError("invalid checkpoint_state in proof")
            if ak not in ("absent_uninitialized", "initialized"):
                raise RuntimeError("invalid artifact_state in proof")
            schema = proof.get("schema_version")
            schema_version = int(schema) if schema is not None else None
            result = validate_active_generation(
                proof,
                GenerationExpectation(
                    checkpoint_state=ck,
                    artifact_state=ak,
                    schema_version=schema_version,
                ),
            )
            if not result.ok or proof.get("generation_id") != gen_id:
                raise RuntimeError(f"generation validation failed: {result.reason}")
            if schema_version is None or not _current_generation_filesystem_is_valid(
                self.profile_root,
                gen_id,
                schema_version=schema_version,
            ):
                raise RuntimeError("generation path or filesystem validation failed")

        self.bootstrapped = True
        # Portable identity under generation; device-private lock remains external.
        self._profile_state = ProfileState.open(
            self.profile_root, generation_id=self.generation_id
        )
        return {"generation_id": self.generation_id, "ok": True}

    def ensure_profile_state(self) -> ProfileState:
        if self._lock is None or not self.bootstrapped:
            raise RuntimeError("bootstrap required before profile state")
        if self._profile_state is None:
            self._profile_state = ProfileState.open(
                self.profile_root, generation_id=self.generation_id
            )
        return self._profile_state

    def attach_host(self, config: RuntimeConfig) -> LoopPlaneHost:
        if self._lock is None or not self.bootstrapped:
            raise RuntimeError("bootstrap required before Host construction")
        self.ensure_profile_state()
        if config.storage is None or not isinstance(
            config.storage.authority, DesktopStorageAuthorityFactory
        ):
            raise RuntimeError("runtime storage authority is unsafe")
        try:
            expected_storage = owned_generation_directory(
                self.profile_root,
                "generation-storage",
                self.generation_id,
            )
        except ValueError as exc:
            raise RuntimeError("runtime storage authority is unsafe") from exc
        if tuple(Path(config.storage.root).parts) != tuple(expected_storage.parts):
            raise RuntimeError("runtime storage authority is unsafe")
        if not DesktopRuntimeStorageInitializer().validate(
            expected_storage
        ).ok or not _current_generation_filesystem_is_valid(
            self.profile_root,
            self.generation_id,
            schema_version=1,
        ):
            raise RuntimeError("runtime storage authority is invalid")
        if self._host is None:
            self._host = LoopPlaneHost(config, working_scope=self.profile_root)
            # The Host keeps storage paths/private handles encapsulated while
            # Desktop explicitly opts into the portable-snapshot provider.
            self._host.enable_desktop_portable_snapshot()
        return self._host

    def adopt_handover_host(self, host: LoopPlaneHost | None) -> None:
        """Track the sole current Host selected by the runtime handover owner."""

        if self._lock is None:
            raise RuntimeError("profile ownership lock is not held")
        self._host = host

    @property
    def host(self) -> LoopPlaneHost | None:
        return self._host

    async def close_host(self) -> None:
        """Close and forget the directly attached current Host before release."""

        host = self._host
        if host is None:
            return
        await host.aclose()
        if self._host is host:
            self._host = None

    @property
    def profile_state(self) -> ProfileState | None:
        return self._profile_state

    def release(self) -> None:
        if self._host is not None:
            raise RuntimeError("runtime Host must be closed before ownership release")
        self._profile_state = None
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        self.bootstrapped = False
