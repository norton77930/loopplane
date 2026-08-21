"""Host portable snapshot default-unavailable (078 T075)."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.checkpoint import SqliteCheckpointStore
from loopplane.checkpoint.records import (
    ReplacementDecisionRecord,
    ReplacementDecisionRecordPayload,
    serialize_record,
)
from loopplane.host import (
    DesktopStorageAuthorityFactory,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
    UnavailablePortableSnapshotProvider,
)
from loopplane.host.snapshot import (
    DesktopPortableSnapshotProvider,
    PortableSnapshotResult,
    _checkpoint_references,
)
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from tests.integration.conftest import BIG_TOOL, EventCollector, big_tool_model


def _host(tmp_path: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / "store",
            ),
        ),
        working_scope=tmp_path,
    )


def test_default_export_and_validate_unavailable(tmp_path: Path) -> None:
    host = _host(tmp_path)
    exp = host.export_portable_snapshot(tmp_path / "out")
    assert exp.ok is False
    assert exp.reason == "portable_snapshot_unavailable"
    val = host.validate_portable_snapshot(tmp_path / "in")
    assert val.ok is False


def test_injected_provider_is_used(tmp_path: Path) -> None:
    class FakeProvider:
        def export_snapshot(self, destination: Path) -> PortableSnapshotResult:
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "ok.txt").write_text("x", encoding="utf-8")
            return PortableSnapshotResult(ok=True, path=str(destination), entry_count=1)

        def validate_snapshot(self, source: Path) -> PortableSnapshotResult:
            return PortableSnapshotResult(
                ok=source.exists(),
                path=str(source),
                entry_count=1 if source.exists() else 0,
            )

    host = _host(tmp_path)
    host.set_portable_snapshot_provider(FakeProvider())
    dest = tmp_path / "snap"
    exp = host.export_portable_snapshot(dest)
    assert exp.ok is True
    assert exp.entry_count == 1
    val = host.validate_portable_snapshot(dest)
    assert val.ok is True
    host.set_portable_snapshot_provider(UnavailablePortableSnapshotProvider())
    assert host.export_portable_snapshot(tmp_path / "x").ok is False


def test_validate_callback_does_not_authorize_arbitrary_symlink_root(
    tmp_path: Path,
) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    SqliteCheckpointStore(storage / "checkpoints.sqlite3").initialize()
    alias = tmp_path / "storage-alias"
    try:
        alias.symlink_to(storage, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform privilege configuration
        pytest.skip(f"directory symlink creation unavailable: {exc.__class__.__name__}")
    destination = tmp_path / "snapshot-alias"
    destination.mkdir()
    provider = DesktopPortableSnapshotProvider(alias, validate_root=lambda: None)

    exported = provider.export_snapshot(destination)

    assert exported.ok is False
    assert exported.reason == "artifact_provenance_unavailable"


def test_checkpoint_references_reject_path_like_opaque_ids(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoints.sqlite3"
    SqliteCheckpointStore(checkpoint).initialize()
    record = ReplacementDecisionRecord(
        session_id="../outside",
        sequence=1,
        recorded_at=datetime.now(UTC),
        payload=ReplacementDecisionRecordPayload(
            artifact_reference="artifact",
            replaced_call_id="call",
            preview="preview",
            decided_at=datetime.now(UTC),
        ),
    )
    with sqlite3.connect(checkpoint) as connection:
        connection.execute(
            "INSERT INTO records(session_id, sequence, recorded_at, data) "
            "VALUES (?, ?, ?, ?)",
            (
                record.session_id,
                record.sequence,
                record.recorded_at.isoformat(),
                serialize_record(record),
            ),
        )

    assert _checkpoint_references(checkpoint) is None


@pytest.mark.anyio
async def test_desktop_provider_exports_consistent_read_only_snapshot(
    tmp_path: Path,
) -> None:
    """The Desktop Host-owned provider never copies the live SQLite file."""

    host = _host(tmp_path)

    async def sink(_event: object) -> None:
        return None

    outcome = await host.run("durable", sink)
    host.enable_desktop_portable_snapshot()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    exported = host.export_portable_snapshot(snapshot)

    assert exported.ok is True
    assert exported.entry_count == 1
    assert (snapshot / "sessions" / "checkpoints.sqlite3").is_file()
    assert outcome.session_id in {
        row[0]
        for row in sqlite3.connect(
            snapshot / "sessions" / "checkpoints.sqlite3"
        ).execute("SELECT DISTINCT session_id FROM records")
    }
    before = (snapshot / "sessions" / "checkpoints.sqlite3").read_bytes()
    validated = host.validate_portable_snapshot(snapshot)
    assert validated.ok is True
    assert (snapshot / "sessions" / "checkpoints.sqlite3").read_bytes() == before


async def _artifact_backed_host(
    tmp_path: Path,
    *,
    retained: bool = False,
) -> tuple[LoopPlaneHost, Path, Path, Path]:
    if retained:
        profile = tmp_path / "profile"
        storage = profile / "generation-storage" / "g0"
        storage.mkdir(parents=True)
        authority = DesktopStorageAuthorityFactory(profile)
    else:
        storage = tmp_path / "artifact-storage"
        authority = None
    host = LoopPlaneHost(
        RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(
                root=storage,
                authority=authority,
                checkpoint_backend="sqlite",
                artifact_threshold_bytes=1_000_000,
                replacement_budget_bytes=1,
            ),
        ),
        working_scope=tmp_path,
    )
    outcome = await host.run("archive", EventCollector())
    host.enable_desktop_portable_snapshot()
    artifacts = storage / outcome.session_id / "artifacts"
    payload = next(artifacts.glob("*.txt"))
    metadata = next(artifacts.glob("*.meta.json"))
    return host, artifacts, payload, metadata


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "unreferenced",
        "metadata_mismatch",
        "replaced_call",
        "identity_change",
    ],
)
async def test_host_export_rejects_artifact_provenance_failures_via_public_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """All source failures become a failed public Host export, never omission."""

    host, artifacts, payload, metadata = await _artifact_backed_host(tmp_path)
    if failure == "missing":
        payload.unlink()
    elif failure == "unreferenced":
        (artifacts / "orphan.txt").write_text("orphan", encoding="utf-8")
    elif failure in {"metadata_mismatch", "replaced_call"}:
        data = json.loads(metadata.read_text(encoding="utf-8"))
        data["size" if failure == "metadata_mismatch" else "call_id"] = (
            -1 if failure == "metadata_mismatch" else "replaced-call"
        )
        metadata.write_text(json.dumps(data), encoding="utf-8")
    else:
        import loopplane.host.snapshot as snapshot_module

        original_lstat = snapshot_module.os.lstat
        observed = {"payload_reads": 0}

        def changed_identity(
            path: str | os.PathLike[str], *, dir_fd: int | None = None
        ) -> os.stat_result:
            result = (
                original_lstat(path)
                if dir_fd is None
                else original_lstat(path, dir_fd=dir_fd)
            )
            if dir_fd is None and Path(path) == payload:
                observed["payload_reads"] += 1
                if observed["payload_reads"] >= 3:
                    return type(
                        "ChangedIdentity",
                        (),
                        {
                            "st_dev": result.st_dev,
                            "st_file_attributes": getattr(
                                result, "st_file_attributes", 0
                            )
                            or 0,
                            "st_ino": result.st_ino + 1,
                            "st_mode": result.st_mode,
                            "st_size": result.st_size,
                        },
                    )()
            return result

        monkeypatch.setattr(snapshot_module.os, "lstat", changed_identity)

    destination = tmp_path / f"snapshot-{failure}"
    destination.mkdir()
    exported = host.export_portable_snapshot(destination)

    assert exported.ok is False
    assert exported.path is None
    assert exported.reason in {
        "artifact_provenance_unavailable",
        "snapshot_export_failed",
    }


@pytest.mark.anyio
async def test_host_export_rejects_symlink_artifact_via_public_seam(
    tmp_path: Path,
) -> None:
    host, _artifacts, payload, _metadata = await _artifact_backed_host(tmp_path)
    target = tmp_path / "outside-artifact"
    target.write_text("not an artifact", encoding="utf-8")
    payload.unlink()
    try:
        payload.symlink_to(target)
    except OSError as exc:  # pragma: no cover - platform privilege configuration
        pytest.skip(f"symlink creation unavailable: {exc.__class__.__name__}")

    destination = tmp_path / "snapshot-symlink"
    destination.mkdir()
    exported = host.export_portable_snapshot(destination)

    assert exported.ok is False
    assert exported.path is None


@pytest.mark.skipif(os.name == "nt", reason="POSIX retained descriptor boundary")
@pytest.mark.anyio
async def test_retained_snapshot_rejects_checkpoint_replacement_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, _artifacts, _payload, _metadata = await _artifact_backed_host(
        tmp_path, retained=True
    )
    storage = tmp_path / "profile" / "generation-storage" / "g0"
    source = storage / "checkpoints.sqlite3"
    retained = tmp_path / "retained-checkpoints.sqlite3"
    replacement = tmp_path / "replacement-checkpoints.sqlite3"
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(replacement) as replacement_connection:
            source_connection.backup(replacement_connection)
    with sqlite3.connect(replacement) as connection:
        connection.execute(
            "UPDATE records SET recorded_at = '2000-01-01T00:00:00+00:00'"
        )
        connection.commit()

    import loopplane.host.snapshot as snapshot_module

    original_regular_file = snapshot_module._regular_file
    original_entry_lstat = snapshot_module._entry_lstat
    swapped = False

    def swap_source() -> None:
        nonlocal swapped
        source.rename(retained)
        replacement.rename(source)
        swapped = True

    def replace_after_path_acceptance(path: Path) -> bool:
        accepted = original_regular_file(path)
        if (
            not swapped
            and path.name == source.name
            and snapshot_module._retained_descriptor_root(path.parent)
        ):
            swap_source()
        return accepted

    def replace_after_descriptor_acceptance(
        parent_fd: int, name: str
    ) -> os.stat_result:
        accepted = original_entry_lstat(parent_fd, name)
        if not swapped and name == source.name:
            swap_source()
        return accepted

    monkeypatch.setattr(
        snapshot_module,
        "_regular_file",
        replace_after_path_acceptance,
    )
    monkeypatch.setattr(
        snapshot_module,
        "_entry_lstat",
        replace_after_descriptor_acceptance,
    )
    destination = tmp_path / "snapshot-checkpoint-pre-open-race"
    destination.mkdir()
    try:
        exported = host.export_portable_snapshot(destination)
    finally:
        if swapped:
            source.unlink()
            retained.rename(source)
        await host.aclose()

    assert swapped is True
    assert exported.ok is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX retained descriptor boundary")
@pytest.mark.anyio
async def test_retained_snapshot_rejects_checkpoint_replacement_during_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, _artifacts, _payload, _metadata = await _artifact_backed_host(
        tmp_path, retained=True
    )
    storage = tmp_path / "profile" / "generation-storage" / "g0"
    source = storage / "checkpoints.sqlite3"
    retained = tmp_path / "retained-checkpoints.sqlite3"
    outside = tmp_path / "outside-checkpoints.sqlite3"
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(outside) as outside_connection:
            source_connection.backup(outside_connection)
    with sqlite3.connect(outside) as connection:
        connection.execute(
            "UPDATE records SET recorded_at = '2000-01-01T00:00:00+00:00'"
        )
        connection.commit()
    outside_before = outside.read_bytes()

    import loopplane.host.snapshot as snapshot_module

    original_connect = snapshot_module.sqlite3.connect
    swapped = False

    def replace_before_connect(
        database: str | Path, *args: object, **kwargs: object
    ) -> sqlite3.Connection:
        nonlocal swapped
        if not swapped and "mode=ro" in str(database):
            source.rename(retained)
            source.symlink_to(outside)
            swapped = True
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(snapshot_module.sqlite3, "connect", replace_before_connect)
    destination = tmp_path / "snapshot-checkpoint-race"
    destination.mkdir()
    try:
        exported = host.export_portable_snapshot(destination)
    finally:
        if swapped:
            source.unlink()
            retained.rename(source)
        await host.aclose()

    assert swapped is True
    assert exported.ok is False
    assert outside.read_bytes() == outside_before


@pytest.mark.skipif(os.name == "nt", reason="POSIX retained descriptor boundary")
@pytest.mark.anyio
async def test_retained_snapshot_rejects_artifact_ancestor_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, artifacts, _payload, _metadata = await _artifact_backed_host(
        tmp_path, retained=True
    )
    retained = tmp_path / "retained-artifacts"
    outside = tmp_path / "outside-artifacts"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("outside-sentinel", encoding="utf-8")

    import loopplane.host.snapshot as snapshot_module

    original_open = snapshot_module.os.open
    swapped = False

    def replace_after_open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if not swapped and path == "artifacts" and dir_fd is not None:
            artifacts.rename(retained)
            artifacts.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptor

    monkeypatch.setattr(snapshot_module.os, "open", replace_after_open)
    destination = tmp_path / "snapshot-ancestor-race"
    destination.mkdir()
    try:
        exported = host.export_portable_snapshot(destination)
    finally:
        if swapped:
            artifacts.unlink()
            retained.rename(artifacts)
        await host.aclose()

    assert swapped is True
    assert exported.ok is False
    assert sentinel.read_text(encoding="utf-8") == "outside-sentinel"


@pytest.mark.skipif(os.name == "nt", reason="POSIX retained descriptor boundary")
@pytest.mark.anyio
@pytest.mark.parametrize("replaced_ancestor", ["session", "artifacts"])
async def test_retained_snapshot_rejects_inventory_preopen_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replaced_ancestor: str,
) -> None:
    host, artifacts, payload, _metadata = await _artifact_backed_host(
        tmp_path, retained=True
    )
    session = artifacts.parent
    target = session if replaced_ancestor == "session" else artifacts
    retained = tmp_path / f"retained-preopen-{replaced_ancestor}"
    replacement = tmp_path / f"replacement-preopen-{replaced_ancestor}"
    shutil.copytree(target, replacement)
    replacement_payload = next(replacement.rglob(payload.name))
    replacement_payload.write_bytes(b"X" * len(payload.read_bytes()))

    import loopplane.host.snapshot as snapshot_module

    original_entry_lstat = snapshot_module._entry_lstat
    matching_stats = 0
    swapped = False

    def replace_before_descriptor_open(parent_fd: int, name: str) -> os.stat_result:
        nonlocal matching_stats, swapped
        if name == target.name:
            matching_stats += 1
            if matching_stats == 2:
                target.rename(retained)
                replacement.rename(target)
                swapped = True
        return original_entry_lstat(parent_fd, name)

    monkeypatch.setattr(
        snapshot_module,
        "_entry_lstat",
        replace_before_descriptor_open,
    )
    destination = tmp_path / f"snapshot-{replaced_ancestor}-preopen-race"
    destination.mkdir()
    try:
        exported = host.export_portable_snapshot(destination)
    finally:
        if swapped:
            shutil.rmtree(target)
            retained.rename(target)
        await host.aclose()

    assert swapped is True
    assert exported.ok is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX retained descriptor boundary")
@pytest.mark.anyio
@pytest.mark.parametrize("replaced_ancestor", ["session", "artifacts"])
async def test_retained_snapshot_rejects_inventory_copy_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replaced_ancestor: str,
) -> None:
    host, artifacts, payload, _metadata = await _artifact_backed_host(
        tmp_path, retained=True
    )
    session = artifacts.parent
    target = session if replaced_ancestor == "session" else artifacts
    retained = tmp_path / f"retained-{replaced_ancestor}"
    replacement = tmp_path / f"replacement-{replaced_ancestor}"
    shutil.copytree(target, replacement)
    replacement_payload = next(replacement.rglob(payload.name))
    replacement_payload.write_bytes(b"X" * len(payload.read_bytes()))

    import loopplane.host.snapshot as snapshot_module

    original_entry_lstat = snapshot_module._entry_lstat
    matching_stats = 0
    swapped = False

    def replace_before_copy_acceptance(parent_fd: int, name: str) -> os.stat_result:
        nonlocal matching_stats, swapped
        if name == target.name:
            matching_stats += 1
            if matching_stats == 4:
                target.rename(retained)
                replacement.rename(target)
                swapped = True
        return original_entry_lstat(parent_fd, name)

    monkeypatch.setattr(
        snapshot_module,
        "_entry_lstat",
        replace_before_copy_acceptance,
    )
    destination = tmp_path / f"snapshot-{replaced_ancestor}-inventory-race"
    destination.mkdir()
    try:
        exported = host.export_portable_snapshot(destination)
    finally:
        if swapped:
            shutil.rmtree(target)
            retained.rename(target)
        await host.aclose()

    assert swapped is True
    assert exported.ok is False
