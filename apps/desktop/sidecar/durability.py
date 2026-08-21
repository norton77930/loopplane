"""Platform-scoped generation publication and restore recovery (078 T025/T078)."""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import stat
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from loopplane.host import (
    DesktopActiveGenerationProvider,
    DesktopRuntimeStorageInitializer,
    GenerationExpectation,
    validate_active_generation,
)

if TYPE_CHECKING:
    from restore import RestoreManager, RestoreReservation

_GenerationState = Literal["absent_uninitialized", "initialized"]
_ACTIVE_GENERATION_PROVIDER = DesktopActiveGenerationProvider()
_MAX_GENERATION_CONTROL_BYTES = 8 * 1024 * 1024
_PROOF_KEYS = frozenset(
    {
        "active_generation",
        "active_pointer_bytes_b64",
        "active_pointer_sha256",
        "generation_publication_receipt",
        "generation_receipt_sha256",
        "proof_kind",
        "proof_sequence",
        "proof_version",
        "record_sha256",
        "restore_id",
        "verified_at",
    }
)
_RECEIPT_KEYS = frozenset(
    {
        "artifact_state",
        "checkpoint_state",
        "generation_id",
        "platform",
        "publication_nonce",
        "publication_sequence",
        "receipt_version",
        "schema_version",
        "validation_digest",
    }
)
_JOURNAL_KEYS = frozenset(
    {
        "archive_sha256",
        "candidate_generation",
        "candidate_generation_publication_receipt",
        "candidate_generation_receipt_sha256",
        "candidate_pointer_bytes_b64",
        "candidate_pointer_sha256",
        "candidate_proof_sha256",
        "journal_sequence",
        "journal_version",
        "previous_generation",
        "previous_pointer_bytes_b64",
        "previous_pointer_sha256",
        "previous_proof_bytes_b64",
        "previous_proof_sha256",
        "record_sha256",
        "restore_id",
        "slot",
        "state",
        "updated_at",
    }
)
_JOURNAL_STATE_SEQUENCE = {"prepared": 1, "published": 2, "verified": 3}
_POINTER_KEYS = frozenset({"generation_id", "receipt_sha256"})
_GENERATION_ID_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_WINDOWS_RESERVED_GENERATION_IDS = frozenset(
    {"aux", "con", "nul", "prn"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


class DurabilityUnsupported(RuntimeError):
    """The active filesystem cannot satisfy its required durability contract."""


class RestorePublicationFailed(RuntimeError):
    """Publication failed before active authority could change."""


class RestoreRolledBack(RuntimeError):
    """Publication began and exact prior authority was restored."""


class RestoreRecoveryLocked(RuntimeError):
    """No independently provable generation may be opened."""


class ProofEffectUncertain(RuntimeError):
    """Proof may have become durable; only a later startup may adjudicate it."""

    def __init__(self, generation_id: str) -> None:
        super().__init__("restore proof effect is uncertain")
        self.generation_id = generation_id


class PostProofCommitError(RuntimeError):
    """Candidate proof is authoritative but resumable cleanup did not finish."""

    def __init__(self, generation_id: str) -> None:
        super().__init__("restore proof is authoritative but cleanup failed")
        self.generation_id = generation_id


class _DurableReplaceEffectUncertain(OSError):
    """A replace occurred, but its required flush acknowledgement failed."""


@dataclass(frozen=True)
class RestoreCommit:
    generation_id: str
    generation_dir: Path


def fsync_path(path: Path) -> None:
    """Flush one regular file, propagating every required durability failure."""

    if not _regular_file(path):
        raise OSError(f"durability target is not a regular file: {path.name}")
    if sys.platform == "win32":
        _windows_flush_regular_file(path)
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_pristine_generation(root: Path, generation_id: str = "g0") -> Path:
    """Write proof-before-pointer pristine absent-uninitialized receipt."""

    gen = owned_generation_directory(
        root,
        "generations",
        generation_id,
        create=True,
    )
    proof = gen / "proof.json"
    payload: dict[str, Any] = {
        "generation_id": generation_id,
        "checkpoint_state": "absent_uninitialized",
        "artifact_state": "absent_uninitialized",
        "schema_version": 1,
    }
    _durable_replace(proof, _canonical(payload))
    result = validate_active_generation(
        payload,
        GenerationExpectation(
            checkpoint_state="absent_uninitialized",
            artifact_state="absent_uninitialized",
            schema_version=1,
        ),
    )
    if not result.ok:
        raise RuntimeError(f"pristine generation proof rejected: {result.reason}")
    return proof


def complete_pointer(root: Path, generation_id: str) -> Path:
    if not is_canonical_generation_id(generation_id):
        raise ValueError("invalid generation id")
    pointer = root / "current-generation"
    _durable_replace(pointer, (generation_id + "\n").encode())
    return pointer


def current_generation_pointer_exists(root: Path) -> bool:
    """Distinguish a missing pointer from every unsafe existing entry type."""

    pointer = _exact_child_path(Path(root), "current-generation")
    if pointer is None:
        return False
    try:
        info = os.lstat(pointer)
    except OSError as exc:
        raise ValueError("invalid current-generation pointer") from exc
    if not stat.S_ISREG(info.st_mode) or is_link_or_reparse(info):
        raise ValueError("invalid current-generation pointer")
    return True


def read_current_generation(root: Path) -> str:
    """Read the exact durable representation written by ``complete_pointer``."""

    if not current_generation_pointer_exists(root):
        raise ValueError("current-generation pointer is missing")
    raw = _read_owned_regular(
        Path(root), "current-generation", _MAX_GENERATION_CONTROL_BYTES
    )
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid current-generation pointer") from exc
    if not value.endswith("\n"):
        raise ValueError("invalid current-generation pointer")
    generation_id = value[:-1]
    if not is_canonical_generation_id(generation_id) or raw != (
        generation_id + "\n"
    ).encode("utf-8"):
        raise ValueError("invalid current-generation pointer")
    return generation_id


def read_proof(root: Path, generation_id: str) -> dict[str, Any]:
    generation = owned_generation_directory(root, "generations", generation_id)
    raw = _read_owned_regular(generation, "proof.json", _MAX_GENERATION_CONTROL_BYTES)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid generation proof") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid generation proof")
    return payload


def validate_proof(
    root: Path,
    generation_id: str,
    *,
    expectation: GenerationExpectation | None = None,
) -> bool:
    payload = read_proof(root, generation_id)
    exp = expectation or GenerationExpectation(
        checkpoint_state="absent_uninitialized",
        artifact_state="absent_uninitialized",
        schema_version=int(payload.get("schema_version", 1)),
    )
    return validate_active_generation(payload, exp).ok


def has_restore_journals(root: Path) -> bool:
    root = Path(root)
    return (
        any(
            (root / name).is_file()
            for name in ("restore-journal-a.json", "restore-journal-b.json")
        )
        or (root / "journals").exists()
    )


def platform_claim() -> str:
    if sys.platform == "win32":
        return "windows_process_crash"
    return "posix_physical_power_loss"


async def commit_restore(
    root: Path,
    reservation: RestoreReservation,
    manager: RestoreManager,
    *,
    candidate_ready: Callable[[Path], object] | None = None,
    close_previous: Callable[[], object] | None = None,
    install_candidate: Callable[[Path], object] | None = None,
    commit_candidate: Callable[[], object] | None = None,
    rollback_candidate: Callable[[], object] | None = None,
    lock_dispatch: Callable[[], object] | None = None,
    unlock_dispatch_after_rollback: Callable[[], object] | None = None,
) -> RestoreCommit:
    """Publish one candidate with recoverable runtime and durable authority.

    The forwarding facade is switched before the proof so the durable proof never
    names an unready Host.  A definitive pre-proof error compensates that switch,
    restores the exact durable preimage, then discards the unreferenced candidate.
    Once proof acknowledgement can be ambiguous, startup is the only adjudicator.
    """

    if not manager.revalidate_archive(reservation):
        raise ValueError("restore archive identity changed")
    root = Path(root)
    try:
        previous_pointer = _read_bytes(root / "active-generation.json")
        previous_proof = _read_bytes(root / "active-generation-proof.json")
    except (OSError, ValueError) as exc:
        raise RestoreRecoveryLocked("restore authority files are unsafe") from exc
    previous_generation = _generation_from_pointer(previous_pointer) or "g0"
    generation_id = f"restore-{uuid.uuid4().hex}"
    proof_written = False
    publication_started = False
    candidate_dir: Path | None = root / "generations" / generation_id
    try:
        candidate_dir, receipt, receipt_digest = _publish_candidate(
            root, reservation.staging_dir, generation_id, manager
        )
        candidate_pointer = _canonical(
            {"generation_id": generation_id, "receipt_sha256": receipt_digest}
        )
        _write_journal_pair(
            root,
            manager,
            previous_generation=previous_generation,
            previous_pointer=previous_pointer,
            previous_proof=previous_proof,
            candidate_generation=generation_id,
            candidate_pointer=candidate_pointer,
            receipt=receipt,
            receipt_digest=receipt_digest,
        )
        manager.hit("recovery.candidate_pointer_before_replace")
        publication_started = True
        _durable_replace(root / "active-generation.json", candidate_pointer)
        manager.hit("recovery.published_slot_copy_on_write")
        _write_journal(
            root / "restore-journal-b.json",
            _journal(
                slot="b",
                state="published",
                sequence=2,
                previous_generation=previous_generation,
                previous_pointer=previous_pointer,
                previous_proof=previous_proof,
                candidate_generation=generation_id,
                candidate_pointer=candidate_pointer,
                receipt=receipt,
                receipt_digest=receipt_digest,
            ),
        )
        manager.hit("recovery.candidate_host_readiness")
        if candidate_ready is not None:
            await _maybe_await(candidate_ready(candidate_dir))
        manager.hit("recovery.old_host_close")
        if close_previous is not None:
            await _maybe_await(close_previous())
        manager.hit("recovery.runtime_owner_swap")
        if install_candidate is not None:
            await _maybe_await(install_candidate(candidate_dir))
        proof = _proof(generation_id, candidate_pointer, receipt, receipt_digest)
        proof_payload = _canonical(proof)
        manager.hit("recovery.proof_before_replace")
        try:
            _durable_replace(root / "active-generation-proof.json", proof_payload)
        except _DurableReplaceEffectUncertain as exc:
            raise ProofEffectUncertain(generation_id) from exc
        try:
            reread_proof = _read_bytes(root / "active-generation-proof.json")
        except (OSError, ValueError) as exc:
            raise ProofEffectUncertain(generation_id) from exc
        if reread_proof != proof_payload or (
            install_candidate is not None
            and not _proof_is_authoritative(root, reread_proof, candidate_pointer)
        ):
            raise ProofEffectUncertain(generation_id)
        proof_written = True
        try:
            manager.hit("recovery.proof_effect_before_acknowledgement")
        except OSError as exc:
            raise ProofEffectUncertain(generation_id) from exc
        if commit_candidate is not None:
            await _maybe_await(commit_candidate())
        manager.hit("recovery.verified_slot_copy_on_write")
        _write_journal(
            root / "restore-journal-a.json",
            _journal(
                slot="a",
                state="verified",
                sequence=3,
                previous_generation=previous_generation,
                previous_pointer=previous_pointer,
                previous_proof=previous_proof,
                candidate_generation=generation_id,
                candidate_pointer=candidate_pointer,
                receipt=receipt,
                receipt_digest=receipt_digest,
            ),
        )
        _cleanup_verified(root, manager)
        return RestoreCommit(generation_id, candidate_dir)
    except ProofEffectUncertain:
        try:
            if lock_dispatch is not None:
                await _maybe_await(lock_dispatch())
        except Exception as lock_exc:
            raise RestoreRecoveryLocked(
                "restore proof ambiguity could not lock runtime dispatch"
            ) from lock_exc
        raise
    except Exception as exc:
        if proof_written:
            raise PostProofCommitError(generation_id) from exc
        try:
            if lock_dispatch is not None:
                await _maybe_await(lock_dispatch())
            if rollback_candidate is not None:
                await _maybe_await(rollback_candidate())
            _restore_exact_previous(root, previous_pointer, previous_proof)
            if previous_pointer and not _proof_is_authoritative(
                root, previous_proof, previous_pointer
            ):
                raise RestoreRecoveryLocked(
                    "previous restore authority is not valid after rollback"
                )
            if candidate_dir is not None:
                _remove_candidate_generation(candidate_dir)
            _cleanup_recovered_rollback(root)
            if unlock_dispatch_after_rollback is not None:
                await _maybe_await(unlock_dispatch_after_rollback())
        except Exception as rollback_exc:
            raise RestoreRecoveryLocked(
                "restore rollback could not prove prior authority"
            ) from rollback_exc
        if isinstance(exc, DurabilityUnsupported):
            raise
        if not isinstance(exc, (OSError, RuntimeError, ValueError)):
            raise
        if publication_started:
            raise RestoreRolledBack("restore publication rolled back") from exc
        raise RestorePublicationFailed("restore publication failed") from exc


def adjudicate_restore_recovery(root: Path) -> str | None:
    """Startup-only authority decision for active proof and dual COW slots."""

    root = Path(root)
    try:
        pointer = _read_bytes(root / "active-generation.json")
        proof = _read_bytes(root / "active-generation-proof.json")
    except (OSError, ValueError) as exc:
        raise RestoreRecoveryLocked("restore authority files are unsafe") from exc
    journal_paths = [
        root / "restore-journal-a.json",
        root / "restore-journal-b.json",
    ]
    slots = [_parse_journal(path) for path in journal_paths]
    if any(
        _checksum_valid_incompatible_journal(path, slot)
        for path, slot in zip(journal_paths, slots, strict=True)
    ):
        raise RestoreRecoveryLocked("checksum-valid restore journal is incompatible")
    valid = [slot for slot in slots if slot is not None]

    if _proof_is_authoritative(root, proof, pointer):
        # Matching proof wins only when every surviving checksum-valid journal
        # belongs to the same restore lineage; torn bytes carry no authority.
        if any(
            not _journal_matches_authoritative_proof(slot, proof, pointer)
            for slot in valid
        ) or (len(valid) == 2 and not _consistent_journal_lineage(valid[0], valid[1])):
            raise RestoreRecoveryLocked("restore journal conflicts with active proof")
        _cleanup_recovered_authority(root)
        return _generation_from_pointer(pointer)
    if _proof_claims_pointer(proof, pointer):
        raise RestoreRecoveryLocked("active restore proof is not independently valid")

    candidate: dict[str, Any] | None = None
    if len(valid) == 1 and valid[0].get("state") in {"prepared", "published"}:
        candidate = valid[0]
    elif len(valid) == 2 and _consistent_preproof_slots(valid[0], valid[1]):
        candidate = valid[0]
    elif (
        has_restore_journals(root)
        or pointer
        or proof
        or _has_retained_restore_generation(root)
    ):
        raise RestoreRecoveryLocked("restore journals lack recovery authority")
    else:
        return None

    assert candidate is not None
    candidate_pointer = _decode_record(candidate, "candidate_pointer_bytes_b64")
    previous_pointer = _decode_record(candidate, "previous_pointer_bytes_b64")
    if pointer not in {candidate_pointer, previous_pointer}:
        raise RestoreRecoveryLocked("restore journal does not match active pointer")
    previous_proof = _decode_record(candidate, "previous_proof_bytes_b64")
    candidate_generation = candidate.get("candidate_generation")
    if not isinstance(candidate_generation, str):
        raise RestoreRecoveryLocked("restore candidate generation is invalid")
    try:
        _restore_exact_previous(root, previous_pointer, previous_proof)
        if previous_pointer and not _proof_is_authoritative(
            root, previous_proof, previous_pointer
        ):
            raise RestoreRecoveryLocked("previous restore authority is not valid")
        _cleanup_recovered_rollback(root, candidate_generation)
    except RestoreRecoveryLocked:
        raise
    except Exception as exc:
        raise RestoreRecoveryLocked(
            "abandoned restore candidate cleanup failed"
        ) from exc
    return _generation_from_pointer(previous_pointer)


def is_canonical_generation_id(value: object) -> bool:
    """Accept one portable path component with no Windows filesystem aliases."""

    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value[0] != "-"
        and value[-1] != "-"
        and "--" not in value
        and all(character in _GENERATION_ID_CHARACTERS for character in value)
        and value not in _WINDOWS_RESERVED_GENERATION_IDS
    )


def is_link_or_reparse(info: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _exact_child_path(parent: Path, name: str) -> Path | None:
    """Resolve an existing child only when its preserved name is byte-for-byte exact."""

    try:
        with os.scandir(parent) as entries:
            exact = any(entry.name == name for entry in entries)
    except OSError as exc:
        raise ValueError("unsafe generation path") from exc
    candidate = parent / name
    if exact:
        return candidate
    try:
        os.lstat(candidate)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("unsafe generation path") from exc
    raise ValueError("unsafe generation path alias")


def _read_owned_regular(parent: Path, name: str, limit: int) -> bytes:
    """Boundedly read one exact, non-reparse child through a stable descriptor."""

    try:
        parent_before = os.lstat(parent)
        path = _exact_child_path(parent, name)
        if path is None:
            raise ValueError("owned regular file is missing")
        before = os.lstat(path)
    except OSError as exc:
        raise ValueError("owned regular file is unsafe") from exc
    if (
        not stat.S_ISDIR(parent_before.st_mode)
        or is_link_or_reparse(parent_before)
        or not stat.S_ISREG(before.st_mode)
        or is_link_or_reparse(before)
        or before.st_size > limit
    ):
        raise ValueError("owned regular file is unsafe")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    chunks: list[bytes] = []
    size = 0
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("owned regular file is unsafe") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or is_link_or_reparse(opened)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            raise ValueError("owned regular file identity changed")
        while chunk := os.read(
            descriptor,
            min(1024 * 1024, limit + 1 - size),
        ):
            size += len(chunk)
            if size > limit or size > before.st_size:
                raise ValueError("owned regular file is oversized")
            chunks.append(chunk)
    except OSError as exc:
        raise ValueError("owned regular file is unsafe") from exc
    finally:
        os.close(descriptor)

    try:
        after = os.lstat(path)
        parent_after = os.lstat(parent)
        exact = _exact_child_path(parent, name)
    except OSError as exc:
        raise ValueError("owned regular file is unsafe") from exc
    if (
        exact != path
        or size != before.st_size
        or not stat.S_ISREG(after.st_mode)
        or is_link_or_reparse(after)
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
        or after.st_size != before.st_size
        or not stat.S_ISDIR(parent_after.st_mode)
        or is_link_or_reparse(parent_after)
        or parent_after.st_dev != parent_before.st_dev
        or parent_after.st_ino != parent_before.st_ino
    ):
        raise ValueError("owned regular file identity changed")
    return b"".join(chunks)


def owned_generation_parent(
    root: Path,
    collection: str,
    *,
    create: bool = False,
    allow_missing: bool = False,
) -> Path:
    """Return one profile-owned non-reparse generation collection directory."""

    if collection not in {"generations", "generation-storage"}:
        raise ValueError("invalid generation collection")
    try:
        canonical_root = Path(root).resolve(strict=True)
        root_info = os.lstat(canonical_root)
    except OSError as exc:
        raise ValueError("unsafe generation path") from exc
    if not stat.S_ISDIR(root_info.st_mode) or is_link_or_reparse(root_info):
        raise ValueError("unsafe generation path")

    parent = _exact_child_path(canonical_root, collection)
    if parent is None:
        parent = canonical_root / collection
        if create:
            try:
                os.mkdir(parent)
            except FileExistsError:
                pass
            parent = _exact_child_path(canonical_root, collection)
            if parent is None:
                raise ValueError("generation collection creation failed")
        elif allow_missing:
            return parent
        else:
            raise ValueError("generation collection is missing")
    try:
        parent_info = os.lstat(parent)
    except OSError as exc:
        raise ValueError("unsafe generation path") from exc
    if not stat.S_ISDIR(parent_info.st_mode) or is_link_or_reparse(parent_info):
        raise ValueError("unsafe generation path")
    return parent


def owned_generation_directory(
    root: Path,
    collection: str,
    generation_id: str,
    *,
    create: bool = False,
    allow_missing: bool = False,
) -> Path:
    """Return one canonical generation directory without following aliases."""

    if not is_canonical_generation_id(generation_id):
        raise ValueError("invalid generation id")
    parent = owned_generation_parent(
        root,
        collection,
        create=create,
        allow_missing=allow_missing,
    )
    try:
        os.lstat(parent)
    except FileNotFoundError:
        if allow_missing:
            return parent / generation_id
        raise ValueError("generation collection is missing") from None
    generation = _exact_child_path(parent, generation_id)
    if generation is None:
        generation = parent / generation_id
        if create:
            try:
                os.mkdir(generation)
            except FileExistsError:
                pass
            generation = _exact_child_path(parent, generation_id)
            if generation is None:
                raise ValueError("generation directory creation failed")
        elif allow_missing:
            return generation
        else:
            raise ValueError("generation directory is missing")
    try:
        generation_info = os.lstat(generation)
    except OSError as exc:
        raise ValueError("unsafe generation path") from exc
    if not stat.S_ISDIR(generation_info.st_mode) or is_link_or_reparse(generation_info):
        raise ValueError("unsafe generation path")
    return generation


def initialize_runtime_storage(root: Path, generation_id: str) -> Path:
    """Publish one Host-initialized storage tree before serving first use."""

    if not is_canonical_generation_id(generation_id):
        raise ValueError("invalid generation id")
    parent = owned_generation_parent(root, "generation-storage", create=True)
    destination = owned_generation_directory(
        root,
        "generation-storage",
        generation_id,
        allow_missing=True,
    )
    initializer = DesktopRuntimeStorageInitializer()
    try:
        info = os.lstat(destination)
    except FileNotFoundError:
        info = None
    if info is not None:
        if not stat.S_ISDIR(info.st_mode) or is_link_or_reparse(info):
            raise ValueError("runtime storage path is unsafe")
        result = initializer.validate(destination)
        if not result.ok:
            raise ValueError("runtime storage is invalid")
        return destination

    temporary = parent / f".{generation_id}.{uuid.uuid4().hex}.initialize"
    try:
        os.mkdir(temporary, 0o700)
        temporary_info = os.lstat(temporary)
        if not stat.S_ISDIR(temporary_info.st_mode) or is_link_or_reparse(
            temporary_info
        ):
            raise ValueError("runtime storage staging is unsafe")
        result = initializer.initialize(temporary)
        if not result.ok:
            raise ValueError("runtime storage initialization failed")
        publish_runtime_storage(temporary, destination)
        destination = owned_generation_directory(
            root, "generation-storage", generation_id
        )
        if not initializer.validate(destination).ok:
            raise ValueError("runtime storage publication is invalid")
        return destination
    finally:
        _remove_candidate_generation(temporary)


def _safe_generation_component(value: str) -> bool:
    return is_canonical_generation_id(value)


def _has_retained_restore_generation(root: Path) -> bool:
    for name in ("generations", "generation-storage"):
        parent = root / name
        try:
            info = os.lstat(parent)
        except FileNotFoundError:
            continue
        except OSError:
            return True
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & reparse
        ):
            return True
        try:
            if any(child.name.startswith("restore-") for child in parent.iterdir()):
                return True
        except OSError:
            return True
    return False


def _publish_candidate(
    root: Path,
    staging: Path,
    generation_id: str,
    manager: RestoreManager,
) -> tuple[Path, dict[str, Any], str]:
    """Publish through the active platform's concrete durability adapter."""

    generations = owned_generation_parent(root, "generations", create=True)
    if staging.stat().st_dev != generations.stat().st_dev:
        raise ValueError("candidate volume differs from generations")
    if not _regular_file(staging / "profile" / "profile.json"):
        raise ValueError("candidate profile missing")
    candidate = owned_generation_directory(
        root,
        "generations",
        generation_id,
        allow_missing=True,
    )
    try:
        os.lstat(candidate)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("candidate generation already exists")
    if sys.platform == "win32":
        _publish_candidate_windows(staging, candidate, manager)
    else:
        _publish_candidate_posix(staging, candidate, manager)
    checkpoint_state, artifact_state = _require_valid_candidate_inventory(candidate)
    receipt = {
        "artifact_state": artifact_state,
        "checkpoint_state": checkpoint_state,
        "generation_id": generation_id,
        "platform": platform_claim(),
        "publication_nonce": uuid.uuid4().hex,
        "publication_sequence": 1,
        "receipt_version": 1,
        "schema_version": 1,
        "validation_digest": hashlib.sha256(b"restore-validation").hexdigest(),
    }
    receipt_digest = hashlib.sha256(_canonical(receipt)).hexdigest()
    result = validate_active_generation(
        receipt,
        GenerationExpectation(
            checkpoint_state=checkpoint_state,
            artifact_state=artifact_state,
            schema_version=1,
        ),
    )
    if not result.ok:
        raise RuntimeError("candidate receipt rejected")
    return candidate, receipt, receipt_digest


def _publish_candidate_posix(
    staging: Path, candidate: Path, manager: RestoreManager
) -> None:
    manager.hit("posix.file_fsync")
    _fsync_regular_tree(staging)
    manager.hit("posix.bottom_up_directory_fsync")
    _fsync_directories_bottom_up(staging)
    manager.hit("posix.same_volume_rename")
    os.replace(staging, candidate)
    manager.hit("posix.former_staging_parent_fsync")
    _fsync_directory(staging.parent)
    manager.hit("posix.generations_parent_fsync")
    _fsync_directory(candidate.parent)
    manager.hit("posix.reopen_inventory_schema_sqlite_artifact_validation")
    _require_valid_candidate_inventory(candidate)


def _publish_candidate_windows(
    staging: Path, candidate: Path, manager: RestoreManager
) -> None:
    manager.hit("windows.supported_local_ntfs_refs_check")
    try:
        supported = _windows_supported_local_volume(
            staging
        ) and _windows_supported_local_volume(candidate.parent)
    except OSError:
        manager.hit("windows.native_api_failure")
        raise
    if not supported or staging.stat().st_dev != candidate.parent.stat().st_dev:
        manager.hit("windows.remote_or_unsupported_volume")
        raise DurabilityUnsupported("windows durability volume is unsupported")
    try:
        manager.hit("windows.regular_file_flush_file_buffers")
        _fsync_regular_tree(staging)
        manager.hit("windows.same_volume_write_through_move")
        _windows_move_write_through(staging, candidate)
        manager.hit("windows.post_move_reopen_validation")
        _require_valid_candidate_inventory(candidate)
    except OSError:
        # Native flush/move/reopen errors are mandatory failure paths, never a
        # downgrade to ordinary os.replace semantics.
        manager.hit("windows.native_api_failure")
        raise
    manager.hit("windows.process_crash_acknowledgement_boundary")


def publish_runtime_storage(staging: Path, destination: Path) -> None:
    """Durably publish the exact mutable storage tree before restore proof."""

    staging = Path(staging)
    destination = Path(destination)
    if (
        destination.exists()
        or staging.stat().st_dev != destination.parent.stat().st_dev
    ):
        raise OSError("runtime storage destination is unavailable")
    _require_valid_runtime_storage(staging)
    if sys.platform == "win32":
        if not (
            _windows_supported_local_volume(staging)
            and _windows_supported_local_volume(destination.parent)
        ):
            raise OSError("windows runtime storage volume is unsupported")
        _fsync_regular_tree(staging)
        _windows_move_write_through(staging, destination)
        _require_valid_runtime_storage(destination)
        return
    _fsync_regular_tree(staging)
    _fsync_directories_bottom_up(staging)
    os.replace(staging, destination)
    _fsync_directory(staging.parent)
    _require_valid_runtime_storage(destination)


def _validate_desktop_source(
    source: dict[str, str],
    *,
    artifact_state: _GenerationState | None = None,
) -> tuple[_GenerationState, _GenerationState]:
    artifact_states: tuple[_GenerationState, ...] = (
        (artifact_state,)
        if artifact_state is not None
        else ("absent_uninitialized", "initialized")
    )
    for expected_artifact_state in artifact_states:
        result = validate_active_generation(
            source,
            GenerationExpectation(
                checkpoint_state="initialized",
                artifact_state=expected_artifact_state,
                schema_version=1,
            ),
            provider=_ACTIVE_GENERATION_PROVIDER,
        )
        if result.ok:
            return "initialized", expected_artifact_state
    raise RuntimeError("Host active-generation validation failed")


def _require_valid_runtime_storage(
    storage: Path,
    *,
    artifact_state: _GenerationState | None = None,
) -> tuple[_GenerationState, _GenerationState]:
    return _validate_desktop_source(
        {"runtime_storage_root": str(Path(storage))},
        artifact_state=artifact_state,
    )


def _windows_kernel32() -> Any:
    """Return typed Win32 durability APIs so HANDLEs are never truncated."""

    if sys.platform != "win32":
        raise OSError("Windows durability API requested on non-Windows platform")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetDriveTypeW.restype = wintypes.UINT
    kernel32.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeInformationW.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.MoveFileExW.restype = wintypes.BOOL
    return kernel32


def _windows_supported_local_volume(path: Path) -> bool:
    """Accept only local NTFS/ReFS volumes; native query errors are failures."""

    if sys.platform != "win32":
        return False
    import ctypes

    resolved = Path(path).resolve()
    drive = resolved.drive
    if not drive:
        return False
    root = drive + "\\"
    kernel32 = _windows_kernel32()
    drive_type = kernel32.GetDriveTypeW(root)
    # DRIVE_FIXED is the only supported local durability class; reject remote,
    # removable, and unknown paths rather than silently downgrading guarantees.
    if drive_type != 3:
        return False
    filesystem = ctypes.create_unicode_buffer(261)
    ok = kernel32.GetVolumeInformationW(
        root, None, 0, None, None, None, filesystem, len(filesystem)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return filesystem.value.upper() in {"NTFS", "REFS"}


def _windows_flush_regular_file(path: Path) -> None:
    """Call Windows FlushFileBuffers for one regular publication file."""

    if sys.platform != "win32":
        raise OSError("Windows flush requested on non-Windows platform")
    if not _regular_file(path):
        raise OSError(f"Windows flush target is not regular: {path.name}")
    import ctypes
    import msvcrt

    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        handle = msvcrt.get_osfhandle(descriptor)
        kernel32 = _windows_kernel32()
        if not kernel32.FlushFileBuffers(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        os.close(descriptor)


def _windows_move_write_through(source: Path, destination: Path) -> None:
    """Move one same-volume candidate with MOVEFILE_WRITE_THROUGH."""

    if sys.platform != "win32":
        raise OSError("Windows move requested on non-Windows platform")
    import ctypes

    kernel32 = _windows_kernel32()
    if not kernel32.MoveFileExW(str(source), str(destination), 0x00000008):
        raise ctypes.WinError(ctypes.get_last_error())


def _regular_file(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISREG(info.st_mode) and not bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _fsync_regular_tree(root: Path) -> None:
    for item in sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True):
        if _regular_file(item):
            fsync_path(item)


def _fsync_directories_bottom_up(root: Path) -> None:
    for item in sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True):
        if item.is_dir() and not item.is_symlink():
            _fsync_directory(item)
    _fsync_directory(root)


def _require_valid_candidate_inventory(
    candidate: Path,
    *,
    artifact_state: _GenerationState | None = None,
) -> tuple[_GenerationState, _GenerationState]:
    """Validate an inactive generation only through the public Host facade."""

    return _validate_desktop_source(
        {"generation_root": str(Path(candidate))},
        artifact_state=artifact_state,
    )


def _write_journal_pair(
    root: Path,
    manager: RestoreManager,
    **values: Any,
) -> None:
    manager.hit("recovery.prepared_a_temp_write_flush_replace_reread")
    _write_journal(
        root / "restore-journal-a.json",
        _journal(slot="a", state="prepared", sequence=1, **values),
    )
    manager.hit("recovery.prepared_b_temp_write_flush_replace_reread")
    _write_journal(
        root / "restore-journal-b.json",
        _journal(slot="b", state="prepared", sequence=1, **values),
    )


def _journal(
    *,
    slot: str,
    state: str,
    sequence: int,
    previous_generation: str,
    previous_pointer: bytes,
    previous_proof: bytes,
    candidate_generation: str,
    candidate_pointer: bytes,
    receipt: dict[str, Any],
    receipt_digest: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "archive_sha256": hashlib.sha256(b"selected-archive").hexdigest(),
        "candidate_generation": candidate_generation,
        "candidate_generation_publication_receipt": receipt,
        "candidate_generation_receipt_sha256": receipt_digest,
        "candidate_pointer_bytes_b64": base64.b64encode(candidate_pointer).decode(),
        "candidate_pointer_sha256": hashlib.sha256(candidate_pointer).hexdigest(),
        "candidate_proof_sha256": None,
        "journal_sequence": sequence,
        "journal_version": 1,
        "previous_generation": previous_generation,
        "previous_pointer_bytes_b64": base64.b64encode(previous_pointer).decode(),
        "previous_pointer_sha256": hashlib.sha256(previous_pointer).hexdigest(),
        "previous_proof_bytes_b64": base64.b64encode(previous_proof).decode(),
        "previous_proof_sha256": hashlib.sha256(previous_proof).hexdigest(),
        "restore_id": "restore-1",
        "slot": slot,
        "state": state,
        "updated_at": "2026-01-01T00:00:00Z",
    }
    record["record_sha256"] = hashlib.sha256(_canonical(record)).hexdigest()
    return record


def _proof(
    generation_id: str, pointer: bytes, receipt: dict[str, Any], receipt_digest: str
) -> dict[str, Any]:
    proof: dict[str, Any] = {
        "active_generation": generation_id,
        "active_pointer_bytes_b64": base64.b64encode(pointer).decode(),
        "active_pointer_sha256": hashlib.sha256(pointer).hexdigest(),
        "generation_publication_receipt": receipt,
        "generation_receipt_sha256": receipt_digest,
        "proof_kind": "restore",
        "proof_sequence": 1,
        "proof_version": 1,
        "restore_id": "restore-1",
        "verified_at": "2026-01-01T00:00:00Z",
    }
    proof["record_sha256"] = hashlib.sha256(_canonical(proof)).hexdigest()
    return proof


def _write_journal(path: Path, record: dict[str, Any]) -> None:
    _durable_replace(path, _canonical(record))
    if _parse_journal(path) is None:
        raise RuntimeError("journal reread failed")


def _cleanup_verified(root: Path, manager: RestoreManager) -> None:
    for index, name in enumerate(("restore-journal-a.json", "restore-journal-b.json")):
        if index == 1:
            manager.hit("recovery.cleanup_between_journal_unlinks")
        (root / name).unlink(missing_ok=True)
        _fsync_directory(root)
    _remove_stale_bindings(root, manager)


def _cleanup_recovered_authority(root: Path) -> None:
    """Remove only recovery metadata after matching proof validation succeeds."""

    for name in ("restore-journal-a.json", "restore-journal-b.json"):
        (root / name).unlink(missing_ok=True)
        _fsync_directory(root)
    _remove_stale_bindings(root)


def _cleanup_recovered_rollback(
    root: Path, candidate_generation: str | None = None
) -> None:
    """Remove one proven-abandoned candidate, then its stale journals."""

    if candidate_generation is not None:
        if not _safe_generation_component(candidate_generation):
            raise ValueError("unsafe candidate generation")
        for parent in ("generation-storage", "generations"):
            candidate = owned_generation_directory(
                root,
                parent,
                candidate_generation,
                allow_missing=True,
            )
            _remove_candidate_generation(candidate)
    for name in ("restore-journal-a.json", "restore-journal-b.json"):
        (root / name).unlink(missing_ok=True)
        _fsync_directory(root)


def _remove_stale_bindings(root: Path, manager: RestoreManager | None = None) -> None:
    if sys.platform == "win32":
        _remove_stale_bindings_windows(Path(root), manager)
        return
    _remove_stale_bindings_posix(Path(root), manager)


def _remove_stale_bindings_windows(root: Path, manager: RestoreManager | None) -> None:
    root_before = _require_cleanup_directory(root)
    private = _exact_child_path(root, "device-private")
    if private is None:
        return
    private_before = _require_cleanup_directory(private)
    directory_handle = _windows_lock_cleanup_directory(private)
    binding_handle = -1
    try:
        _require_same_cleanup_directory(private, private_before)
        bindings = _exact_child_path(private, "workspace-bindings.json")
        if bindings is None:
            return
        binding_before = os.lstat(bindings)
        if not stat.S_ISREG(binding_before.st_mode) or is_link_or_reparse(
            binding_before
        ):
            raise ValueError("stale binding authority is unsafe")
        binding_handle = _windows_open_cleanup_file(bindings)
        binding_after = os.lstat(bindings)
        if (
            not stat.S_ISREG(binding_after.st_mode)
            or is_link_or_reparse(binding_after)
            or binding_after.st_dev != binding_before.st_dev
            or binding_after.st_ino != binding_before.st_ino
        ):
            raise ValueError("stale binding authority is unsafe")
        if manager is not None:
            manager.hit("recovery.stale_bindings_before_unlink")
        _windows_delete_cleanup_file(binding_handle)
        _windows_close_cleanup_handle(binding_handle)
        binding_handle = -1
        if manager is not None:
            manager.hit("recovery.stale_bindings_after_unlink")
        if _exact_child_path(private, "workspace-bindings.json") is not None:
            raise ValueError("stale binding authority changed")
        _require_same_cleanup_directory(private, private_before)
        _require_same_cleanup_directory(root, root_before)
        _fsync_directory(private)
    except OSError as exc:
        raise ValueError("stale binding authority is unsafe") from exc
    finally:
        if binding_handle >= 0:
            _windows_close_cleanup_handle(binding_handle)
        _windows_close_cleanup_handle(directory_handle)


def _remove_stale_bindings_posix(root: Path, manager: RestoreManager | None) -> None:
    root_before = _require_cleanup_directory(root)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    root_descriptor = -1
    private_descriptor = -1
    try:
        root_descriptor = os.open(root, flags)
        root_opened = os.fstat(root_descriptor)
        if (
            not stat.S_ISDIR(root_opened.st_mode)
            or root_opened.st_dev != root_before.st_dev
            or root_opened.st_ino != root_before.st_ino
        ):
            raise ValueError("stale binding authority is unsafe")
        if not _posix_exact_child_exists(root_descriptor, "device-private"):
            return
        private_descriptor = os.open("device-private", flags, dir_fd=root_descriptor)
        private_before = os.fstat(private_descriptor)
        if not stat.S_ISDIR(private_before.st_mode):
            raise ValueError("stale binding authority is unsafe")
        if not _posix_exact_child_exists(private_descriptor, "workspace-bindings.json"):
            return
        binding_info = os.stat(
            "workspace-bindings.json",
            dir_fd=private_descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(binding_info.st_mode) or is_link_or_reparse(binding_info):
            raise ValueError("stale binding authority is unsafe")
        if manager is not None:
            manager.hit("recovery.stale_bindings_before_unlink")
        os.unlink("workspace-bindings.json", dir_fd=private_descriptor)
        os.fsync(private_descriptor)
        if manager is not None:
            manager.hit("recovery.stale_bindings_after_unlink")
        if _posix_exact_child_exists(private_descriptor, "workspace-bindings.json"):
            raise ValueError("stale binding authority changed")
        _require_same_cleanup_directory(root, root_before)
        _require_same_cleanup_directory(root / "device-private", private_before)
    except OSError as exc:
        raise ValueError("stale binding authority is unsafe") from exc
    finally:
        if private_descriptor >= 0:
            os.close(private_descriptor)
        if root_descriptor >= 0:
            os.close(root_descriptor)


def _require_cleanup_directory(path: Path) -> os.stat_result:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ValueError("stale binding authority is unsafe") from exc
    if not stat.S_ISDIR(info.st_mode) or is_link_or_reparse(info):
        raise ValueError("stale binding authority is unsafe")
    return info


def _require_same_cleanup_directory(path: Path, before: os.stat_result) -> None:
    current = _require_cleanup_directory(path)
    if current.st_dev != before.st_dev or current.st_ino != before.st_ino:
        raise ValueError("stale binding authority changed")


def _posix_exact_child_exists(parent_descriptor: int, name: str) -> bool:
    try:
        if name in os.listdir(parent_descriptor):
            return True
        os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ValueError("stale binding authority is unsafe") from exc
    raise ValueError("stale binding authority is unsafe")


def _windows_lock_cleanup_directory(path: Path) -> int:
    import ctypes
    from ctypes import wintypes

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
        file_read_attributes,
        file_share_read | file_share_write,
        None,
        open_existing,
        file_flag_backup_semantics | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def _windows_open_cleanup_file(path: Path) -> int:
    import ctypes
    from ctypes import wintypes

    delete_access = 0x00010000
    file_read_attributes = 0x00000080
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
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
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def _windows_delete_cleanup_file(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOL)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_information.restype = wintypes.BOOL
    disposition = _FileDispositionInfo(True)
    if not set_information(
        handle,
        4,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _windows_close_cleanup_handle(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    if not close_handle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _remove_candidate_generation(path: Path) -> None:
    """Remove an unreferenced candidate without following a link."""

    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if is_link_or_reparse(info):
        raise OSError("refusing candidate reparse-point cleanup")
    if not stat.S_ISDIR(info.st_mode):
        path.unlink(missing_ok=True)
        return
    for child in path.iterdir():
        _remove_candidate_generation(child)
    path.rmdir()
    _fsync_directory(path.parent)


def _restore_exact_previous(root: Path, pointer: bytes, proof: bytes) -> None:
    _write_or_remove(root / "active-generation.json", pointer)
    _write_or_remove(root / "active-generation-proof.json", proof)


def _write_or_remove(path: Path, value: bytes) -> None:
    if value:
        _durable_replace(path, value)
    else:
        path.unlink(missing_ok=True)
        _fsync_directory(path.parent)


def _parse_journal(path: Path) -> dict[str, Any] | None:
    try:
        value = _parse_checksummed_record(_read_bytes(path))
        if value is None or set(value) != _JOURNAL_KEYS:
            return None
        expected_slot = {
            "restore-journal-a.json": "a",
            "restore-journal-b.json": "b",
        }.get(path.name)
        state = value.get("state")
        if (
            expected_slot is None
            or value.get("slot") != expected_slot
            or value.get("journal_version") != 1
            or _JOURNAL_STATE_SEQUENCE.get(state) != value.get("journal_sequence")
            or not isinstance(value.get("restore_id"), str)
            or not value["restore_id"]
            or not isinstance(value.get("updated_at"), str)
            or not value["updated_at"]
            or not _sha256_claim(value.get("archive_sha256"))
            or value.get("candidate_proof_sha256") is not None
        ):
            return None

        candidate_generation = value.get("candidate_generation")
        previous_generation = value.get("previous_generation")
        if (
            not isinstance(candidate_generation, str)
            or not _safe_generation_component(candidate_generation)
            or not isinstance(previous_generation, str)
            or not _safe_generation_component(previous_generation)
            or candidate_generation == previous_generation
        ):
            return None

        candidate_pointer = _decode_record(value, "candidate_pointer_bytes_b64")
        previous_pointer = _decode_record(value, "previous_pointer_bytes_b64")
        previous_proof = _decode_record(value, "previous_proof_bytes_b64")
        if (
            hashlib.sha256(candidate_pointer).hexdigest()
            != value.get("candidate_pointer_sha256")
            or hashlib.sha256(previous_pointer).hexdigest()
            != value.get("previous_pointer_sha256")
            or hashlib.sha256(previous_proof).hexdigest()
            != value.get("previous_proof_sha256")
        ):
            return None

        receipt = value.get("candidate_generation_publication_receipt")
        receipt_digest = value.get("candidate_generation_receipt_sha256")
        if not _generation_receipt_is_valid(
            receipt,
            receipt_digest,
            candidate_generation,
        ):
            return None
        pointer_value = json.loads(candidate_pointer)
        if (
            not isinstance(pointer_value, dict)
            or set(pointer_value) != _POINTER_KEYS
            or _canonical(pointer_value) != candidate_pointer
            or pointer_value.get("generation_id") != candidate_generation
            or pointer_value.get("receipt_sha256") != receipt_digest
        ):
            return None

        if previous_pointer:
            previous_pointer_value = json.loads(previous_pointer)
            if (
                not isinstance(previous_pointer_value, dict)
                or set(previous_pointer_value) != _POINTER_KEYS
                or _canonical(previous_pointer_value) != previous_pointer
                or previous_pointer_value.get("generation_id") != previous_generation
                or not previous_proof
                or not _proof_is_authoritative(
                    path.parent, previous_proof, previous_pointer
                )
            ):
                return None
        elif previous_generation != "g0" or previous_proof:
            return None
        return value
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _checksum_valid_incompatible_journal(
    path: Path, parsed: dict[str, Any] | None
) -> bool:
    if parsed is not None:
        return False
    try:
        return _parse_checksummed_record(_read_bytes(path)) is not None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _sha256_claim(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _generation_receipt_is_valid(
    receipt: object,
    receipt_digest: object,
    generation: str,
) -> bool:
    if (
        not isinstance(receipt, dict)
        or set(receipt) != _RECEIPT_KEYS
        or receipt.get("generation_id") != generation
        or receipt.get("receipt_version") != 1
        or receipt.get("publication_sequence") != 1
        or receipt.get("schema_version") != 1
        or not isinstance(receipt.get("platform"), str)
        or not receipt["platform"]
        or not isinstance(receipt.get("publication_nonce"), str)
        or not receipt["publication_nonce"]
        or not _sha256_claim(receipt.get("validation_digest"))
        or not _sha256_claim(receipt_digest)
        or hashlib.sha256(_canonical(receipt)).hexdigest() != receipt_digest
    ):
        return False
    checkpoint_state = receipt.get("checkpoint_state")
    artifact_state = receipt.get("artifact_state")
    if checkpoint_state not in {"absent_uninitialized", "initialized"} or (
        artifact_state not in {"absent_uninitialized", "initialized"}
    ):
        return False
    return validate_active_generation(
        receipt,
        GenerationExpectation(
            checkpoint_state=checkpoint_state,
            artifact_state=artifact_state,
            schema_version=1,
        ),
    ).ok


def _parse_checksummed_record(raw: bytes) -> dict[str, Any] | None:
    value = json.loads(raw)
    if not isinstance(value, dict) or _canonical(value) != raw:
        return None
    digest = value.pop("record_sha256", None)
    if (
        not isinstance(digest, str)
        or hashlib.sha256(_canonical(value)).hexdigest() != digest
    ):
        return None
    value["record_sha256"] = digest
    return value


def _decode_record(record: dict[str, Any], key: str) -> bytes:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError("missing journal byte preimage")
    return base64.b64decode(value, validate=True)


def _consistent_preproof_slots(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two complete slots may differ in sequence/state but must name one rollback."""

    return not (
        {a.get("state"), b.get("state")} - {"prepared", "published"}
    ) and _consistent_journal_lineage(a, b)


def _consistent_journal_lineage(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = (
        "archive_sha256",
        "candidate_generation",
        "candidate_generation_receipt_sha256",
        "candidate_pointer_bytes_b64",
        "candidate_pointer_sha256",
        "previous_generation",
        "previous_pointer_bytes_b64",
        "previous_pointer_sha256",
        "previous_proof_bytes_b64",
        "previous_proof_sha256",
        "restore_id",
    )
    return all(a.get(key) == b.get(key) for key in keys) and _canonical(
        a.get("candidate_generation_publication_receipt")
    ) == _canonical(b.get("candidate_generation_publication_receipt"))


def _journal_matches_authoritative_proof(
    journal: dict[str, Any], proof: bytes, pointer: bytes
) -> bool:
    value = _parse_checksummed_record(proof)
    if value is None:
        return False
    try:
        return (
            journal.get("candidate_generation") == value.get("active_generation")
            and _decode_record(journal, "candidate_pointer_bytes_b64") == pointer
            and journal.get("candidate_generation_receipt_sha256")
            == value.get("generation_receipt_sha256")
            and journal.get("restore_id") == value.get("restore_id")
            and _canonical(journal.get("candidate_generation_publication_receipt"))
            == _canonical(value.get("generation_publication_receipt"))
        )
    except (ValueError, TypeError):
        return False


def _proof_claims_pointer(proof: bytes, pointer: bytes) -> bool:
    try:
        value = json.loads(proof)
        if not isinstance(value, dict):
            return False
        return (
            isinstance(value.get("active_generation"), str)
            and value.get("active_generation") == _generation_from_pointer(pointer)
            and base64.b64decode(
                str(value.get("active_pointer_bytes_b64")), validate=True
            )
            == pointer
            and value.get("active_pointer_sha256")
            == hashlib.sha256(pointer).hexdigest()
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def _proof_is_authoritative(root: Path, proof: bytes, pointer: bytes) -> bool:
    """Validate record hash, receipt lineage, and read-only candidate inventory."""

    if not _proof_claims_pointer(proof, pointer):
        return False
    try:
        value = _parse_checksummed_record(proof)
        if value is None:
            return False
        generation = _generation_from_pointer(pointer)
        receipt = value.get("generation_publication_receipt")
        receipt_digest = value.get("generation_receipt_sha256")
        pointer_value = json.loads(pointer)
        if (
            generation is None
            or set(value) != _PROOF_KEYS
            or value.get("active_generation") != generation
            or value.get("proof_kind") != "restore"
            or value.get("proof_sequence") != 1
            or value.get("proof_version") != 1
            or not isinstance(value.get("restore_id"), str)
            or not value["restore_id"]
            or not isinstance(value.get("verified_at"), str)
            or not value["verified_at"]
            or not isinstance(receipt, dict)
            or set(receipt) != _RECEIPT_KEYS
            or receipt.get("receipt_version") != 1
            or receipt.get("publication_sequence") != 1
            or not isinstance(receipt.get("platform"), str)
            or not receipt["platform"]
            or not isinstance(receipt.get("publication_nonce"), str)
            or not receipt["publication_nonce"]
            or not isinstance(receipt.get("validation_digest"), str)
            or len(receipt["validation_digest"]) != 64
            or not isinstance(receipt_digest, str)
            or hashlib.sha256(_canonical(receipt)).hexdigest() != receipt_digest
            or receipt.get("generation_id") != generation
            or not isinstance(pointer_value, dict)
            or set(pointer_value) != _POINTER_KEYS
            or _canonical(pointer_value) != pointer
            or pointer_value.get("receipt_sha256") != receipt_digest
        ):
            return False
        checkpoint_state = receipt.get("checkpoint_state")
        artifact_state = receipt.get("artifact_state")
        schema_version = receipt.get("schema_version")
        if checkpoint_state not in {"absent_uninitialized", "initialized"} or (
            artifact_state not in {"absent_uninitialized", "initialized"}
            or schema_version != 1
        ):
            return False
        receipt_validation = validate_active_generation(
            receipt,
            GenerationExpectation(
                checkpoint_state=checkpoint_state,
                artifact_state=artifact_state,
                schema_version=schema_version,
            ),
        )
        if not receipt_validation.ok:
            return False
        if checkpoint_state != "initialized":
            return False
        candidate = owned_generation_directory(root, "generations", generation)
        runtime_storage = owned_generation_directory(
            root, "generation-storage", generation
        )
        return _validate_desktop_source(
            {
                "generation_root": str(candidate),
                "runtime_storage_root": str(runtime_storage),
            },
            artifact_state=artifact_state,
        ) == (checkpoint_state, artifact_state)
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _generation_from_pointer(pointer: bytes) -> str | None:
    try:
        value = json.loads(pointer)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    generation = value.get("generation_id") if isinstance(value, dict) else None
    if not isinstance(generation, str) or not is_canonical_generation_id(generation):
        return None
    return generation


def _durable_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("xb") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temp, path)
        try:
            fsync_path(path)
            _fsync_directory(path.parent)
        except OSError as exc:
            raise _DurableReplaceEffectUncertain(path.name) from exc
    finally:
        temp.unlink(missing_ok=True)


def _fsync_tree(root: Path) -> None:
    _fsync_regular_tree(root)
    _fsync_directories_bottom_up(root)


def _fsync_directory(path: Path) -> None:
    if sys.platform == "win32":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_bytes(path: Path) -> bytes:
    """Read one optional recovery record through exact owned-file authority."""

    parent = path.parent
    name = path.name
    if _exact_child_path(parent, name) is None:
        return b""
    return _read_owned_regular(parent, name, _MAX_GENERATION_CONTROL_BYTES)


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
