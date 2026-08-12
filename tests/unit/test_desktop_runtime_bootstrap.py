"""DesktopRuntimeOwner lock + generation bootstrap before Host (078 T025)."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from loopplane.checkpoint import SqliteCheckpointStore
from loopplane.host import (
    DesktopActiveGenerationProvider,
    DesktopStorageAuthorityFactory,
    GenerationExpectation,
    PortableSnapshotResult,
    RuntimeConfig,
    validate_active_generation,
)
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileBusyError  # noqa: E402

from durability import (  # noqa: E402
    has_restore_journals,
    publish_pristine_generation,
    read_current_generation,
)
from runtime import DesktopRuntimeOwner, RestoreJournalsPresent  # noqa: E402


def _create_directory_alias(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("Windows junction creation is unavailable")
        return
    os.symlink(target, link, target_is_directory=True)


def _remove_directory_alias(link: Path) -> None:
    if sys.platform == "win32":
        os.rmdir(link)
    else:
        link.unlink()


def test_bootstrap_before_host_and_second_lock_busy(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    assert owner.host is None
    owner.acquire()
    assert owner.bootstrapped is False
    info = owner.bootstrap_generation()
    assert info["ok"] is True
    assert owner.bootstrapped is True
    assert has_restore_journals(root) is False

    # Second process/owner same root is busy with zero Host on the second.
    other = DesktopRuntimeOwner(profile_root=root)
    with pytest.raises(ProfileBusyError):
        other.acquire()
    assert other.host is None

    from bridge import desktop_runtime_config

    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="x")])],
        context_capacity=100_000,
    )
    with pytest.raises(RuntimeError, match="storage authority"):
        owner.attach_host(RuntimeConfig(model=model))
    host = owner.attach_host(
        desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
    )
    assert host is owner.host
    with pytest.raises(RuntimeError, match="Host must be closed"):
        owner.release()
    assert owner.host is host
    still_blocked = DesktopRuntimeOwner(profile_root=root)
    with pytest.raises(ProfileBusyError):
        still_blocked.acquire()

    anyio.run(owner.close_host)
    owner.release()
    assert owner.host is None

    replacement = DesktopRuntimeOwner(profile_root=root)
    replacement.acquire()
    replacement.release()


def test_restore_journals_fail_locked_without_host(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    root.mkdir()
    jdir = root / "journals"
    jdir.mkdir()
    (jdir / "slot-0.preimage").write_bytes(b"x")
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    with pytest.raises(RestoreJournalsPresent):
        owner.bootstrap_generation()
    assert owner.host is None
    owner.release()


@pytest.mark.parametrize(
    "pointer_bytes",
    [b"g0 \n", b" g0\n", b"", b"g0", b"g0\n\n", b"g0\r\n"],
)
def test_bootstrap_rejects_nonexact_current_generation_representation(
    tmp_path: Path, pointer_bytes: bytes
) -> None:
    """The durable current pointer accepts only canonical id plus one LF."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_path = first.ensure_profile_state().portable_path()
        profile_before = profile_path.read_bytes()
    finally:
        first.release()

    (root / "current-generation").write_bytes(pointer_bytes)
    second = DesktopRuntimeOwner(profile_root=root)
    second.acquire()
    try:
        with pytest.raises(RuntimeError, match="current-generation"):
            second.bootstrap_generation()
    finally:
        second.release()

    assert profile_path.read_bytes() == profile_before


def test_bootstrap_recovers_proof_before_pointer_pristine_generation(
    tmp_path: Path,
) -> None:
    """A crash after pristine proof publication can complete the missing pointer."""

    root = tmp_path / "profile"
    root.mkdir()
    proof = publish_pristine_generation(root, "g0")
    proof_before = proof.read_bytes()

    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        assert owner.bootstrap_generation() == {"generation_id": "g0", "ok": True}
    finally:
        owner.release()

    assert proof.read_bytes() == proof_before
    assert read_current_generation(root) == "g0"


def test_missing_pointer_rejects_linked_pristine_proof_without_external_mutation(
    tmp_path: Path,
) -> None:
    """An external proof file can never authorize a local current pointer."""

    root = tmp_path / "profile"
    generation = root / "generations" / "g0"
    generation.mkdir(parents=True)
    external = tmp_path / "external-proof.json"
    external_bytes = json.dumps(
        {
            "artifact_state": "absent_uninitialized",
            "checkpoint_state": "absent_uninitialized",
            "generation_id": "g0",
            "schema_version": 1,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    external.write_bytes(external_bytes)
    proof = generation / "proof.json"
    try:
        os.symlink(external, proof)
    except OSError:
        pytest.skip("file symlink creation is unavailable")

    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        with pytest.raises(RuntimeError, match="missing current-generation"):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert external.read_bytes() == external_bytes
    assert not (root / "current-generation").exists()
    assert not (generation / "profile.json").exists()


def test_missing_pointer_rejects_reparse_marked_pristine_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Windows reparse-marked proof fails before pointer/profile mutation."""

    import durability

    root = tmp_path / "profile"
    root.mkdir()
    proof = publish_pristine_generation(root, "g0")
    proof_before = proof.read_bytes()
    real_lstat = os.lstat

    def reparse_proof(path: os.PathLike[str] | str) -> os.stat_result | SimpleNamespace:
        info = real_lstat(path)
        if Path(path) != proof:
            return info
        return SimpleNamespace(
            st_mode=info.st_mode,
            st_dev=info.st_dev,
            st_ino=info.st_ino,
            st_size=info.st_size,
            st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        )

    monkeypatch.setattr(durability.os, "lstat", reparse_proof)
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        with pytest.raises(RuntimeError, match="missing current-generation"):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert proof.read_bytes() == proof_before
    assert not (root / "current-generation").exists()
    assert not (root / "generations" / "g0" / "profile.json").exists()


@pytest.mark.parametrize("damage", ["checkpoint", "artifact", "profile"])
def test_missing_pointer_rejects_existing_mutable_g0_before_profile_mutation(
    tmp_path: Path, damage: str
) -> None:
    """Missing pointer is pristine only when no mutable g0 authority exists."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_path = first.ensure_profile_state().portable_path()
    finally:
        first.release()

    (root / "current-generation").unlink()
    if damage == "checkpoint":
        damaged_path = root / "generation-storage" / "g0" / "checkpoints.sqlite3"
        damaged_path.parent.mkdir(parents=True)
        damaged_path.write_bytes(b"not-a-sqlite-database")
    elif damage == "artifact":
        damaged_path = (
            root
            / "generation-storage"
            / "g0"
            / "session"
            / "artifacts"
            / "unexpected.bin"
        )
        damaged_path.parent.mkdir(parents=True)
        damaged_path.write_bytes(b"unexpected-artifact")
    else:
        damaged_path = profile_path
        damaged_path.write_bytes(b"{}")
    damaged_before = damaged_path.read_bytes()

    second = DesktopRuntimeOwner(profile_root=root)
    second.acquire()
    try:
        with pytest.raises(RuntimeError, match="missing current-generation"):
            second.bootstrap_generation()
    finally:
        second.release()

    assert damaged_path.read_bytes() == damaged_before


def test_bootstrap_rejects_nonregular_current_pointer_before_any_mutation(
    tmp_path: Path,
) -> None:
    """Only a missing pointer authorizes pristine publication.

    A directory never does.
    """

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_path = first.ensure_profile_state().portable_path()
        profile_before = profile_path.read_bytes()
    finally:
        first.release()

    proof_path = root / "generations" / "g0" / "proof.json"
    proof_before = b"proof-must-not-change"
    proof_path.write_bytes(proof_before)
    checkpoint = root / "generation-storage" / "g0" / "checkpoints.sqlite3"
    checkpoint.parent.mkdir(parents=True)
    checkpoint_before = b"corrupt-mutable-checkpoint"
    checkpoint.write_bytes(checkpoint_before)
    pointer = root / "current-generation"
    pointer.unlink()
    pointer.mkdir()

    second = DesktopRuntimeOwner(profile_root=root)
    second.acquire()
    try:
        with pytest.raises(RuntimeError, match="current-generation"):
            second.bootstrap_generation()
    finally:
        second.release()

    assert proof_path.read_bytes() == proof_before
    assert profile_path.read_bytes() == profile_before
    assert checkpoint.read_bytes() == checkpoint_before


def test_bootstrap_rejects_current_pointer_reparse_without_external_mutation(
    tmp_path: Path,
) -> None:
    """A current-generation junction/symlink is never treated as missing."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_path = first.ensure_profile_state().portable_path()
        profile_before = profile_path.read_bytes()
    finally:
        first.release()

    proof_path = root / "generations" / "g0" / "proof.json"
    proof_before = proof_path.read_bytes()
    pointer = root / "current-generation"
    pointer.unlink()
    external = tmp_path / "external-pointer"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    _create_directory_alias(pointer, external)
    try:
        second = DesktopRuntimeOwner(profile_root=root)
        second.acquire()
        try:
            with pytest.raises(RuntimeError, match="current-generation"):
                second.bootstrap_generation()
        finally:
            second.release()

        assert proof_path.read_bytes() == proof_before
        assert profile_path.read_bytes() == profile_before
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        _remove_directory_alias(pointer)


def test_bootstrap_rejects_generation_directory_alias_without_external_mutation(
    tmp_path: Path,
) -> None:
    """A current generation junction/symlink never becomes profile authority."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        generation = root / "generations" / "g0"
        profile_before = first.ensure_profile_state().portable_path().read_bytes()
    finally:
        first.release()

    external = tmp_path / "external-generation"
    generation.rename(external)
    _create_directory_alias(generation, external)
    try:
        second = DesktopRuntimeOwner(profile_root=root)
        second.acquire()
        try:
            with pytest.raises(RuntimeError, match="generation path"):
                second.bootstrap_generation()
        finally:
            second.release()

        assert (external / "profile.json").read_bytes() == profile_before
    finally:
        _remove_directory_alias(generation)


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
@pytest.mark.parametrize("alias_level", ["collection", "generation"])
def test_bootstrap_rejects_case_aliased_generation_entry_before_profile_mutation(
    tmp_path: Path, alias_level: str
) -> None:
    """The actual Windows directory names must exactly match canonical authority."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_before = first.ensure_profile_state().portable_path().read_bytes()
    finally:
        first.release()

    generations = root / "generations"
    if alias_level == "collection":
        temporary = root / "generations-rename"
        generations.rename(temporary)
        actual_generation = root / "Generations" / "g0"
        temporary.rename(root / "Generations")
    else:
        generation = generations / "g0"
        temporary = generations / "g0-rename"
        generation.rename(temporary)
        actual_generation = generations / "G0"
        temporary.rename(actual_generation)

    second = DesktopRuntimeOwner(profile_root=root)
    second.acquire()
    try:
        with pytest.raises(RuntimeError, match="generation path"):
            second.bootstrap_generation()
    finally:
        second.release()

    assert (actual_generation / "profile.json").read_bytes() == profile_before


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
def test_missing_pointer_rejects_case_aliased_runtime_storage_before_mutation(
    tmp_path: Path,
) -> None:
    """Proof-before-pointer recovery rejects aliased mutable storage authority."""

    root = tmp_path / "profile"
    root.mkdir()
    proof = publish_pristine_generation(root, "g0")
    proof_before = proof.read_bytes()
    alias = root / "Generation-Storage" / "G0"
    alias.mkdir(parents=True)

    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        with pytest.raises(RuntimeError):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert proof.read_bytes() == proof_before
    assert list(alias.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction storage boundary")
def test_missing_pointer_rejects_runtime_storage_junction_without_external_mutation(
    tmp_path: Path,
) -> None:
    """A junction cannot become storage authority during pristine recovery."""

    root = tmp_path / "profile"
    root.mkdir()
    proof = publish_pristine_generation(root, "g0")
    proof_before = proof.read_bytes()
    external = tmp_path / "external-storage"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    link = root / "generation-storage"
    _create_directory_alias(link, external)

    try:
        owner = DesktopRuntimeOwner(profile_root=root)
        owner.acquire()
        try:
            with pytest.raises(RuntimeError):
                owner.bootstrap_generation()
        finally:
            owner.release()

        assert proof.read_bytes() == proof_before
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        if os.path.lexists(link):
            _remove_directory_alias(link)


def test_bootstrap_rejects_traversal_generation_before_profile_mutation(
    tmp_path: Path,
) -> None:
    """An active pointer cannot select profile state outside generations/."""

    root = tmp_path / "profile"
    outside = root / "outside"
    outside.mkdir(parents=True)
    (outside / "proof.json").write_text(
        json.dumps(
            {
                "generation_id": "../outside",
                "checkpoint_state": "absent_uninitialized",
                "artifact_state": "absent_uninitialized",
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    root.mkdir(exist_ok=True)
    (root / "current-generation").write_text("../outside\n", encoding="utf-8")

    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        with pytest.raises(RuntimeError, match="current-generation"):
            owner.bootstrap_generation()
    finally:
        owner.release()

    assert not (outside / "profile.json").exists()


def test_bootstrap_rejects_corrupt_current_checkpoint_without_profile_rewrite(
    tmp_path: Path,
) -> None:
    """Current mutable SQLite must pass Host validation before profile open."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_path = first.ensure_profile_state().portable_path()
        profile_before = profile_path.read_bytes()
    finally:
        first.release()

    checkpoint = root / "generation-storage" / "g0" / "checkpoints.sqlite3"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"not-a-sqlite-database")

    second = DesktopRuntimeOwner(profile_root=root)
    second.acquire()
    try:
        with pytest.raises(RuntimeError, match="filesystem validation"):
            second.bootstrap_generation()
    finally:
        second.release()

    assert profile_path.read_bytes() == profile_before


def test_bootstrap_rejects_missing_profile_identity_without_rewriting(
    tmp_path: Path,
) -> None:
    """A shape-valid but identity-less current profile remains untouched and locked."""

    root = tmp_path / "profile"
    first = DesktopRuntimeOwner(profile_root=root)
    first.acquire()
    try:
        first.bootstrap_generation()
        profile_path = first.ensure_profile_state().portable_path()
    finally:
        first.release()

    malformed = b"{}"
    profile_path.write_bytes(malformed)

    second = DesktopRuntimeOwner(profile_root=root)
    second.acquire()
    try:
        with pytest.raises(RuntimeError, match="filesystem validation"):
            second.bootstrap_generation()
    finally:
        second.release()

    assert profile_path.read_bytes() == malformed


def test_runtime_config_initializes_host_owned_sqlite_before_return(
    tmp_path: Path,
) -> None:
    """Desktop composition returns an initialized, Host-valid storage authority."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        profile_path = owner.ensure_profile_state().portable_path()
        model = ScriptedModel(script=[], context_capacity=100_000)
        config = desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
        assert config.storage is not None
        result = validate_active_generation(
            {
                "profile_path": str(profile_path),
                "runtime_storage_root": str(config.storage.root),
            },
            GenerationExpectation(
                checkpoint_state="initialized",
                artifact_state="absent_uninitialized",
                schema_version=1,
            ),
            provider=DesktopActiveGenerationProvider(),
        )
        assert result.ok, result.reason
    finally:
        owner.release()


def test_runtime_config_initialization_failure_leaves_no_empty_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed Host initializer leaves no corrupt empty generation leaf."""

    import durability
    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        monkeypatch.setattr(
            durability.DesktopRuntimeStorageInitializer,
            "initialize",
            lambda _self, _destination: PortableSnapshotResult(
                ok=False, reason="injected"
            ),
        )
        model = ScriptedModel(script=[], context_capacity=100_000)
        with pytest.raises(ValueError, match="initialization failed"):
            desktop_runtime_config(
                model=model,
                profile_root=root,
                generation_id=owner.generation_id,
            )
        parent = root / "generation-storage"
        assert not (parent / "g0").exists()
        assert not any(entry.name.endswith(".initialize") for entry in parent.iterdir())
    finally:
        owner.release()


def test_runtime_config_rejects_corrupt_existing_storage_before_host(
    tmp_path: Path,
) -> None:
    """A corrupt first-use destination never reaches Host construction."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        checkpoint = root / "generation-storage" / "g0" / "checkpoints.sqlite3"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b"not-a-sqlite-database")
        model = ScriptedModel(script=[], context_capacity=100_000)
        with pytest.raises(ValueError, match="runtime storage"):
            desktop_runtime_config(
                model=model,
                profile_root=root,
                generation_id=owner.generation_id,
            )
        assert owner.host is None
        assert checkpoint.read_bytes() == b"not-a-sqlite-database"
    finally:
        owner.release()


@pytest.mark.parametrize(
    "records_schema",
    [
        "CREATE TABLE records (session_id TEXT, data TEXT)",
        (
            "CREATE TABLE records (session_id TEXT, sequence INTEGER, "
            "recorded_at TEXT, data TEXT)"
        ),
        (
            "CREATE TABLE records (session_id TEXT NOT NULL, "
            "sequence INTEGER NOT NULL, recorded_at TEXT NOT NULL, "
            "data TEXT NOT NULL, PRIMARY KEY (sequence, session_id))"
        ),
        (
            "CREATE TABLE records (session_id TEXT NOT NULL, "
            "sequence TEXT NOT NULL, recorded_at TEXT NOT NULL, "
            "data TEXT NOT NULL, PRIMARY KEY (session_id, sequence))"
        ),
    ],
    ids=["missing-columns", "nullable", "wrong-primary-key", "wrong-type"],
)
def test_runtime_config_rejects_queryable_incompatible_checkpoint_schema(
    tmp_path: Path, records_schema: str
) -> None:
    """A queryable SQLite file is not serving authority without the exact schema."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        checkpoint = root / "generation-storage" / "g0" / "checkpoints.sqlite3"
        checkpoint.parent.mkdir(parents=True)
        with sqlite3.connect(checkpoint) as connection:
            connection.execute(records_schema)
        checkpoint_before = checkpoint.read_bytes()
        model = ScriptedModel(script=[], context_capacity=100_000)

        with pytest.raises(ValueError, match="runtime storage"):
            desktop_runtime_config(
                model=model,
                profile_root=root,
                generation_id=owner.generation_id,
            )

        assert owner.host is None
        assert checkpoint.read_bytes() == checkpoint_before
    finally:
        owner.release()


@pytest.mark.parametrize(
    "extra_sql",
    [
        "CREATE TABLE unexpected (value TEXT)",
        ("CREATE TRIGGER unexpected AFTER INSERT ON records BEGIN SELECT 1; END"),
    ],
    ids=["extra-table", "insert-trigger"],
)
def test_runtime_config_rejects_extra_checkpoint_schema_objects(
    tmp_path: Path,
    extra_sql: str,
) -> None:
    """Mutable startup rejects non-serving tables and executable schema objects."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        checkpoint = root / "generation-storage" / "g0" / "checkpoints.sqlite3"
        SqliteCheckpointStore(checkpoint).initialize()
        with sqlite3.connect(checkpoint) as connection:
            connection.execute(extra_sql)
        checkpoint_before = checkpoint.read_bytes()

        with pytest.raises(ValueError, match="runtime storage"):
            desktop_runtime_config(
                model=ScriptedModel(script=[], context_capacity=100_000),
                profile_root=root,
                generation_id=owner.generation_id,
            )

        assert owner.host is None
        assert checkpoint.read_bytes() == checkpoint_before
    finally:
        owner.release()


def test_runtime_config_rejects_noncanonical_generation_storage_path(
    tmp_path: Path,
) -> None:
    """Desktop Host storage composition accepts only one canonical component."""

    from bridge import desktop_runtime_config

    model = ScriptedModel(script=[], context_capacity=100_000)

    with pytest.raises(ValueError, match="generation id"):
        desktop_runtime_config(
            model=model,
            profile_root=tmp_path / "profile",
            generation_id="../outside",
        )


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
def test_runtime_config_rejects_case_aliased_storage_generation(tmp_path: Path) -> None:
    """Runtime storage composition requires the preserved canonical leaf name."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    alias = root / "generation-storage" / "G0"
    alias.mkdir(parents=True)
    model = ScriptedModel(script=[], context_capacity=100_000)

    with pytest.raises(ValueError, match="generation path"):
        desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id="g0",
        )


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
def test_host_attach_revalidates_storage_after_config_composition(
    tmp_path: Path,
) -> None:
    """An alias inserted after config composition cannot reach Host first use."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        model = ScriptedModel(script=[], context_capacity=100_000)
        config = desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
        storage_parent = root / "generation-storage"
        if storage_parent.exists():
            temporary = root / "generation-storage-rename"
            storage_parent.rename(temporary)
            temporary.rename(root / "Generation-Storage")
        else:
            (root / "Generation-Storage" / "G0").mkdir(parents=True)

        with pytest.raises(RuntimeError, match="storage authority"):
            owner.attach_host(config)
        assert owner.host is None
    finally:
        owner.release()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows preserves case-insensitive path aliases"
)
def test_host_attach_rejects_case_aliased_config_storage_spelling(
    tmp_path: Path,
) -> None:
    """Config spelling must bind to the preserved canonical storage components."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        model = ScriptedModel(script=[], context_capacity=100_000)
        config = desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
        assert config.storage is not None
        aliased = replace(
            config,
            storage=replace(
                config.storage,
                root=root / "Generation-Storage" / "G0",
            ),
        )

        with pytest.raises(RuntimeError, match="storage authority"):
            owner.attach_host(aliased)

        assert owner.host is None
    finally:
        owner.release()


def test_host_attach_rejects_storage_without_retained_authority(
    tmp_path: Path,
) -> None:
    """Desktop serving storage cannot bypass its per-Host retained authority."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        model = ScriptedModel(script=[], context_capacity=100_000)
        config = desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
        assert config.storage is not None
        unretained = replace(
            config,
            storage=replace(config.storage, authority=None),
        )

        with pytest.raises(RuntimeError, match="storage authority"):
            owner.attach_host(unretained)

        assert owner.host is None
    finally:
        owner.release()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows retained-handle boundary")
@pytest.mark.parametrize("boundary", ["collection", "generation"])
def test_attached_host_retains_runtime_storage_against_replacement(
    tmp_path: Path, boundary: str
) -> None:
    """An attached Desktop Host prevents ancestor or leaf authority replacement."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    host = None
    moved: tuple[Path, Path] | None = None
    owner.acquire()
    try:
        owner.bootstrap_generation()
        model = ScriptedModel(script=[], context_capacity=100_000)
        config = desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
        host = owner.attach_host(config)
        source = root / "generation-storage"
        if boundary == "generation":
            source /= "g0"
        target = source.with_name(f"{source.name}-moved")

        try:
            source.rename(target)
        except OSError:
            pass
        else:
            moved = (source, target)
            pytest.fail("attached Host allowed runtime storage replacement")
    finally:
        if host is not None:
            anyio.run(owner.close_host)
        if moved is not None:
            source, target = moved
            target.rename(source)
        elif host is not None:
            source.rename(target)
            target.rename(source)
        owner.release()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows retained-handle boundary")
def test_windows_storage_ancestor_close_failure_requires_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial ancestor close blocks reuse until the owning lease retries."""

    import loopplane.host.storage_authority as authority_module

    profile = tmp_path / "profile"
    generation = profile / "generation-storage" / "g0"
    generation.mkdir(parents=True)
    factory = DesktopStorageAuthorityFactory(profile)
    lease = factory.acquire(generation)
    original_close = authority_module._windows_close_handle
    close_calls = {"count": 0}

    def fail_first_ancestor_close(handle: int) -> None:
        close_calls["count"] += 1
        if close_calls["count"] == 2:
            raise OSError("ancestor close failed")
        original_close(handle)

    monkeypatch.setattr(
        authority_module,
        "_windows_close_handle",
        fail_first_ancestor_close,
    )
    with pytest.raises(OSError, match="ancestor close failed"):
        lease.close()
    with pytest.raises(RuntimeError, match="close retry is pending"):
        factory.acquire(generation)

    monkeypatch.setattr(
        authority_module,
        "_windows_close_handle",
        original_close,
    )
    lease.close()
    replacement = factory.acquire(generation)
    replacement.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX descriptor-root boundary")
def test_posix_storage_authority_uses_retained_descriptor_after_replacement(
    tmp_path: Path,
) -> None:
    """A validate-to-open race stays rooted in the retained generation inode."""

    profile = tmp_path / "profile"
    generation = profile / "generation-storage" / "g0"
    generation.mkdir(parents=True)
    marker = generation / "marker"
    marker.write_text("retained", encoding="utf-8")
    lease = DesktopStorageAuthorityFactory(profile).acquire(generation)
    moved = generation.with_name("g0-moved")
    try:
        lease.validate()
        generation.rename(moved)
        generation.mkdir()
        (generation / "marker").write_text("replacement", encoding="utf-8")

        assert (lease.root / "marker").read_text(encoding="utf-8") == "retained"
        with pytest.raises(RuntimeError, match="identity changed"):
            lease.validate()
    finally:
        lease.close()


def test_production_runtime_config_uses_active_generation_local_sqlite(
    tmp_path: Path,
) -> None:
    """The launch composition never leaves desktop Host storage ephemeral."""

    from bridge import desktop_runtime_config

    root = tmp_path / "profile"
    owner = DesktopRuntimeOwner(profile_root=root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
        model = ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="x")])],
            context_capacity=100_000,
        )
        config = desktop_runtime_config(
            model=model,
            profile_root=root,
            generation_id=owner.generation_id,
        )
        assert config.storage is not None
        assert config.storage.checkpoint_backend == "sqlite"
        assert config.storage.root == root / "generation-storage" / "g0"
        assert owner.attach_host(config) is owner.host
    finally:
        anyio.run(owner.close_host)
        owner.release()
