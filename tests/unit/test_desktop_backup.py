"""Desktop backup/restore lease + archive skeleton (078 T076/T077)."""

from __future__ import annotations

import errno
import hashlib
import json
import stat
import sys
import unicodedata
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

import methods.backup as backup_methods_module  # noqa: E402
from archive import (  # noqa: E402
    ArchiveValidationError,
    create_portable_archive,
    validate_archive,
)
from backup import describe_backup  # noqa: E402
from interaction import InteractionLease  # noqa: E402
from methods.backup import BackupMethods  # noqa: E402
from methods.inspection import InspectionMethods  # noqa: E402
from methods.interaction import InteractionMethods  # noqa: E402
from methods.projects import ProjectMethods  # noqa: E402
from methods.sessions import SessionMethods  # noqa: E402
from methods.workspace import WorkspaceMethods  # noqa: E402
from mutation_lease import MutationLeaseBusy, ProfileMutationLease  # noqa: E402
from protocol import RpcError  # noqa: E402

INITIALIZE_PARAMS = {
    "protocol": {"name": "loopplane.desktop.stdio", "major": 1, "minor": 0},
    "runtime_event_schema": 1,
    "client": {"name": "test-client", "version": "0"},
    "requested_capabilities": [],
}
from restore import RestoreManager  # noqa: E402

pytestmark = pytest.mark.anyio


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


def test_describe_excludes_drafts_and_secrets() -> None:
    d = describe_backup().to_public()
    assert "unencrypted" in d["disclosure"].lower()
    assert "unsent_drafts" in d["excludes"]
    assert "credentials" in d["excludes"]


def test_canonical_archive_records_safe_profile_and_integrity(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    (snapshot / "sessions").mkdir(parents=True)
    (snapshot / "sessions" / "checkpoints.sqlite3").write_bytes(b"sqlite-snapshot")
    destination = tmp_path / "portable.zip"

    result = create_portable_archive(
        destination,
        profile_portable={
            "schema_version": 1,
            "profile_id": "profile-opaque",
            "principal_id": "principal-opaque",
            "projects": [{"id": "project", "label": "Work", "session_ids": ["s"]}],
            "preferences": {"theme": "dark", "composer_draft": "unsent"},
            "workspace_references": [
                {"id": "workspace", "label": "Docs", "availability": "available"}
            ],
            "credentials": {"token": "must-not-export"},
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )

    assert result["finalized"] is True
    manifest = validate_archive(destination)
    assert manifest["format"] == "loopplane.desktop.backup"
    assert manifest["version"] == {"major": 1, "minor": 0}
    assert manifest["disclosure"] == {"version": 1, "acknowledged": True}
    assert manifest["totals"]["entries"] == 2
    assert [entry["path"] for entry in manifest["entries"]] == [
        "profile/profile.json",
        "sessions/checkpoints.sqlite3",
    ]
    with zipfile.ZipFile(destination) as zf:
        profile = json.loads(zf.read("profile/profile.json"))
    assert profile["preferences"] == {"theme": "dark"}
    assert profile["workspace_references"][0]["availability"] == "relink_required"
    assert "credentials" not in profile


def test_external_electron_oauth_vault_cannot_enter_profile_backup(
    tmp_path: Path,
) -> None:
    sentinel = b"refresh-token-084-outside-profile"
    user_data = tmp_path / "userData"
    user_data.mkdir()
    (user_data / "mcp-authorization.bin").write_bytes(sentinel)

    snapshot = tmp_path / "profile-snapshot"
    (snapshot / "sessions").mkdir(parents=True)
    (snapshot / "sessions" / "checkpoints.sqlite3").write_bytes(b"sqlite")
    destination = tmp_path / "portable.zip"
    create_portable_archive(
        destination,
        profile_portable={
            "schema_version": 1,
            "profile_id": "profile-opaque",
            "principal_id": "principal-opaque",
            "projects": [],
            "preferences": {},
            "workspace_references": [],
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )

    with zipfile.ZipFile(destination) as archive:
        payload = b"".join(archive.read(name) for name in archive.namelist())
        assert all("mcp-authorization" not in name for name in archive.namelist())
    assert sentinel not in payload


async def test_snapshot_failure_uses_the_sole_fallback_without_replacing_destination(
    tmp_path: Path,
) -> None:
    from bridge import build_rpc_dispatcher

    destination = tmp_path / "existing.zip"
    destination.write_bytes(b"keep-existing-destination")
    state = ProfileState.open(tmp_path / "profile")
    dispatcher = build_rpc_dispatcher(
        _host(tmp_path),
        working_scope=tmp_path,
        profile_state=state,
        mutation_lease=ProfileMutationLease(),
        principal_id=state.principal_id,
    )
    await dispatcher.handle_frame(  # type: ignore[attr-defined]
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": INITIALIZE_PARAMS,
            }
        )
    )

    response = await dispatcher.handle_frame(  # type: ignore[attr-defined]
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "backup-create",
                "method": "backup.create",
                "params": {
                    "mutation_id": "backup",
                    "acknowledgement": True,
                    "destination_path": str(destination),
                },
            }
        )
    )

    assert response[0]["error"] == {
        "code": -32603,
        "message": "Internal failure",
        "data": {
            "category": "internal_failure",
            "retryable": True,
            "messageKey": "desktop.error.internal_failure",
            "recovery": "restart_runtime",
        },
    }
    assert destination.read_bytes() == b"keep-existing-destination"


async def test_backup_insufficient_space_uses_the_exact_public_error_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SnapshotHost:
        def export_portable_snapshot(self, _destination: Path) -> SimpleNamespace:
            return SimpleNamespace(ok=True)

    def no_space(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise OSError(errno.ENOSPC, "test-only disk full")

    monkeypatch.setattr(backup_methods_module, "create_backup_archive", no_space)
    lease = ProfileMutationLease()
    methods = BackupMethods(  # type: ignore[arg-type]
        SnapshotHost(),
        ProfileState.open(tmp_path / "profile"),
        lease,
    )

    with pytest.raises(RpcError) as caught:
        await methods.create(
            {
                "mutation_id": "backup-no-space",
                "acknowledgement": True,
                "destination_path": str(tmp_path / "backup.zip"),
            }
        )

    assert caught.value.to_jsonrpc() == {
        "code": -32008,
        "message": "Unavailable",
        "data": {
            "category": "unavailable",
            "retryable": True,
            "messageKey": "backup.error.insufficient_space",
            "recovery": "retry",
        },
    }
    assert lease.held() is False


async def test_restore_validation_failure_releases_reservation_and_token(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    (snapshot / "sessions").mkdir(parents=True)
    (snapshot / "sessions" / "checkpoints.sqlite3").write_bytes(b"not-a-database")
    archive = tmp_path / "input.zip"
    create_portable_archive(
        archive,
        profile_portable={
            "schema_version": 1,
            "profile_id": "profile",
            "principal_id": "principal",
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )
    manager = RestoreManager(tmp_path / "profile")
    lease = ProfileMutationLease()
    methods = BackupMethods(
        _host(tmp_path),
        ProfileState.open(tmp_path / "profile"),
        lease,
        restore_manager=manager,
    )

    with pytest.raises(RpcError) as exc:
        await methods.restore_validate(
            {"mutation_id": "restore", "source_path": str(archive)}
        )

    assert exc.value.category == "unsafe_input"
    assert lease.held() is False
    assert manager.has_active_reservation() is False


async def test_backup_create_holds_lease_and_blocks_second_writer(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)

    async def sink(_event: object) -> None:
        return None

    await host.run("durable", sink)
    host.enable_desktop_portable_snapshot()
    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    methods = BackupMethods(host, state, lease)
    # Hold lease as another writer (restore) so backup is busy.
    lease.acquire("restore")
    with pytest.raises(RpcError) as exc:
        await methods.create(
            {
                "mutation_id": "m1",
                "acknowledgement": True,
                "destination_path": str(tmp_path / "a.zip"),
            }
        )
    assert exc.value.category == "busy"
    lease.release("restore")
    out = await methods.create(
        {
            "mutation_id": "m2",
            "acknowledgement": True,
            "destination_path": str(tmp_path / "a.zip"),
        }
    )
    assert out["finalized"] is True
    assert lease.held() is False


async def test_restore_validate_issues_token_and_cancel_cleans(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    state = ProfileState.open(tmp_path / "profile")

    async def sink(_event: object) -> None:
        return None

    await host.run("durable", sink, principal_id=state.principal_id)
    host.enable_desktop_portable_snapshot()
    lease = ProfileMutationLease()
    archive = tmp_path / "in.zip"
    methods = BackupMethods(
        host, state, lease, restore_manager=RestoreManager(tmp_path / "profile")
    )
    await methods.create(
        {
            "mutation_id": "backup",
            "acknowledgement": True,
            "destination_path": str(archive),
        }
    )
    validated = await methods.restore_validate(
        {
            "mutation_id": "m1",
            "source_path": str(archive),
        }
    )
    token = validated["restore_token"]
    assert validated["summary"]["relink_required"] is True
    assert lease.owner == "restore"
    # Same mutation returns the original reservation, rather than restaging.
    assert (
        await methods.restore_validate(
            {"mutation_id": "m1", "source_path": str(archive)}
        )
        == validated
    )
    cancelled = await methods.restore_cancel(
        {"mutation_id": "m1", "restore_token": token}
    )
    assert cancelled["cancelled"] is True
    assert lease.held() is False


async def test_backup_blocked_when_interaction_active(tmp_path: Path) -> None:
    host = _host(tmp_path)
    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    ilease = InteractionLease()
    # Manually mark interaction owner without full host session for busy gate
    ilease._owner = type(  # noqa: SLF001
        "O",
        (),
        {"released": False, "pane_id": "p", "session_id": "s"},
    )()
    methods = BackupMethods(host, state, lease, interaction_lease=ilease)
    with pytest.raises(RpcError) as exc:
        await methods.create(
            {
                "mutation_id": "m1",
                "acknowledgement": True,
                "destination_path": str(tmp_path / "b.zip"),
            }
        )
    assert exc.value.category == "busy"


async def test_backup_lease_rejects_interactive_open_before_host_dispatch() -> None:
    class TrackingHost:
        called = False

        def session(self, *args: object, **kwargs: object) -> object:
            self.called = True
            raise AssertionError("Host must not be reached while backup owns lease")

    host = TrackingHost()
    lease = ProfileMutationLease()
    lease.acquire("backup")
    methods = InteractionMethods(
        host,  # type: ignore[arg-type]
        InteractionLease(),
        mutation_lease=lease,
    )

    with pytest.raises(RpcError) as exc:
        await methods.create_interactive({"mutation_id": "interactive"})

    assert exc.value.category == "busy"
    assert host.called is False


async def test_backup_lease_rejects_interaction_writes_before_session_dispatch() -> (
    None
):
    class TrackingSession:
        called = False

        async def submit(self, *_args: object, **_kwargs: object) -> object:
            self.called = True
            raise AssertionError("Session must not be reached while backup owns lease")

        def answer_approval(self, *_args: object, **_kwargs: object) -> bool:
            self.called = True
            raise AssertionError("Session must not be reached while backup owns lease")

        def answer_question(self, *_args: object, **_kwargs: object) -> bool:
            self.called = True
            raise AssertionError("Session must not be reached while backup owns lease")

    session = TrackingSession()
    interaction = InteractionLease()
    subscription = SimpleNamespace(
        subscription_id="subscription",
        session_id="session",
        pane_id=None,
        session=session,
        run_active=False,
        released=False,
    )
    interaction._owner = subscription  # noqa: SLF001
    interaction._pending[subscription.subscription_id] = subscription  # noqa: SLF001
    lease = ProfileMutationLease()
    lease.acquire("backup")
    methods = InteractionMethods(
        object(),  # type: ignore[arg-type]
        interaction,
        mutation_lease=lease,
    )

    for method, params in (
        (methods.submit, {"prompt": "continue"}),
        (methods.answer_approval, {"request_id": "approval", "allow": True}),
        (methods.answer_question, {"request_id": "question", "answers": ["yes"]}),
    ):
        with pytest.raises(RpcError) as exc:
            await method(
                {
                    "mutation_id": "interaction",
                    "subscription_id": "subscription",
                    **params,
                }
            )
        assert exc.value.category == "busy"

    assert session.called is False


async def test_restore_commit_and_cancel_require_active_restore_owner(
    tmp_path: Path,
) -> None:
    class TrackingRestore:
        cancelled = False

        def get(self, _token: str) -> object:
            return object()

        def cancel(self, _token: str) -> bool:
            self.cancelled = True
            return True

    restore = TrackingRestore()
    methods = BackupMethods(
        _host(tmp_path),
        ProfileState.open(tmp_path / "profile"),
        ProfileMutationLease(),
        restore_manager=restore,  # type: ignore[arg-type]
    )

    with pytest.raises(RpcError) as exc:
        await methods.restore_commit(
            {"mutation_id": "commit", "restore_token": "token", "confirmation": True}
        )
    assert exc.value.category == "busy"

    with pytest.raises(RpcError) as exc:
        await methods.restore_cancel(
            {"mutation_id": "cancel", "restore_token": "token"}
        )
    assert exc.value.category == "busy"
    assert restore.cancelled is False


def _snapshot_tree(root: Path) -> Path:
    snapshot = root / "snapshot"
    (snapshot / "sessions").mkdir(parents=True)
    (snapshot / "sessions" / "checkpoints.sqlite3").write_bytes(b"sqlite-snapshot")
    return snapshot


def _manifest_for(entries: list[tuple[str, str, bytes]]) -> dict[str, object]:
    declared = [
        {
            "path": path,
            "kind": "regular_file",
            "content_class": content_class,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, content_class, payload in entries
    ]
    return {
        "format": "loopplane.desktop.backup",
        "version": {"major": 1, "minor": 0},
        "profile_schema_version": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "profile_id": "profile",
        "principal_id": "principal",
        "disclosure": {"version": 1, "acknowledged": True},
        "totals": {
            "entries": len(declared),
            "compressed_bytes": sum(len(payload) for _, _, payload in entries),
            "uncompressed_bytes": sum(len(payload) for _, _, payload in entries),
        },
        "entries": declared,
    }


def _write_archive(
    path: Path,
    entries: list[tuple[str, str, bytes]],
    *,
    manifest: dict[str, object] | None = None,
    compression: int = zipfile.ZIP_STORED,
    external_mode: int = stat.S_IFREG,
) -> None:
    manifest = manifest or _manifest_for(entries)
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        manifest_info = zipfile.ZipInfo("manifest.json")
        manifest_info.external_attr = stat.S_IFREG << 16
        archive.writestr(
            manifest_info,
            json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        )
        for name, _content_class, payload in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = compression
            info.external_attr = external_mode << 16
            archive.writestr(info, payload)


def test_mutation_lease_reenters_only_the_same_operation_identity() -> None:
    lease = ProfileMutationLease()

    lease.acquire("session", "request-a")
    lease.acquire("session", "request-a")
    with pytest.raises(MutationLeaseBusy):
        lease.acquire("session", "request-b")

    assert lease.owner == "session"
    lease.release("session", "request-a")
    assert lease.held() is True
    lease.release("session", "request-a")
    assert lease.held() is False


def test_mutation_lease_requires_the_same_owner_and_identity_pair() -> None:
    lease = ProfileMutationLease()
    lease.acquire("backup", "shared-request")

    with pytest.raises(MutationLeaseBusy):
        lease.acquire("restore", "shared-request")
    with pytest.raises(MutationLeaseBusy):
        lease.require_free_or_owner("restore", "shared-request")
    # The legacy one-argument release normalizes identity to its owner; it must
    # not release a same-category operation carrying a distinct request token.
    with pytest.raises(MutationLeaseBusy):
        lease.release("backup")

    assert lease.held_by("backup", "shared-request")


async def test_backup_held_lease_rejects_competing_backup_and_restore(
    tmp_path: Path,
) -> None:
    lease = ProfileMutationLease()
    lease.acquire("backup", "backup-active")
    methods = BackupMethods(
        _host(tmp_path), ProfileState.open(tmp_path / "profile"), lease
    )

    with pytest.raises(RpcError) as backup_exc:
        await methods.create(
            {
                "mutation_id": "backup-competing",
                "acknowledgement": True,
                "destination_path": str(tmp_path / "other.zip"),
            }
        )
    with pytest.raises(RpcError) as restore_exc:
        await methods.restore_validate(
            {"mutation_id": "restore-competing", "source_path": str(tmp_path / "x.zip")}
        )

    assert backup_exc.value.category == "busy"
    assert restore_exc.value.category == "busy"


async def test_backup_lease_blocks_every_exposed_writer_before_dispatch(
    tmp_path: Path,
) -> None:
    """Projects and Workspace are the only existing exposed profile-write seams."""

    class DispatchSentinel:
        called = False

        def __getattr__(self, _name: str) -> object:
            def forbidden(*_args: object, **_kwargs: object) -> object:
                self.called = True
                raise AssertionError("Host/Profile/Store dispatch must not occur")

            return forbidden

    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    lease.acquire("backup", "backup-held")
    sentinel = DispatchSentinel()

    sessions = SessionMethods(sentinel, lease)  # type: ignore[arg-type]
    projects = ProjectMethods(state, lease)
    projects._store = sentinel  # type: ignore[assignment]  # noqa: SLF001
    workspaces = WorkspaceMethods(state, lease)
    workspaces._store = sentinel  # type: ignore[assignment]  # noqa: SLF001
    capabilities = InspectionMethods(  # type: ignore[call-arg]
        sentinel, mutation_lease=lease
    )

    calls = (
        (sessions.rename, {"mutation_id": "s1", "session_id": "s", "title": "n"}),
        (
            sessions.set_starred,
            {"mutation_id": "s2", "session_id": "s", "starred": True},
        ),
        (
            sessions.delete,
            {"mutation_id": "s3", "session_id": "s", "confirmation": True},
        ),
        (
            sessions.fork,
            {"mutation_id": "s4", "session_id": "s", "confirmation": True},
        ),
        (projects.create, {"mutation_id": "p1", "label": "Project"}),
        (
            projects.rename,
            {"mutation_id": "p2", "project_id": "p", "label": "Renamed"},
        ),
        (projects.remove, {"mutation_id": "p3", "project_id": "p"}),
        (
            projects.assign_session,
            {"mutation_id": "p4", "project_id": "p", "session_id": "s"},
        ),
        (workspaces.bind, {"mutation_id": "w1", "path": str(tmp_path)}),
        (
            workspaces.relink,
            {"mutation_id": "w2", "workspace_id": "w", "path": str(tmp_path)},
        ),
        (workspaces.remove, {"mutation_id": "w3", "workspace_id": "w"}),
        (workspaces.revalidate, {"mutation_id": "w4", "workspace_id": "w"}),
        (
            capabilities.capabilities_invoke,
            {
                "mutation_id": "c1",
                "capability_id": "memory",
                "action": "refresh",
            },
        ),
    )
    for method, params in calls:
        with pytest.raises(RpcError) as exc:
            await method(params)
        assert exc.value.category == "busy"
    assert sentinel.called is False


async def test_backup_create_holds_the_same_identity_through_archive_finalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import archive as archive_module

    observations: list[str] = []
    lease = ProfileMutationLease()

    class ControlledHost:
        def export_portable_snapshot(self, destination: Path) -> object:
            assert lease.held_by("backup", "backup-1")
            observations.append("snapshot")
            (destination / "sessions").mkdir()
            (destination / "sessions" / "checkpoints.sqlite3").write_bytes(b"db")
            return SimpleNamespace(ok=True)

    original_flush = archive_module._flush_file

    def observe_archive_finalization(path: Path) -> None:
        assert lease.held_by("backup", "backup-1")
        observations.append("archive-finalization")
        original_flush(path)

    monkeypatch.setattr(archive_module, "_flush_file", observe_archive_finalization)
    state = ProfileState.open(tmp_path / "profile")
    result = await BackupMethods(ControlledHost(), state, lease).create(  # type: ignore[arg-type]
        {
            "mutation_id": "backup-1",
            "acknowledgement": True,
            "destination_path": str(tmp_path / "portable.zip"),
        }
    )

    assert result["finalized"] is True
    assert observations == ["snapshot", "archive-finalization"]
    assert lease.held() is False


async def test_restore_commit_publishes_relinked_profile_and_releases_reservation(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    state = ProfileState.open(tmp_path / "profile")

    async def sink(_event: object) -> None:
        return None

    await host.run("durable", sink, principal_id=state.principal_id)
    host.enable_desktop_portable_snapshot()
    state.save_portable(
        {
            **state.load_portable(),
            "workspace_references": [
                {"id": "w", "label": "Docs", "availability": "available"}
            ],
        }
    )
    lease = ProfileMutationLease()
    restore = RestoreManager(tmp_path / "profile")
    methods = BackupMethods(host, state, lease, restore_manager=restore)
    archive = tmp_path / "restore-source.zip"
    await methods.create(
        {
            "mutation_id": "backup-source",
            "acknowledgement": True,
            "destination_path": str(archive),
        }
    )
    validated = await methods.restore_validate(
        {"mutation_id": "restore", "source_path": str(archive)}
    )
    before = state.portable_path().read_bytes()

    result = await methods.restore_commit(
        {
            "mutation_id": "restore",
            "restore_token": validated["restore_token"],
            "confirmation": True,
        }
    )

    assert result["committed"] is True
    assert result["relink_required"] is True
    assert state.portable_path().read_bytes() != before
    assert state.load_portable()["workspace_references"] == [
        {
            "id": "w",
            "label": "Docs",
            "availability": "relink_required",
            "actions": ["open", "relink", "remove"],
        }
    ]
    assert restore.has_active_reservation() is False
    assert lease.held() is False


async def test_restore_transition_rejects_token_without_exact_lease_mapping(
    tmp_path: Path,
) -> None:
    reservation_id = "restore-reservation-id"

    class Reservation:
        token = reservation_id

    class TrackingRestore:
        cancelled = False

        def get(self, token: str) -> Reservation | None:
            return Reservation() if token == reservation_id else None

        def cancel(self, _token: str) -> bool:
            self.cancelled = True
            return True

    state = ProfileState.open(tmp_path / "profile")
    before = state.portable_path().read_bytes()
    lease = ProfileMutationLease()
    lease.acquire("restore", "validated-request")
    restore = TrackingRestore()
    methods = BackupMethods(
        _host(tmp_path),
        state,
        lease,
        restore_manager=restore,  # type: ignore[arg-type]
    )

    with pytest.raises(RpcError) as exc:
        await methods.restore_commit(
            {
                "mutation_id": "restore-commit",
                "restore_token": reservation_id,
                "confirmation": True,
            }
        )

    assert exc.value.category == "busy"
    assert state.portable_path().read_bytes() == before
    assert restore.cancelled is False
    assert lease.held_by("restore", "validated-request")


@pytest.mark.parametrize(
    ("name", "external_mode"),
    [
        ("profile/profile.json", stat.S_IFLNK),
        ("profile/profile.json", stat.S_IFDIR),
    ],
)
def test_validator_rejects_non_regular_external_modes(
    tmp_path: Path, name: str, external_mode: int
) -> None:
    archive = tmp_path / "non-regular.zip"
    _write_archive(archive, [(name, "profile", b"{}")], external_mode=external_mode)

    with pytest.raises(ValueError) as exc:
        validate_archive(archive)

    assert name not in str(exc.value)


def test_validator_rejects_declared_single_entry_over_two_gib(tmp_path: Path) -> None:
    archive = tmp_path / "single-entry-limit.zip"
    entries = [("profile/profile.json", "profile", b"{}")]
    manifest = _manifest_for(entries)
    oversized = 2 * 1024 * 1024 * 1024 + 1
    manifest["entries"][0]["size"] = oversized  # type: ignore[index]
    manifest["totals"] = {
        "entries": 1,
        "compressed_bytes": len(entries[0][2]),
        "uncompressed_bytes": oversized,
    }
    _write_archive(archive, entries, manifest=manifest)

    with pytest.raises(ArchiveValidationError, match="manifest_limits"):
        validate_archive(archive)


def test_validator_rejects_single_entry_and_aggregate_expansion_limits(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "ratio.zip"
    payload = b"x" * 201_000
    entries = [("profile/profile.json", "profile", payload)]
    # First pass gives the deterministic DEFLATE compressed size needed by V1 totals.
    _write_archive(archive, entries, compression=zipfile.ZIP_DEFLATED)
    compressed = zipfile.ZipFile(archive).getinfo("profile/profile.json").compress_size
    manifest = _manifest_for(entries)
    manifest["totals"] = {
        "entries": 1,
        "compressed_bytes": compressed,
        "uncompressed_bytes": len(payload),
    }
    _write_archive(
        archive, entries, manifest=manifest, compression=zipfile.ZIP_DEFLATED
    )

    with pytest.raises(ValueError) as exc:
        validate_archive(archive)

    assert "profile/profile.json" not in str(exc.value)


def test_validator_rejects_deep_manifest_and_unsafe_or_colliding_names(
    tmp_path: Path,
) -> None:
    cases: list[tuple[str, list[tuple[str, str, bytes]], dict[str, object] | None]] = []
    unsafe = "artifacts/session/bad\x01.txt"
    cases.append(("control", [(unsafe, "artifact", b"")], None))
    terminal_dot = "artifacts/session/trailing.txt "
    cases.append(("terminal", [(terminal_dot, "artifact", b"")], None))
    nfc = "artifacts/session/é.txt"
    nfd = f"artifacts/session/{unicodedata.normalize('NFD', 'é')}.txt"
    cases.append(
        ("normalization", [(nfc, "artifact", b""), (nfd, "artifact", b"")], None)
    )
    cases.append(
        (
            "casefold",
            [
                ("artifacts/session/A.txt", "artifact", b""),
                ("artifacts/session/a.txt", "artifact", b""),
            ],
            None,
        )
    )
    deep_manifest = _manifest_for([("profile/profile.json", "profile", b"{}")])
    nested: object = "leaf"
    for _ in range(33):
        nested = [nested]
    deep_manifest["profile_id"] = nested
    cases.append(("depth", [("profile/profile.json", "profile", b"{}")], deep_manifest))

    for label, entries, manifest in cases:
        archive = tmp_path / f"{label}.zip"
        _write_archive(archive, entries, manifest=manifest)
        with pytest.raises(ValueError) as exc:
            validate_archive(archive)
        assert all(name not in str(exc.value) for name, _class, _payload in entries)


def test_validator_rejects_a_single_non_nfc_path(tmp_path: Path) -> None:
    decomposed = unicodedata.normalize("NFD", "é")
    path = f"artifacts/session/{decomposed}.txt"
    archive = tmp_path / "non-nfc.zip"
    _write_archive(archive, [(path, "artifact", b"")])

    with pytest.raises(ArchiveValidationError, match="archive_path_invalid"):
        validate_archive(archive)


@pytest.mark.parametrize("stage", ["write", "revalidate", "file_flush"])
def test_prepublication_failure_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    import archive as archive_module

    destination = tmp_path / "existing.zip"
    old = b"old-destination-bytes"
    destination.write_bytes(old)
    snapshot = _snapshot_tree(tmp_path)
    kwargs = {
        "profile_portable": {
            "schema_version": 1,
            "profile_id": "p",
            "principal_id": "u",
        },
        "snapshot_root": snapshot,
        "disclosure_acknowledged": True,
    }
    if stage == "write":
        monkeypatch.setattr(
            zipfile.ZipFile,
            "writestr",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("write failed")),
        )
    elif stage == "revalidate":
        monkeypatch.setattr(
            archive_module,
            "validate_archive",
            lambda _path: (_ for _ in ()).throw(ValueError("revalidation failed")),
        )
    else:
        monkeypatch.setattr(
            archive_module,
            "_flush_file",
            lambda _path: (_ for _ in ()).throw(OSError("flush failed")),
        )

    with pytest.raises((OSError, ValueError)):
        create_portable_archive(destination, **kwargs)
    assert destination.read_bytes() == old


def test_post_publication_directory_flush_failure_is_not_reported_as_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import archive as archive_module

    destination = tmp_path / "existing.zip"
    old = b"old-destination-bytes"
    destination.write_bytes(old)
    snapshot = _snapshot_tree(tmp_path)
    monkeypatch.setattr(
        archive_module,
        "_flush_directory",
        lambda _path: (_ for _ in ()).throw(OSError("directory flush failed")),
    )

    with pytest.raises(OSError):
        create_portable_archive(
            destination,
            profile_portable={
                "schema_version": 1,
                "profile_id": "p",
                "principal_id": "u",
            },
            snapshot_root=snapshot,
            disclosure_acknowledged=True,
        )
    assert destination.read_bytes() != old
