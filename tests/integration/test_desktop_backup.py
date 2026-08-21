"""Portable Desktop backup round trip (078 T069)."""

from __future__ import annotations

import json
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

from loopplane.checkpoint.records import (
    AssistantMessageRecord,
    ReplacementDecisionRecord,
    SessionMetaRecord,
    TerminationRecord,
    ToolResultRecord,
    UserInputRecord,
    deserialize_record,
)
from loopplane.host import (
    DesktopStorageAuthorityFactory,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
)

from .conftest import BIG_TOOL, EventCollector, big_tool_model

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

from archive import validate_archive  # noqa: E402
from durability import initialize_runtime_storage  # noqa: E402
from methods.backup import BackupMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from projects import ProjectStore  # noqa: E402
from restore import RestoreManager  # noqa: E402

pytestmark = pytest.mark.anyio

INITIALIZE_PARAMS = {
    "protocol": {"name": "loopplane.desktop.stdio", "major": 1, "minor": 0},
    "runtime_event_schema": 1,
    "client": {"name": "test-client", "version": "0"},
    "requested_capabilities": [],
}


def _stage_manifest_declared_members(archive: Path, destination: Path) -> None:
    """Test-only staging uses the production manifest-first validation seam.

    It intentionally does not call ``ZipFile.extractall``: restore's adversarial
    extraction ownership remains T070.
    """

    manifest = validate_archive(archive)
    with zipfile.ZipFile(archive) as source:
        for entry in manifest["entries"]:
            relative = Path(str(entry["path"]))
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with (
                source.open(str(entry["path"]), "r") as reader,
                target.open("xb") as writer,
            ):
                while chunk := reader.read(64 * 1024):
                    written += len(chunk)
                    assert written <= int(entry["size"])
                    writer.write(chunk)
            assert written == entry["size"]


async def test_backup_round_trip_preserves_projects_star_preferences_and_artifact(
    tmp_path: Path,
) -> None:
    state = ProfileState.open(tmp_path / "profile")
    storage = initialize_runtime_storage(state.root, "g0")
    host = LoopPlaneHost(
        RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(
                authority=DesktopStorageAuthorityFactory(state.root),
                root=storage,
                checkpoint_backend="sqlite",
                # Let the checkpoint replacement ledger create the one
                # checkpoint-referenced artifact; a pre-ledger Gateway offload
                # would intentionally be rejected as unreferenced.
                artifact_threshold_bytes=1_000_000,
                replacement_budget_bytes=1,
            ),
        ),
        working_scope=tmp_path,
    )
    outcome = await host.run(
        "archive this",
        EventCollector(),
        principal_id=state.principal_id,
    )
    await host.set_session_starred(outcome.session_id, True)
    host.enable_desktop_portable_snapshot()

    projects = ProjectStore(state)
    project = projects.create(label="Desktop project")
    projects.assign_session(project["id"], outcome.session_id)
    state.set_preference("theme", "dark")
    # ProfileState strips transient drafts before persistence/export.
    state.save_portable({**state.load_portable(), "composer_draft": "transient"})

    exported_snapshot = tmp_path / "host-snapshot"
    exported_snapshot.mkdir()
    exported = host.export_portable_snapshot(exported_snapshot)
    assert exported.ok, exported.reason

    archive = tmp_path / "portable.zip"
    methods = BackupMethods(host, state, ProfileMutationLease())
    result = await methods.create(
        {
            "mutation_id": "backup-1",
            "acknowledgement": True,
            "destination_path": str(archive),
        }
    )

    assert result["finalized"] is True
    manifest = validate_archive(archive)
    assert manifest["disclosure"] == {"version": 1, "acknowledged": True}
    assert any(entry["content_class"] == "artifact" for entry in manifest["entries"])
    assert all(len(str(entry["sha256"])) == 64 for entry in manifest["entries"])

    staging = tmp_path / "read-only-stage"
    staging.mkdir()
    _stage_manifest_declared_members(archive, staging)
    validation = host.validate_portable_snapshot(staging)
    assert validation.ok is True

    with sqlite3.connect(staging / "sessions" / "checkpoints.sqlite3") as connection:
        rows = connection.execute(
            "SELECT data FROM records WHERE session_id = ? ORDER BY sequence",
            (outcome.session_id,),
        ).fetchall()
    records = [deserialize_record(encoded) for (encoded,) in rows]
    assert all(record is not None for record in records)
    typed_records = [record for record in records if record is not None]
    session_meta = [
        record for record in typed_records if isinstance(record, SessionMetaRecord)
    ]
    user_input = next(
        record for record in typed_records if isinstance(record, UserInputRecord)
    )
    assert session_meta
    assert all(
        record.payload.principal_id == state.principal_id for record in session_meta
    )
    assert session_meta[-1].payload.starred is True
    assert any(
        getattr(block, "text", None) == "archive this"
        for block in user_input.payload.blocks
    )
    assert any(isinstance(record, AssistantMessageRecord) for record in typed_records)
    assert any(isinstance(record, ToolResultRecord) for record in typed_records)
    assert any(
        isinstance(record, ReplacementDecisionRecord) for record in typed_records
    )
    assert any(isinstance(record, TerminationRecord) for record in typed_records)

    original_artifact = next(
        (storage / outcome.session_id / "artifacts").glob("*.txt")
    ).read_bytes()
    restored_artifact = next(
        (staging / "artifacts" / outcome.session_id).glob("*.txt")
    ).read_bytes()
    assert restored_artifact == original_artifact

    profile = json.loads((staging / "profile" / "profile.json").read_text("utf-8"))
    assert profile["projects"] == [
        {
            "id": project["id"],
            "label": "Desktop project",
            "session_ids": [outcome.session_id],
            "workspace_id": None,
        }
    ]
    assert profile["preferences"] == {"theme": "dark"}
    assert "composer_draft" not in profile
    # Preview data comes from the production staged-restore validation seam.
    preview = (
        RestoreManager(tmp_path / "restore-profile").validate_archive(archive).summary
    )
    assert preview == {
        "entry_count": manifest["totals"]["entries"],
        "project_count": 1,
        "session_count": 1,
        "artifact_count": 1,
        "has_manifest": True,
        "has_profile": True,
        "format": "loopplane.desktop.backup",
        "version": manifest["version"],
        "created_at": manifest["created_at"],
        "drafts_excluded": True,
        "relink_required": True,
    }


async def test_backup_public_seam_never_materializes_checkpoint_or_artifact_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The complete Host-export-to-archive path must use bounded streams."""

    import archive as archive_module

    import loopplane.host.snapshot as snapshot_module

    state = ProfileState.open(tmp_path / "profile")
    storage = initialize_runtime_storage(state.root, "g0")
    host = LoopPlaneHost(
        RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(
                authority=DesktopStorageAuthorityFactory(state.root),
                root=storage,
                checkpoint_backend="sqlite",
                artifact_threshold_bytes=1_000_000,
                replacement_budget_bytes=1,
            ),
        ),
        working_scope=tmp_path,
    )
    await host.run("stream this", EventCollector())
    host.enable_desktop_portable_snapshot()

    snapshot_read = snapshot_module._read_stable
    archive_read = archive_module._read_stable

    def forbid_unbounded_snapshot_read(path: Path) -> bytes:
        if path.name == "checkpoints.sqlite3" or path.suffix == ".txt":
            raise AssertionError("checkpoint/artifact bytes must stream")
        return snapshot_read(path)

    def forbid_unbounded_archive_read(path: Path) -> bytes:
        if path.name == "checkpoints.sqlite3" or path.suffix == ".txt":
            raise AssertionError("checkpoint/artifact bytes must stream")
        return archive_read(path)

    monkeypatch.setattr(snapshot_module, "_read_stable", forbid_unbounded_snapshot_read)
    monkeypatch.setattr(archive_module, "_read_stable", forbid_unbounded_archive_read)

    result = await BackupMethods(host, state, ProfileMutationLease()).create(
        {
            "mutation_id": "streaming-backup",
            "acknowledgement": True,
            "destination_path": str(tmp_path / "streaming.zip"),
        }
    )

    assert result["finalized"] is True


async def test_shutdown_keeps_backup_mutation_lease_and_starts_no_durable_work(
    tmp_path: Path,
) -> None:
    from bridge import build_rpc_dispatcher

    class HostSentinel:
        called = False

        def __getattr__(self, _name: str) -> object:
            self.called = True
            raise AssertionError("shutdown must not start Host durable work")

    lease = ProfileMutationLease()
    lease.acquire("backup", "backup-in-flight")
    shutdown_calls: list[str] = []

    async def shutdown_hook() -> None:
        shutdown_calls.append("closed-existing-context")

    host = HostSentinel()
    dispatcher = build_rpc_dispatcher(  # type: ignore[arg-type]
        host,
        mutation_lease=lease,
        on_shutdown=shutdown_hook,
    )
    await dispatcher.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": INITIALIZE_PARAMS,
            }
        )
    )
    response = await dispatcher.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "shutdown",
                "method": "system.shutdown",
                "params": {},
            }
        )
    )

    assert response[0]["result"] == {"ok": True}
    assert shutdown_calls == ["closed-existing-context"]
    assert host.called is False
    assert lease.held_by("backup", "backup-in-flight")
