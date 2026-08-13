"""T070 public RPC integration RED tests for restore reservation and handover."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

from loopplane.host import (
    DesktopStorageAuthorityFactory,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
)
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

from .conftest import BIG_TOOL, big_tool_model

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

from archive import canonical_json  # noqa: E402
from durability import initialize_runtime_storage  # noqa: E402
from methods.backup import BackupMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from projects import ProjectStore  # noqa: E402
from protocol import (  # noqa: E402
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
    PROTOCOL_NAME,
    RUNTIME_EVENT_SCHEMA,
    RpcError,
)
from workspace import WorkspaceStore  # noqa: E402

pytestmark = pytest.mark.anyio

_PUBLICATION_RESTART_ERROR = {
    "code": -32012,
    "message": "Publication failed",
    "data": {
        "category": "publication_failed",
        "retryable": False,
        "messageKey": "restore.error.publication_failed_restart",
        "recovery": "restart_runtime",
    },
}
_ROLLED_BACK_ERROR = {
    "code": -32012,
    "message": "Publication failed",
    "data": {
        "category": "publication_failed",
        "retryable": True,
        "messageKey": "restore.error.rolled_back",
        "recovery": "retry",
    },
}
_INTERNAL_FALLBACK_ERROR = {
    "code": -32603,
    "message": "Internal failure",
    "data": {
        "category": "internal_failure",
        "retryable": True,
        "messageKey": "desktop.error.internal_failure",
        "recovery": "restart_runtime",
    },
}
_INTEGRITY_FAILED_ERROR = {
    "code": -32007,
    "message": "Unsafe input",
    "data": {
        "category": "unsafe_input",
        "retryable": False,
        "messageKey": "backup.error.integrity_failed",
    },
}


async def _rpc(dispatcher: object, request_id: int, method: str, params: dict) -> dict:
    frames = await dispatcher.handle_frame(  # type: ignore[attr-defined]
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": str(request_id),
                "method": method,
                "params": params,
            }
        )
    )
    assert len(frames) == 1
    return frames[0]


def _damage_archive_manifest(archive: Path, cause: str) -> None:
    with zipfile.ZipFile(archive, "r") as source:
        members = [(info, source.read(info)) for info in source.infolist()]
    manifest = json.loads(members[0][1])
    if cause == "incompatible_backup":
        manifest["version"] = {"major": 2, "minor": 0}
    elif cause == "integrity_failed":
        manifest["entries"][0]["sha256"] = "0" * 64
    elif cause == "limit_exceeded":
        manifest["totals"]["uncompressed_bytes"] = 8 * 1024 * 1024 * 1024 + 1
    elif cause == "single_entry_limit":
        previous_size = manifest["entries"][0]["size"]
        oversized = 2 * 1024 * 1024 * 1024 + 1
        manifest["entries"][0]["size"] = oversized
        manifest["totals"]["uncompressed_bytes"] += oversized - previous_size
    else:  # pragma: no cover - table-owned helper
        raise AssertionError(f"unsupported archive damage: {cause}")
    members[0] = (members[0][0], canonical_json(manifest))
    replacement = archive.with_suffix(".damaged.zip")
    with zipfile.ZipFile(replacement, "w") as target:
        for info, data in members:
            target.writestr(info, data)
    replacement.replace(archive)


def _config(root: Path) -> RuntimeConfig:
    storage_root = initialize_runtime_storage(root, "g0")
    return RuntimeConfig(
        model=ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
            context_capacity=100_000,
        ),
        storage=StorageConfig(
            authority=DesktopStorageAuthorityFactory(root),
            checkpoint_backend="sqlite",
            root=storage_root,
        ),
    )


def _host(root: Path) -> LoopPlaneHost:
    return LoopPlaneHost(_config(root), working_scope=root)


async def _source_archive(
    root: Path, host: LoopPlaneHost, state: ProfileState
) -> tuple[Path, str]:
    async def sink(_event: object) -> None:
        return None

    # A normal durable turn ensures this is a real Host-owned SQLite snapshot,
    # not an invalid empty-store fixture.
    outcome = await host.run("restore source", sink, principal_id=state.principal_id)
    host.enable_desktop_portable_snapshot()
    destination = root / "selected-source.zip"
    result = await BackupMethods(host, state, ProfileMutationLease()).create(
        {
            "mutation_id": "backup-source",
            "acknowledgement": True,
            "destination_path": str(destination),
        }
    )
    assert result["finalized"] is True
    return destination, outcome.session_id


async def _initialized_dispatcher(
    root: Path,
) -> tuple[
    object,
    LoopPlaneHost,
    ProfileState,
    ProfileMutationLease,
    Path,
    str,
    str,
]:
    from bridge import build_rpc_dispatcher

    source_state = ProfileState.open(root / "source-profile")
    source_host = _host(source_state.root)
    archive, source_session_id = await _source_archive(root, source_host, source_state)

    destination_root = root / "destination"
    state = ProfileState.open(root / "destination-profile")
    config = _config(state.root)
    host = LoopPlaneHost(config, working_scope=destination_root)

    async def sink(_event: object) -> None:
        return None

    old_outcome = await host.run(
        "old destination", sink, principal_id=state.principal_id
    )
    lease = ProfileMutationLease()
    dispatcher = build_rpc_dispatcher(
        host,
        working_scope=root,
        profile_state=state,
        mutation_lease=lease,
        principal_id=state.principal_id,
        runtime_config=config,
    )
    initialized = await _rpc(
        dispatcher,
        1,
        "initialize",
        {
            "protocol": {
                "name": PROTOCOL_NAME,
                "major": PROTOCOL_MAJOR,
                "minor": PROTOCOL_MINOR,
            },
            "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
            "client": {"name": "restore-test", "version": "0"},
            "requested_capabilities": [],
        },
    )
    assert "result" in initialized
    return (
        dispatcher,
        host,
        state,
        lease,
        archive,
        source_session_id,
        old_outcome.session_id,
    )


async def test_restore_reservation_blocks_every_rpc_writer_and_shutdown_cleans(
    tmp_path: Path,
) -> None:
    """The public sidecar dispatch path owns reservation through connection teardown."""

    (
        dispatcher,
        _host_instance,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    token = validated["result"]["restore_token"]
    staging = state.root / "staging" / "restore" / token
    assert staging.is_dir()
    assert lease.held_by("restore", "restore-owner")

    competing = (
        ("session.rename", {"mutation_id": "s1", "session_id": "s", "title": "x"}),
        (
            "session.setStarred",
            {"mutation_id": "s2", "session_id": "s", "starred": True},
        ),
        (
            "session.fork",
            {"mutation_id": "s3", "session_id": "s", "confirmation": True},
        ),
        (
            "session.delete",
            {"mutation_id": "s4", "session_id": "s", "confirmation": True},
        ),
        ("session.createInteractive", {"mutation_id": "i-open"}),
        (
            "interaction.submit",
            {"mutation_id": "i-submit", "subscription_id": "sub", "prompt": "p"},
        ),
        (
            "interaction.answerApproval",
            {
                "mutation_id": "i-approval",
                "subscription_id": "sub",
                "request_id": "r",
                "allow": True,
            },
        ),
        (
            "interaction.answerQuestion",
            {
                "mutation_id": "i-question",
                "subscription_id": "sub",
                "request_id": "r",
                "answers": ["a"],
            },
        ),
        ("project.create", {"mutation_id": "p", "label": "Project"}),
        ("workspace.revalidate", {"mutation_id": "w", "workspace_id": "workspace"}),
        (
            "capabilities.invokeAction",
            {"mutation_id": "c", "capability_id": "memory", "action": "refresh"},
        ),
        (
            "backup.create",
            {
                "mutation_id": "b",
                "acknowledgement": True,
                "destination_path": str(tmp_path / "busy.zip"),
            },
        ),
        ("restore.validate", {"mutation_id": "r2", "source_path": str(archive)}),
    )
    for request_id, (method, params) in enumerate(competing, start=3):
        response = await _rpc(dispatcher, request_id, method, params)
        assert response["error"]["data"]["category"] == "busy"

    shutdown = await _rpc(dispatcher, 99, "system.shutdown", {})
    assert shutdown["result"] == {"ok": True}
    assert lease.held() is False
    assert staging.exists() is False


@pytest.mark.parametrize(
    ("method", "params"),
    [
        (
            "backup.create",
            {
                "mutation_id": "backup-request",
                "acknowledgement": True,
                "destination_path": "unused.zip",
            },
        ),
        (
            "restore.validate",
            {"mutation_id": "restore-request", "source_path": "unused.zip"},
        ),
    ],
)
async def test_backup_restore_busy_uses_the_exact_public_error_row(
    tmp_path: Path,
    method: str,
    params: dict[str, object],
) -> None:
    """Backup/restore producers emit the contract row, not a generic busy row."""

    (
        dispatcher,
        _host_instance,
        _state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )

    response = await _rpc(dispatcher, 3, method, params)

    assert response["error"] == {
        "code": -32004,
        "message": "Busy",
        "data": {
            "category": "busy",
            "retryable": True,
            "messageKey": "backup.error.profile_busy",
            "recovery": "wait",
        },
    }


@pytest.mark.parametrize(
    ("cause", "expected_error"),
    [
        (
            "unsafe_archive",
            {
                "code": -32007,
                "message": "Unsafe input",
                "data": {
                    "category": "unsafe_input",
                    "retryable": False,
                    "messageKey": "backup.error.unsafe_archive",
                },
            },
        ),
        (
            "incompatible_backup",
            {
                "code": -32001,
                "message": "Incompatible backup",
                "data": {
                    "category": "incompatible_protocol",
                    "retryable": False,
                    "messageKey": "backup.error.incompatible",
                    "recovery": "contact_support",
                },
            },
        ),
        (
            "integrity_failed",
            {
                "code": -32007,
                "message": "Unsafe input",
                "data": {
                    "category": "unsafe_input",
                    "retryable": False,
                    "messageKey": "backup.error.integrity_failed",
                },
            },
        ),
        (
            "limit_exceeded",
            {
                "code": -32007,
                "message": "Unsafe input",
                "data": {
                    "category": "unsafe_input",
                    "retryable": False,
                    "messageKey": "backup.error.limit_exceeded",
                },
            },
        ),
        (
            "single_entry_limit",
            {
                "code": -32007,
                "message": "Unsafe input",
                "data": {
                    "category": "unsafe_input",
                    "retryable": False,
                    "messageKey": "backup.error.limit_exceeded",
                },
            },
        ),
    ],
)
async def test_restore_validation_emits_exact_archive_error_rows(
    tmp_path: Path,
    cause: str,
    expected_error: dict[str, object],
) -> None:
    """Archive internals select only their fixed public RPC row."""

    (
        dispatcher,
        _host_instance,
        _state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    if cause == "unsafe_archive":
        archive.write_bytes(b"not-a-backup")
    else:
        _damage_archive_manifest(archive, cause)

    response = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": f"restore-{cause}", "source_path": str(archive)},
    )

    assert response["error"] == expected_error
    assert lease.held() is False


async def test_restore_validation_unknown_cause_uses_the_sole_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        dispatcher,
        host,
        _state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)

    def fail_validation(_staging: Path) -> object:
        raise RuntimeError("test-only unknown validation failure")

    monkeypatch.setattr(host, "validate_portable_snapshot", fail_validation)
    response = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-unknown", "source_path": str(archive)},
    )

    assert response["error"] == _INTERNAL_FALLBACK_ERROR
    assert lease.held() is False


@pytest.mark.parametrize("exception_kind", ["archive", "value"])
async def test_unknown_restore_validation_reason_uses_the_sole_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_kind: str,
) -> None:
    from archive import ArchiveValidationError
    from restore import RestoreManager

    (
        dispatcher,
        _host_instance,
        _state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)

    def fail_validation(
        _manager: RestoreManager,
        _source: Path,
    ) -> object:
        if exception_kind == "archive":
            raise ArchiveValidationError("novel_archive_cause")
        raise ValueError("unexpected_internal_bug")

    monkeypatch.setattr(RestoreManager, "validate_archive", fail_validation)
    response = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": f"restore-{exception_kind}", "source_path": str(archive)},
    )

    assert response["error"] == _INTERNAL_FALLBACK_ERROR
    assert lease.held() is False


@pytest.mark.parametrize("transition", ["restore.commit", "restore.cancel"])
async def test_restore_token_authorizes_a_distinct_transition_mutation(
    tmp_path: Path,
    transition: str,
) -> None:
    """Each RPC owns its mutation ID while the opaque token owns the reservation."""

    (
        dispatcher,
        _host_instance,
        _state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-validate", "source_path": str(archive)},
    )
    token = validated["result"]["restore_token"]
    params = {"mutation_id": f"{transition}-request", "restore_token": token}
    if transition == "restore.commit":
        params["confirmation"] = True

    response = await _rpc(dispatcher, 3, transition, params)

    assert "error" not in response
    if transition == "restore.commit":
        assert response["result"]["committed"] is True
    else:
        assert response["result"]["cancelled"] is True
    assert lease.held() is False


async def test_unknown_post_pointer_failure_rolls_back_before_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        dispatcher,
        old_host,
        state,
        lease,
        archive,
        source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_list = LoopPlaneHost.list_sessions

    def fail_candidate_read(target: LoopPlaneHost) -> object:
        if target is not old_host:
            raise KeyError("test-only unknown candidate failure")
        return original_list(target)

    monkeypatch.setattr(LoopPlaneHost, "list_sessions", fail_candidate_read)
    before = {
        name: (
            (state.root / name).read_bytes() if (state.root / name).exists() else None
        )
        for name in ("active-generation.json", "active-generation-proof.json")
    }
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-validate", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-commit",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert response["error"] == _INTERNAL_FALLBACK_ERROR
    assert {
        name: (
            (state.root / name).read_bytes() if (state.root / name).exists() else None
        )
        for name in ("active-generation.json", "active-generation-proof.json")
    } == before
    assert (state.root / "restore-journal-a.json").exists() is False
    assert (state.root / "restore-journal-b.json").exists() is False
    assert lease.held() is False
    listed = await _rpc(dispatcher, 4, "session.list", {})
    session_ids = {item["session_id"] for item in listed["result"]["sessions"]}
    assert old_session_id in session_ids
    assert source_session_id not in session_ids


async def test_restore_commit_identity_race_releases_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import restore as restore_module

    (
        dispatcher,
        _host_instance,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-validate", "source_path": str(archive)},
    )
    token = validated["result"]["restore_token"]
    staging = state.root / "staging" / "restore" / token
    original_identity = restore_module._archive_identity
    calls = {"count": 0}

    def fail_final_identity(path: Path) -> str:
        calls["count"] += 1
        if calls["count"] == 2:
            raise FileNotFoundError("test-only final identity race")
        return original_identity(path)

    monkeypatch.setattr(restore_module, "_archive_identity", fail_final_identity)
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-commit",
            "restore_token": token,
            "confirmation": True,
        },
    )

    assert response["error"] == _INTEGRITY_FAILED_ERROR
    assert lease.held() is False
    assert staging.exists() is False


async def test_restore_identity_race_releases_authority_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import restore as restore_module

    (
        dispatcher,
        _host_instance,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-validate", "source_path": str(archive)},
    )
    token = validated["result"]["restore_token"]
    original_identity = restore_module._archive_identity
    original_remove = restore_module._remove_tree
    calls = {"count": 0}

    def fail_final_identity(path: Path) -> str:
        calls["count"] += 1
        if calls["count"] == 2:
            raise FileNotFoundError("test-only final identity race")
        return original_identity(path)

    def fail_staging_cleanup(path: Path) -> None:
        if path.name == token:
            raise OSError("test-only staging cleanup failure")
        original_remove(path)

    monkeypatch.setattr(restore_module, "_archive_identity", fail_final_identity)
    monkeypatch.setattr(restore_module, "_remove_tree", fail_staging_cleanup)
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-commit",
            "restore_token": token,
            "confirmation": True,
        },
    )

    assert response["error"] == _INTEGRITY_FAILED_ERROR
    assert lease.held() is False
    second = await _rpc(
        dispatcher,
        4,
        "restore.validate",
        {"mutation_id": "restore-next", "source_path": str(archive)},
    )
    assert "result" in second
    assert second["result"]["restore_token"] != token


async def test_restore_commit_unknown_cause_uses_fallback_and_releases_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import methods.backup as backup_methods_module

    (
        dispatcher,
        _host_instance,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-validate", "source_path": str(archive)},
    )
    token = validated["result"]["restore_token"]
    staging = state.root / "staging" / "restore" / token

    async def fail_commit(*_args: object, **_kwargs: object) -> object:
        raise KeyError("test-only unknown commit failure")

    monkeypatch.setattr(backup_methods_module, "commit_restore", fail_commit)
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-commit",
            "restore_token": token,
            "confirmation": True,
        },
    )

    assert response["error"] == _INTERNAL_FALLBACK_ERROR
    assert lease.held() is False
    assert staging.exists() is False


async def test_restore_commit_handover_uses_candidate_host_and_publishes_proof(
    tmp_path: Path,
) -> None:
    """T078 only: proof follows candidate readiness/owner swap, never precedes it."""

    import gc
    import weakref

    (
        dispatcher,
        old_host,
        state,
        _lease,
        archive,
        source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    previous_host = weakref.ref(old_host)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )

    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert committed["result"]["committed"] is True
    proof = state.root / "active-generation-proof.json"
    pointer = state.root / "active-generation.json"
    assert pointer.is_file()
    assert proof.is_file()
    proof_value = json.loads(proof.read_text("utf-8"))
    receipt = proof_value["generation_publication_receipt"]
    assert receipt["checkpoint_state"] == "initialized"
    assert receipt["artifact_state"] == "absent_uninitialized"

    listed = await _rpc(dispatcher, 4, "session.list", {})
    session_ids = {session["session_id"] for session in listed["result"]["sessions"]}
    assert source_session_id in session_ids
    assert old_session_id not in session_ids

    del old_host
    gc.collect()
    assert previous_host() is None


async def test_runtime_owner_tracks_handover_and_releases_closed_host_graphs(
    tmp_path: Path,
) -> None:
    """The process owner follows current Host replacement and teardown release."""

    import gc
    import weakref

    from bridge import (
        bootstrap_desktop_owner,
        build_rpc_dispatcher,
        desktop_runtime_config,
    )

    source_state = ProfileState.open(tmp_path / "source-profile")
    source_host = _host(source_state.root)
    archive, source_session_id = await _source_archive(
        tmp_path,
        source_host,
        source_state,
    )
    owner = bootstrap_desktop_owner(tmp_path / "destination-profile")
    config = desktop_runtime_config(
        model=ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="old")])],
            context_capacity=100_000,
        ),
        profile_root=owner.profile_root,
        generation_id=owner.generation_id,
    )
    old_host = owner.attach_host(config)
    state = owner.ensure_profile_state()

    async def sink(_event: object) -> None:
        return None

    old_outcome = await old_host.run(
        "old destination",
        sink,
        principal_id=state.principal_id,
    )
    old_host_ref = weakref.ref(old_host)
    dispatcher = build_rpc_dispatcher(
        old_host,
        working_scope=owner.profile_root,
        profile_state=state,
        mutation_lease=owner.mutation_lease,
        principal_id=state.principal_id,
        runtime_config=config,
        runtime_owner=owner,
    )
    await _rpc(
        dispatcher,
        1,
        "initialize",
        {
            "protocol": {
                "name": PROTOCOL_NAME,
                "major": PROTOCOL_MAJOR,
                "minor": PROTOCOL_MINOR,
            },
            "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
            "client": {"name": "restore-test", "version": "0"},
            "requested_capabilities": [],
        },
    )
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    assert owner.host is not None
    assert owner.host is not old_host
    assert {session.session_id for session in owner.host.list_sessions()} == {
        source_session_id
    }
    assert old_outcome.session_id != source_session_id

    del old_host
    gc.collect()
    assert old_host_ref() is None

    current_host_ref = weakref.ref(owner.host)
    await dispatcher.aclose()  # type: ignore[attr-defined]
    assert owner.host is None
    gc.collect()
    assert current_host_ref() is None
    owner.release()
    await source_host.aclose()


async def test_second_restore_preproof_rollback_rebuilds_current_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback after a prior commit must reopen that committed generation, not g0."""

    import durability

    (
        dispatcher,
        _old_host,
        _state,
        _lease,
        archive,
        source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    first_validation = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-first", "source_path": str(archive)},
    )
    first_commit = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-first",
            "restore_token": first_validation["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert first_commit["result"]["committed"] is True

    original_replace = durability._durable_replace
    proof_failed = {"value": False}

    def fail_second_proof(path: Path, payload: bytes) -> None:
        if path.name == "active-generation-proof.json" and not proof_failed["value"]:
            proof_failed["value"] = True
            raise OSError("second proof write failed")
        original_replace(path, payload)

    monkeypatch.setattr(durability, "_durable_replace", fail_second_proof)
    second_validation = await _rpc(
        dispatcher,
        4,
        "restore.validate",
        {"mutation_id": "restore-second", "source_path": str(archive)},
    )
    second_commit = await _rpc(
        dispatcher,
        5,
        "restore.commit",
        {
            "mutation_id": "restore-second",
            "restore_token": second_validation["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert second_commit["error"] == _ROLLED_BACK_ERROR
    listed = await _rpc(dispatcher, 6, "session.list", {})
    session_ids = {session["session_id"] for session in listed["result"]["sessions"]}
    assert source_session_id in session_ids
    assert old_session_id not in session_ids


async def test_committed_restore_bootstraps_serving_candidate_storage_after_restart(
    tmp_path: Path,
) -> None:
    """A matching proof must reopen the exact restored storage on process restart."""

    from bridge import bootstrap_desktop_owner, desktop_runtime_config

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    shutdown = await _rpc(dispatcher, 4, "system.shutdown", {})
    assert shutdown["result"] == {"ok": True}

    owner = bootstrap_desktop_owner(state.root)
    restarted: LoopPlaneHost | None = None
    try:
        assert owner.generation_id == generation_id
        config = desktop_runtime_config(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="restarted")])],
                context_capacity=100_000,
            ),
            profile_root=state.root,
            generation_id=owner.generation_id,
        )
        restarted = owner.attach_host(config)
        session_ids = {item.session_id for item in restarted.list_sessions()}
        assert source_session_id in session_ids
        assert old_session_id not in session_ids
    finally:
        if restarted is not None:
            await owner.close_host()
        owner.release()


async def test_restored_profile_mutation_remains_startable(
    tmp_path: Path,
) -> None:
    """Normal Project/preference persistence cannot invalidate restore authority."""

    from bridge import bootstrap_desktop_owner

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    restored = ProfileState.open(state.root, generation_id=generation_id)
    restored.set_preference("theme", "dark")
    workspace_path = tmp_path / "relinked-workspace"
    workspace_path.mkdir()
    workspaces = WorkspaceStore(restored)
    workspace = workspaces.bind(workspace_path, label="Restored workspace")
    workspaces.mark_relink_required(workspace["id"])
    workspaces.relink(workspace["id"], workspace_path)

    owner = bootstrap_desktop_owner(state.root)
    try:
        assert owner.generation_id == generation_id
    finally:
        owner.release()


async def test_restored_desktop_interaction_uses_active_profile_principal(
    tmp_path: Path,
) -> None:
    """The path-free Desktop RPC creates sessions owned by the active profile."""

    from bridge import bootstrap_desktop_owner, build_rpc_dispatcher

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    try:
        config = RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="new")])],
                context_capacity=100_000,
            ),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                authority=DesktopStorageAuthorityFactory(state.root),
                root=state.root / "generation-storage" / generation_id,
            ),
        )
        active = owner.attach_host(config)
        restored = ProfileState.open(state.root, generation_id=generation_id)
        desktop = build_rpc_dispatcher(
            active,
            profile_state=restored,
            principal_id=restored.principal_id,
            runtime_config=config,
            runtime_owner=owner,
        )
        initialized = await _rpc(
            desktop,
            5,
            "initialize",
            {
                "protocol": {
                    "name": PROTOCOL_NAME,
                    "major": PROTOCOL_MAJOR,
                    "minor": PROTOCOL_MINOR,
                },
                "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
                "client": {"name": "restore-test", "version": "0"},
                "requested_capabilities": [],
            },
        )
        assert "result" in initialized, initialized
        opened = await _rpc(
            desktop,
            6,
            "session.createInteractive",
            {"mutation_id": "desktop-open", "pane_id": "pane-1"},
        )
        assert "result" in opened, opened
        submitted = await _rpc(
            desktop,
            7,
            "interaction.submit",
            {
                "mutation_id": "desktop-submit",
                "subscription_id": opened["result"]["subscription_id"],
                "prompt": "new restored session",
            },
        )
        assert submitted["result"]["accepted"] is True
        await _rpc(desktop, 8, "system.shutdown", {})
        active = None
    finally:
        if active is not None:
            await owner.close_host()
        owner.release()

    restarted = bootstrap_desktop_owner(state.root)
    try:
        assert restarted.generation_id == generation_id
    finally:
        restarted.release()


async def test_restored_project_session_delete_remains_startable(
    tmp_path: Path,
) -> None:
    """Desktop deletion removes Project membership before durable session authority."""

    from bridge import bootstrap_desktop_owner, build_rpc_dispatcher

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    try:
        config = RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="new")])],
                context_capacity=100_000,
            ),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                authority=DesktopStorageAuthorityFactory(state.root),
                root=state.root / "generation-storage" / generation_id,
            ),
        )
        active = owner.attach_host(config)
        restored = ProfileState.open(state.root, generation_id=generation_id)
        desktop = build_rpc_dispatcher(
            active,
            profile_state=restored,
            principal_id=restored.principal_id,
            runtime_config=config,
            runtime_owner=owner,
        )
        await _rpc(
            desktop,
            5,
            "initialize",
            {
                "protocol": {
                    "name": PROTOCOL_NAME,
                    "major": PROTOCOL_MAJOR,
                    "minor": PROTOCOL_MINOR,
                },
                "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
                "client": {"name": "restore-test", "version": "0"},
                "requested_capabilities": [],
            },
        )
        opened = await _rpc(
            desktop,
            6,
            "session.createInteractive",
            {"mutation_id": "desktop-open", "pane_id": "pane-1"},
        )
        submitted = await _rpc(
            desktop,
            7,
            "interaction.submit",
            {
                "mutation_id": "desktop-submit",
                "subscription_id": opened["result"]["subscription_id"],
                "prompt": "new restored session",
            },
        )
        session_id = submitted["result"]["session_id"]
        created = await _rpc(
            desktop,
            8,
            "project.create",
            {"mutation_id": "project-create", "label": "Restored project"},
        )
        project_id = created["result"]["project"]["id"]
        assigned = await _rpc(
            desktop,
            9,
            "project.assignSession",
            {
                "mutation_id": "project-assign",
                "project_id": project_id,
                "session_id": session_id,
            },
        )
        assert assigned["result"]["project"]["session_ids"] == [session_id]
        deleted = await _rpc(
            desktop,
            10,
            "session.delete",
            {
                "mutation_id": "session-delete",
                "session_id": session_id,
                "confirmation": True,
            },
        )
        assert deleted["result"]["deleted"] is True
        await _rpc(desktop, 11, "system.shutdown", {})
        active = None
    finally:
        if active is not None:
            await owner.close_host()
        owner.release()

    restarted = bootstrap_desktop_owner(state.root)
    try:
        assert restarted.generation_id == generation_id
    finally:
        restarted.release()


async def test_post_effect_session_delete_error_keeps_authority_consistent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A delete applied before an error remains committed across all authorities."""

    from bridge import bootstrap_desktop_owner, build_rpc_dispatcher

    from loopplane.checkpoint.sqlite import SqliteCheckpointStore

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    session_id = ""
    try:
        config = RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                authority=DesktopStorageAuthorityFactory(state.root),
                root=state.root / "generation-storage" / generation_id,
                artifact_threshold_bytes=1_000_000,
                replacement_budget_bytes=1,
            ),
        )
        active = owner.attach_host(config)
        restored = ProfileState.open(state.root, generation_id=generation_id)
        desktop = build_rpc_dispatcher(
            active,
            profile_state=restored,
            principal_id=restored.principal_id,
            runtime_config=config,
            runtime_owner=owner,
        )
        await _rpc(
            desktop,
            5,
            "initialize",
            {
                "protocol": {
                    "name": PROTOCOL_NAME,
                    "major": PROTOCOL_MAJOR,
                    "minor": PROTOCOL_MINOR,
                },
                "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
                "client": {"name": "restore-test", "version": "0"},
                "requested_capabilities": [],
            },
        )
        opened = await _rpc(
            desktop,
            6,
            "session.createInteractive",
            {"mutation_id": "desktop-open", "pane_id": "pane-1"},
        )
        submitted = await _rpc(
            desktop,
            7,
            "interaction.submit",
            {
                "mutation_id": "desktop-submit",
                "subscription_id": opened["result"]["subscription_id"],
                "prompt": "create restored artifact",
            },
        )
        session_id = submitted["result"]["session_id"]
        artifact_session = (
            state.root / "generation-storage" / generation_id / session_id
        )
        assert any(artifact_session.joinpath("artifacts").glob("*.txt"))
        created = await _rpc(
            desktop,
            8,
            "project.create",
            {"mutation_id": "project-create", "label": "Restored project"},
        )
        project_id = created["result"]["project"]["id"]
        await _rpc(
            desktop,
            9,
            "project.assignSession",
            {
                "mutation_id": "project-assign",
                "project_id": project_id,
                "session_id": session_id,
            },
        )
        original_delete = SqliteCheckpointStore.delete_session

        def delete_then_fail(store: SqliteCheckpointStore, target: str) -> None:
            original_delete(store, target)
            raise OSError("delete acknowledgement lost")

        monkeypatch.setattr(
            SqliteCheckpointStore,
            "delete_session",
            delete_then_fail,
        )
        deleted = await _rpc(
            desktop,
            10,
            "session.delete",
            {
                "mutation_id": "session-delete",
                "session_id": session_id,
                "confirmation": True,
            },
        )
        assert deleted["result"]["deleted"] is True
        assert artifact_session.exists() is False
        await _rpc(desktop, 11, "system.shutdown", {})
        active = None
    finally:
        if active is not None:
            await owner.close_host()
        owner.release()

    restarted = bootstrap_desktop_owner(state.root)
    reopened: LoopPlaneHost | None = None
    try:
        reopened = restarted.attach_host(
            RuntimeConfig(
                model=ScriptedModel(script=[], context_capacity=100_000),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                ),
            )
        )
        assert session_id not in {
            session.session_id for session in reopened.list_sessions()
        }
    finally:
        if reopened is not None:
            await restarted.close_host()
        restarted.release()


async def test_artifact_rollback_failure_does_not_restore_project_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed artifact rollback never recreates a dangling Project reference."""

    from bridge import bootstrap_desktop_owner, build_rpc_dispatcher

    from loopplane.checkpoint.sqlite import SqliteCheckpointStore

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    try:
        config = RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                authority=DesktopStorageAuthorityFactory(state.root),
                root=state.root / "generation-storage" / generation_id,
                artifact_threshold_bytes=1_000_000,
                replacement_budget_bytes=1,
            ),
        )
        active = owner.attach_host(config)
        restored = ProfileState.open(state.root, generation_id=generation_id)
        desktop = build_rpc_dispatcher(
            active,
            profile_state=restored,
            principal_id=restored.principal_id,
            runtime_config=config,
            runtime_owner=owner,
        )
        await _rpc(
            desktop,
            5,
            "initialize",
            {
                "protocol": {
                    "name": PROTOCOL_NAME,
                    "major": PROTOCOL_MAJOR,
                    "minor": PROTOCOL_MINOR,
                },
                "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
                "client": {"name": "restore-test", "version": "0"},
                "requested_capabilities": [],
            },
        )
        opened = await _rpc(
            desktop,
            6,
            "session.createInteractive",
            {"mutation_id": "desktop-open", "pane_id": "pane-1"},
        )
        submitted = await _rpc(
            desktop,
            7,
            "interaction.submit",
            {
                "mutation_id": "desktop-submit",
                "subscription_id": opened["result"]["subscription_id"],
                "prompt": "create restored artifact",
            },
        )
        session_id = submitted["result"]["session_id"]
        artifact_session = (
            state.root / "generation-storage" / generation_id / session_id
        )
        created = await _rpc(
            desktop,
            8,
            "project.create",
            {"mutation_id": "project-create", "label": "Restored project"},
        )
        project_id = created["result"]["project"]["id"]
        await _rpc(
            desktop,
            9,
            "project.assignSession",
            {
                "mutation_id": "project-assign",
                "project_id": project_id,
                "session_id": session_id,
            },
        )

        def fail_before_delete(
            _store: SqliteCheckpointStore,
            _target: str,
        ) -> None:
            artifact_session.mkdir()
            raise OSError("checkpoint delete rejected")

        monkeypatch.setattr(
            SqliteCheckpointStore,
            "delete_session",
            fail_before_delete,
        )
        failed = await _rpc(
            desktop,
            10,
            "session.delete",
            {
                "mutation_id": "session-delete",
                "session_id": session_id,
                "confirmation": True,
            },
        )
        assert failed["error"]["data"]["category"] == "not_found"
        assert ProjectStore(restored).session_project(session_id) is None
        artifact_session.rmdir()
    finally:
        if active is not None:
            await owner.close_host()
        owner.release()


async def test_restored_runtime_project_assignment_remains_startable(
    tmp_path: Path,
) -> None:
    """Active Projects may include sessions created after restore publication."""

    from bridge import bootstrap_desktop_owner

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    first_owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    try:
        active = first_owner.attach_host(
            RuntimeConfig(
                model=ScriptedModel(
                    script=[ScriptedTurn(increments=[TextIncrement(text="new")])],
                    context_capacity=100_000,
                ),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                ),
            )
        )

        async def sink(_event: object) -> None:
            return None

        outcome = await active.run(
            "new restored session",
            sink,
            principal_id=state.principal_id,
        )
        profile = ProfileState.open(state.root, generation_id=generation_id)
        projects = ProjectStore(profile)
        project = projects.create(label="Post-restore project")
        projects.assign_session(project["id"], outcome.session_id)
    finally:
        if active is not None:
            await first_owner.close_host()
        first_owner.release()

    second_owner = bootstrap_desktop_owner(state.root)
    try:
        assert second_owner.generation_id == generation_id
    finally:
        second_owner.release()


async def test_restored_runtime_artifact_mutation_remains_startable(
    tmp_path: Path,
) -> None:
    """Serving artifact state may evolve after immutable restore publication."""

    from bridge import bootstrap_desktop_owner

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    first_owner = bootstrap_desktop_owner(state.root)
    mutated: LoopPlaneHost | None = None
    try:
        mutated = first_owner.attach_host(
            RuntimeConfig(
                model=big_tool_model(),
                tools=(BIG_TOOL,),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                    artifact_threshold_bytes=1_000_000,
                    replacement_budget_bytes=1,
                ),
            )
        )

        async def sink(_event: object) -> None:
            return None

        outcome = await mutated.run(
            "create restored artifact",
            sink,
            principal_id=state.principal_id,
        )
        artifact_session = (
            state.root / "generation-storage" / generation_id / outcome.session_id
        )
        assert any(artifact_session.joinpath("artifacts").glob("*.txt"))
        deleted = mutated.bulk_delete_sessions(
            [outcome.session_id], principal_id=state.principal_id
        )
        assert deleted == [outcome.session_id]
        assert artifact_session.exists() is False
    finally:
        if mutated is not None:
            await first_owner.close_host()
        first_owner.release()

    second_owner = bootstrap_desktop_owner(state.root)
    try:
        assert second_owner.generation_id == generation_id
    finally:
        second_owner.release()


async def test_unsafe_artifact_delete_preserves_checkpoint_authority(
    tmp_path: Path,
) -> None:
    """Artifact layout rejection must occur before session checkpoint deletion."""

    from bridge import bootstrap_desktop_owner

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    first_owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    outcome = None
    try:
        active = first_owner.attach_host(
            RuntimeConfig(
                model=big_tool_model(),
                tools=(BIG_TOOL,),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                    artifact_threshold_bytes=1_000_000,
                    replacement_budget_bytes=1,
                ),
            )
        )

        async def sink(_event: object) -> None:
            return None

        outcome = await active.run(
            "create guarded artifact",
            sink,
            principal_id=state.principal_id,
        )
        artifact_session = (
            state.root / "generation-storage" / generation_id / outcome.session_id
        )
        unexpected = artifact_session / "unexpected"
        unexpected.write_text("not store-owned", encoding="utf-8")
        with pytest.raises(RuntimeError):
            active.bulk_delete_sessions(
                [outcome.session_id], principal_id=state.principal_id
            )
        unexpected.unlink()
    finally:
        if active is not None:
            await first_owner.close_host()
        first_owner.release()

    assert outcome is not None
    second_owner = bootstrap_desktop_owner(state.root)
    reopened: LoopPlaneHost | None = None
    try:
        reopened = second_owner.attach_host(
            RuntimeConfig(
                model=ScriptedModel(script=[], context_capacity=100_000),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                ),
            )
        )
        assert outcome.session_id in {
            session.session_id for session in reopened.list_sessions()
        }
    finally:
        if reopened is not None:
            await second_owner.close_host()
        second_owner.release()


async def test_artifact_tree_is_detached_before_checkpoint_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checkpoint deletion starts only after the owned artifact tree is detached."""

    from bridge import bootstrap_desktop_owner

    from loopplane.checkpoint.sqlite import SqliteCheckpointStore

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    generation_id = state.generation_id
    await _rpc(dispatcher, 4, "system.shutdown", {})

    owner = bootstrap_desktop_owner(state.root)
    active: LoopPlaneHost | None = None
    outcome = None
    try:
        active = owner.attach_host(
            RuntimeConfig(
                model=big_tool_model(),
                tools=(BIG_TOOL,),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                    artifact_threshold_bytes=1_000_000,
                    replacement_budget_bytes=1,
                ),
            )
        )

        async def sink(_event: object) -> None:
            return None

        outcome = await active.run(
            "create guarded artifact",
            sink,
            principal_id=state.principal_id,
        )
        artifact_session = (
            state.root / "generation-storage" / generation_id / outcome.session_id
        )
        original_delete = SqliteCheckpointStore.delete_session
        observed = {"called": False}

        def assert_detached_before_delete(
            store: SqliteCheckpointStore, session_id: str
        ) -> None:
            observed["called"] = True
            assert artifact_session.exists() is False
            original_delete(store, session_id)

        monkeypatch.setattr(
            SqliteCheckpointStore,
            "delete_session",
            assert_detached_before_delete,
        )
        deleted = active.bulk_delete_sessions(
            [outcome.session_id], principal_id=state.principal_id
        )
        assert deleted == [outcome.session_id]
        assert observed["called"] is True
    finally:
        if active is not None:
            await owner.close_host()
        owner.release()

    assert outcome is not None
    restarted = bootstrap_desktop_owner(state.root)
    reopened: LoopPlaneHost | None = None
    try:
        reopened = restarted.attach_host(
            RuntimeConfig(
                model=ScriptedModel(script=[], context_capacity=100_000),
                storage=StorageConfig(
                    checkpoint_backend="sqlite",
                    authority=DesktopStorageAuthorityFactory(state.root),
                    root=state.root / "generation-storage" / generation_id,
                ),
            )
        )
        assert outcome.session_id not in {
            session.session_id for session in reopened.list_sessions()
        }
    finally:
        if reopened is not None:
            await restarted.close_host()
        restarted.release()


async def test_startup_fail_locks_when_committed_restore_authority_is_missing(
    tmp_path: Path,
) -> None:
    """Retained restore generations never authorize fallback to current-generation."""

    from bridge import bootstrap_desktop_owner
    from runtime import RestoreJournalsPresent

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    await _rpc(dispatcher, 4, "system.shutdown", {})

    (state.root / "active-generation.json").unlink()
    (state.root / "active-generation-proof.json").unlink()

    with pytest.raises(RestoreJournalsPresent):
        bootstrap_desktop_owner(state.root)


async def test_startup_rejects_profile_principal_mismatched_to_restored_storage(
    tmp_path: Path,
) -> None:
    """A valid proof cannot authorize a profile/checkpoint principal split."""

    from bridge import bootstrap_desktop_owner
    from runtime import RestoreJournalsPresent

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    await _rpc(dispatcher, 4, "system.shutdown", {})

    profile_path = (
        state.root / "generations" / state.generation_id / "profile" / "profile.json"
    )
    profile_value = json.loads(profile_path.read_text("utf-8"))
    profile_value["principal_id"] = "foreign-principal"
    profile_path.write_text(
        json.dumps(profile_value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(RestoreJournalsPresent):
        bootstrap_desktop_owner(state.root)


async def test_restore_commit_rejects_changed_archive_before_candidate_handover(
    tmp_path: Path,
) -> None:
    """The public RPC owner rechecks archive content before it can quiesce a Host."""

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    recovery_paths = (
        state.root / "active-generation.json",
        state.root / "active-generation-proof.json",
    )
    before = {
        path.name: path.read_bytes() if path.exists() else None
        for path in recovery_paths
    }
    archive.write_bytes(b"replaced-after-validation")

    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert "error" in response
    assert {
        path.name: path.read_bytes() if path.exists() else None
        for path in recovery_paths
    } == before


async def test_old_host_close_failure_rolls_back_before_proof_and_reopens_previous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A close failure is pre-proof and must restore one usable previous Host."""

    (
        dispatcher,
        old_host,
        _state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_close = old_host.aclose
    close_calls = {"count": 0}

    async def fail_once() -> None:
        close_calls["count"] += 1
        if close_calls["count"] == 1:
            raise KeyError("old Host close failed")
        await original_close()

    monkeypatch.setattr(old_host, "aclose", fail_once)
    first_validation = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-one", "source_path": str(archive)},
    )
    first_commit = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-one",
            "restore_token": first_validation["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert first_commit["error"] == _INTERNAL_FALLBACK_ERROR
    assert close_calls["count"] == 2

    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert "result" in listed
    second_validation = await _rpc(
        dispatcher,
        5,
        "restore.validate",
        {"mutation_id": "restore-two", "source_path": str(archive)},
    )
    assert "result" in second_validation
    cancelled = await _rpc(
        dispatcher,
        6,
        "restore.cancel",
        {
            "mutation_id": "restore-two-cancel",
            "restore_token": second_validation["result"]["restore_token"],
        },
    )
    assert cancelled["result"]["cancelled"] is True

    shutdown = await _rpc(dispatcher, 7, "system.shutdown", {})
    assert shutdown["result"] == {"ok": True}


async def test_shutdown_closes_candidate_when_previous_host_close_keeps_failing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown attempts every retained Host and remains retryable on failure."""

    (
        dispatcher,
        old_host,
        _state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_close = LoopPlaneHost.aclose
    fail_old = {"value": True}
    closed: list[int] = []

    async def observe_close(target: LoopPlaneHost) -> None:
        if target is old_host and fail_old["value"]:
            raise OSError("old Host close still failing")
        closed.append(id(target))
        await original_close(target)

    monkeypatch.setattr(LoopPlaneHost, "aclose", observe_close)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-one", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-one",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["error"] == _PUBLICATION_RESTART_ERROR

    shutdown = await _rpc(dispatcher, 4, "system.shutdown", {})
    assert shutdown["error"]["data"]["category"] == "internal_failure"
    assert id(old_host) not in closed
    assert len(closed) == 1

    fail_old["value"] = False
    await dispatcher.aclose()  # type: ignore[attr-defined]
    assert id(old_host) in closed


async def test_failed_previous_host_readiness_remains_teardown_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rebuilt Host that fails its first read remains owned until close succeeds."""

    import durability

    (
        dispatcher,
        old_host,
        _state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_list = LoopPlaneHost.list_sessions
    original_close = LoopPlaneHost.aclose
    original_replace = durability._durable_replace
    non_old_hosts: list[LoopPlaneHost] = []
    close_attempts = {"count": 0}
    fail_pending_close = {"value": True}

    def fail_rebuilt_read(target: LoopPlaneHost) -> object:
        if target is not old_host and target not in non_old_hosts:
            non_old_hosts.append(target)
        if len(non_old_hosts) >= 2 and target is non_old_hosts[1]:
            raise KeyError("rebuilt previous Host read failed")
        return original_list(target)

    def fail_proof_replace(path: Path, payload: bytes) -> None:
        if path.name == "active-generation-proof.json":
            raise OSError("proof write failed")
        original_replace(path, payload)

    async def fail_rebuilt_close_once(target: LoopPlaneHost) -> None:
        if len(non_old_hosts) >= 2 and target is non_old_hosts[1]:
            close_attempts["count"] += 1
            if fail_pending_close["value"]:
                raise OSError("rebuilt previous Host close failed")
        await original_close(target)

    monkeypatch.setattr(LoopPlaneHost, "list_sessions", fail_rebuilt_read)
    monkeypatch.setattr(LoopPlaneHost, "aclose", fail_rebuilt_close_once)
    monkeypatch.setattr(durability, "_durable_replace", fail_proof_replace)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert committed["error"] == _PUBLICATION_RESTART_ERROR
    assert len(non_old_hosts) == 2
    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert listed["error"] == _INTERNAL_FALLBACK_ERROR

    shutdown = await _rpc(dispatcher, 5, "system.shutdown", {})
    assert shutdown["error"]["data"]["category"] == "internal_failure"
    assert close_attempts["count"] == 1

    fail_pending_close["value"] = False
    await dispatcher.aclose()  # type: ignore[attr-defined]
    assert close_attempts["count"] == 2


async def test_preproof_failure_after_real_handover_restores_runtime_and_disk_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A proof-write failure rolls the public RPC facade back to its old Host."""

    import durability
    from runtime import RuntimeHostHandover

    ready = RuntimeHostHandover.candidate_ready
    close = RuntimeHostHandover.close_previous
    install = RuntimeHostHandover.install_candidate
    rollback = RuntimeHostHandover.rollback_candidate
    callbacks: list[str] = []

    async def observe_ready(self: RuntimeHostHandover, generation: Path) -> None:
        callbacks.append("ready")
        await ready(self, generation)

    async def observe_close(self: RuntimeHostHandover) -> None:
        callbacks.append("close")
        await close(self)

    def observe_install(self: RuntimeHostHandover, generation: Path) -> None:
        callbacks.append("install")
        install(self, generation)

    async def observe_rollback(self: RuntimeHostHandover) -> None:
        callbacks.append("rollback")
        await rollback(self)

    monkeypatch.setattr(RuntimeHostHandover, "candidate_ready", observe_ready)
    monkeypatch.setattr(RuntimeHostHandover, "close_previous", observe_close)
    monkeypatch.setattr(RuntimeHostHandover, "install_candidate", observe_install)
    monkeypatch.setattr(RuntimeHostHandover, "rollback_candidate", observe_rollback)
    (
        dispatcher,
        _old_host,
        state,
        lease,
        archive,
        source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    recovery_paths = (
        state.root / "active-generation.json",
        state.root / "active-generation-proof.json",
    )
    before = {
        path.name: path.read_bytes() if path.exists() else None
        for path in recovery_paths
    }
    original_replace = durability._durable_replace

    def fail_proof_replace(path: Path, payload: bytes) -> None:
        if path.name == "active-generation-proof.json":
            raise OSError("proof write failed")
        original_replace(path, payload)

    monkeypatch.setattr(durability, "_durable_replace", fail_proof_replace)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert "error" in response
    assert callbacks == ["ready", "close", "install", "rollback"]
    assert {
        path.name: path.read_bytes() if path.exists() else None
        for path in recovery_paths
    } == before
    listed = await _rpc(dispatcher, 4, "session.list", {})
    session_ids = {item["session_id"] for item in listed["result"]["sessions"]}
    assert old_session_id in session_ids
    assert source_session_id not in session_ids
    assert lease.held() is False


async def test_durable_rollback_failure_locks_rebuilt_previous_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed exact disk rollback cannot leave the rebuilt Host dispatchable."""

    import durability

    (
        dispatcher,
        _old_host,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_replace = durability._durable_replace

    def fail_proof_replace(path: Path, payload: bytes) -> None:
        if path.name == "active-generation-proof.json":
            raise OSError("proof write failed")
        original_replace(path, payload)

    def fail_previous_restore(_root: Path, _pointer: bytes, _proof: bytes) -> None:
        raise OSError("previous authority restore failed")

    monkeypatch.setattr(durability, "_durable_replace", fail_proof_replace)
    monkeypatch.setattr(durability, "_restore_exact_previous", fail_previous_restore)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert response["error"] == _PUBLICATION_RESTART_ERROR
    assert lease.held() is True
    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert listed["error"] == _INTERNAL_FALLBACK_ERROR


async def test_preproof_rollback_close_failure_locks_dispatch_until_teardown_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A candidate close failure retains authority and blocks further dispatch."""

    import durability

    (
        dispatcher,
        old_host,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_close = LoopPlaneHost.aclose
    original_replace = durability._durable_replace
    candidate: list[LoopPlaneHost] = []
    fail_candidate_close = {"value": True}

    def fail_proof_replace(path: Path, payload: bytes) -> None:
        if path.name == "active-generation-proof.json":
            raise OSError("proof write failed")
        original_replace(path, payload)

    async def fail_discarded_candidate_close(target: LoopPlaneHost) -> None:
        if target is not old_host:
            if target not in candidate:
                candidate.append(target)
            if fail_candidate_close["value"]:
                raise KeyError("discarded candidate close failed")
        await original_close(target)

    monkeypatch.setattr(durability, "_durable_replace", fail_proof_replace)
    monkeypatch.setattr(LoopPlaneHost, "aclose", fail_discarded_candidate_close)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert response["error"] == _PUBLICATION_RESTART_ERROR
    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert listed["error"] == _INTERNAL_FALLBACK_ERROR
    assert lease.held() is True
    storage_parent = state.root / "generation-storage"
    assert candidate and list(storage_parent.iterdir())

    shutdown = await _rpc(dispatcher, 5, "system.shutdown", {})
    assert shutdown["error"]["data"]["category"] == "internal_failure"
    assert list(storage_parent.iterdir())

    fail_candidate_close["value"] = False
    await dispatcher.aclose()  # type: ignore[attr-defined]
    assert {entry.name for entry in storage_parent.iterdir()} == {"g0"}


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows retained-directory boundary"
)
async def test_retained_candidate_storage_prevents_junction_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry-owned candidate cannot be renamed for a junction replacement."""

    import durability

    (
        dispatcher,
        old_host,
        state,
        _lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_close = LoopPlaneHost.aclose
    original_replace = durability._durable_replace
    fail_candidate_close = {"value": True}

    def fail_proof_replace(path: Path, payload: bytes) -> None:
        if path.name == "active-generation-proof.json":
            raise OSError("proof write failed")
        original_replace(path, payload)

    async def fail_discarded_candidate_close(target: LoopPlaneHost) -> None:
        if target is not old_host and fail_candidate_close["value"]:
            raise KeyError("discarded candidate close failed")
        await original_close(target)

    monkeypatch.setattr(durability, "_durable_replace", fail_proof_replace)
    monkeypatch.setattr(LoopPlaneHost, "aclose", fail_discarded_candidate_close)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["error"] == _PUBLICATION_RESTART_ERROR

    storage_parent = state.root / "generation-storage"
    storage = next(entry for entry in storage_parent.iterdir() if entry.name != "g0")
    with pytest.raises(PermissionError):
        storage.rename(tmp_path / "retained-storage")

    fail_candidate_close["value"] = False
    await dispatcher.aclose()  # type: ignore[attr-defined]
    assert {entry.name for entry in storage_parent.iterdir()} == {"g0"}


async def test_proof_replace_effect_with_flush_failure_freezes_for_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A proof replace followed by flush failure is ambiguous, never rollback-safe."""

    import durability

    (
        dispatcher,
        _old_host,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    original_fsync = durability.fsync_path

    def fail_proof_flush(path: Path) -> None:
        if path.name == "active-generation-proof.json":
            raise OSError("proof flush failed after replace")
        original_fsync(path)

    monkeypatch.setattr(durability, "fsync_path", fail_proof_flush)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert response["error"] == _PUBLICATION_RESTART_ERROR
    pointer = json.loads((state.root / "active-generation.json").read_text("utf-8"))
    proof = json.loads((state.root / "active-generation-proof.json").read_text("utf-8"))
    assert proof["active_generation"] == pointer["generation_id"]
    assert pointer["generation_id"] != "g0"
    assert (state.root / "restore-journal-a.json").is_file()
    assert (state.root / "restore-journal-b.json").is_file()
    assert lease.held() is True
    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert listed["error"] == _INTERNAL_FALLBACK_ERROR


async def test_handover_updates_session_audit_and_inspection_principal_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All principal-filtered public RPC projections follow the restored profile."""

    (
        dispatcher,
        _old_host,
        state,
        _lease,
        archive,
        source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    previous_principal = state.principal_id
    seen_principals: list[str | None] = []
    original_status = LoopPlaneHost.capability_settings_status

    def observe_status(
        self: LoopPlaneHost, *, principal_id: str | None = None
    ) -> object:
        seen_principals.append(principal_id)
        return original_status(self, principal_id=principal_id)

    monkeypatch.setattr(LoopPlaneHost, "capability_settings_status", observe_status)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    committed = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )
    assert committed["result"]["committed"] is True
    assert state.principal_id != previous_principal

    listed = await _rpc(dispatcher, 4, "session.list", {})
    session_ids = {item["session_id"] for item in listed["result"]["sessions"]}
    assert source_session_id in session_ids
    assert old_session_id not in session_ids
    audit = await _rpc(
        dispatcher, 5, "audit.list", {"session_id": source_session_id, "limit": 1}
    )
    assert "result" in audit
    capabilities = await _rpc(dispatcher, 6, "capabilities.list", {})
    assert "result" in capabilities
    assert seen_principals[-1] == state.principal_id


async def test_restore_validation_rejects_foreign_principal_checkpoint_inventory(
    tmp_path: Path,
) -> None:
    """A profile cannot authorize sessions owned by another principal."""

    source_state = ProfileState.open(tmp_path / "source-profile")
    source_host = _host(source_state.root)

    async def sink(_event: object) -> None:
        return None

    await source_host.run("owned", sink, principal_id=source_state.principal_id)
    await source_host.run("foreign", sink, principal_id="foreign-principal")
    source_host.enable_desktop_portable_snapshot()
    archive = tmp_path / "mixed-principal.zip"
    created = await BackupMethods(
        source_host, source_state, ProfileMutationLease()
    ).create(
        {
            "mutation_id": "backup-source",
            "acknowledgement": True,
            "destination_path": str(archive),
        }
    )
    assert created["finalized"] is True

    state = ProfileState.open(tmp_path / "destination-profile")
    host = _host(state.root)
    lease = ProfileMutationLease()
    methods = BackupMethods(host, state, lease)

    with pytest.raises(RpcError) as caught:
        await methods.restore_validate(
            {"mutation_id": "restore-owner", "source_path": str(archive)}
        )

    assert getattr(caught.value, "category", None) == "unsafe_input"
    assert lease.held() is False


async def test_session_mutation_and_agent_controls_reject_foreign_principal_session(
    tmp_path: Path,
) -> None:
    """Knowing a hidden session ID grants no mutation or inspection authority."""

    from bridge import build_rpc_dispatcher

    root = tmp_path / "profile"
    state = ProfileState.open(root)
    config = _config(root)
    host = LoopPlaneHost(config, working_scope=root)

    async def sink(_event: object) -> None:
        return None

    owned = await host.run("owned", sink, principal_id=state.principal_id)
    foreign = await host.run("foreign", sink, principal_id="foreign-principal")
    dispatcher = build_rpc_dispatcher(
        host,
        working_scope=root,
        profile_state=state,
        mutation_lease=ProfileMutationLease(),
        principal_id=state.principal_id,
        runtime_config=config,
    )

    initialized = await _rpc(
        dispatcher,
        1,
        "initialize",
        {
            "protocol": {
                "name": PROTOCOL_NAME,
                "major": PROTOCOL_MAJOR,
                "minor": PROTOCOL_MINOR,
            },
            "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
            "client": {"name": "restore-test", "version": "0"},
            "requested_capabilities": [],
        },
    )
    assert "result" in initialized
    listed = await _rpc(dispatcher, 2, "session.list", {})
    listed_ids = {item["session_id"] for item in listed["result"]["sessions"]}
    assert owned.session_id in listed_ids
    assert foreign.session_id not in listed_ids

    attempts = (
        (
            "session.rename",
            {
                "mutation_id": "rename-foreign",
                "session_id": foreign.session_id,
                "title": "changed",
            },
        ),
        (
            "session.setStarred",
            {
                "mutation_id": "star-foreign",
                "session_id": foreign.session_id,
                "starred": True,
            },
        ),
        ("agentControls.get", {"session_id": foreign.session_id}),
    )
    for request_id, (method, params) in enumerate(attempts, start=3):
        response = await _rpc(dispatcher, request_id, method, params)
        assert response["error"]["data"]["category"] == "not_found"


async def test_candidate_storage_copy_failure_leaves_no_partial_runtime_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A materialization failure is compensated before the restore lease is released."""

    import runtime

    (
        dispatcher,
        _old_host,
        state,
        lease,
        archive,
        _source_session_id,
        old_session_id,
    ) = await _initialized_dispatcher(tmp_path)

    def fail_copy(_source: Path, _destination: Path) -> None:
        raise OSError("disk full during candidate storage copy")

    monkeypatch.setattr(runtime, "_stream_copy", fail_copy)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert "error" in response
    storage_parent = state.root / "generation-storage"
    assert {entry.name for entry in storage_parent.iterdir()} == {"g0"}
    assert (state.root / "restore-journal-a.json").exists() is False
    assert (state.root / "restore-journal-b.json").exists() is False
    assert lease.held() is False
    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert {item["session_id"] for item in listed["result"]["sessions"]} == {
        old_session_id
    }


async def test_candidate_host_read_failure_closes_candidate_and_cleans_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Host opened during readiness is closed even if its first public read fails."""

    candidate: list[LoopPlaneHost] = []
    closed: list[LoopPlaneHost] = []
    original_list = LoopPlaneHost.list_sessions
    original_close = LoopPlaneHost.aclose

    def fail_candidate_read(self: LoopPlaneHost) -> object:
        if not candidate:
            candidate.append(self)
            raise RuntimeError("candidate read failed")
        return original_list(self)

    async def observe_close(self: LoopPlaneHost) -> None:
        closed.append(self)
        await original_close(self)

    monkeypatch.setattr(LoopPlaneHost, "list_sessions", fail_candidate_read)
    monkeypatch.setattr(LoopPlaneHost, "aclose", observe_close)
    (
        dispatcher,
        _old_host,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert "error" in response
    assert candidate and candidate[0] in closed
    storage_parent = state.root / "generation-storage"
    assert {entry.name for entry in storage_parent.iterdir()} == {"g0"}
    assert lease.held() is False


async def test_candidate_read_and_close_failure_locks_runtime_until_teardown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retained readiness candidate keeps dispatch and writers fail-locked."""

    candidate: list[LoopPlaneHost] = []
    original_list = LoopPlaneHost.list_sessions
    original_close = LoopPlaneHost.aclose
    fail_candidate_close = {"value": True}
    close_attempts = {"count": 0}

    def fail_candidate_read(target: LoopPlaneHost) -> object:
        if not candidate:
            candidate.append(target)
            raise RuntimeError("candidate read failed")
        return original_list(target)

    async def fail_candidate_cleanup(target: LoopPlaneHost) -> None:
        if candidate and target is candidate[0]:
            close_attempts["count"] += 1
            if fail_candidate_close["value"]:
                raise OSError("candidate close failed")
        await original_close(target)

    monkeypatch.setattr(LoopPlaneHost, "list_sessions", fail_candidate_read)
    monkeypatch.setattr(LoopPlaneHost, "aclose", fail_candidate_cleanup)
    (
        dispatcher,
        _old_host,
        state,
        lease,
        archive,
        _source_session_id,
        _old_session_id,
    ) = await _initialized_dispatcher(tmp_path)
    validated = await _rpc(
        dispatcher,
        2,
        "restore.validate",
        {"mutation_id": "restore-owner", "source_path": str(archive)},
    )
    response = await _rpc(
        dispatcher,
        3,
        "restore.commit",
        {
            "mutation_id": "restore-owner",
            "restore_token": validated["result"]["restore_token"],
            "confirmation": True,
        },
    )

    assert response["error"] == _PUBLICATION_RESTART_ERROR
    storage_parent = state.root / "generation-storage"
    assert candidate and close_attempts["count"] == 2
    assert list(storage_parent.iterdir())
    assert lease.held() is True
    listed = await _rpc(dispatcher, 4, "session.list", {})
    assert listed["error"] == _INTERNAL_FALLBACK_ERROR

    shutdown = await _rpc(dispatcher, 5, "system.shutdown", {})
    assert shutdown["error"]["data"]["category"] == "internal_failure"
    assert close_attempts["count"] == 3
    assert list(storage_parent.iterdir())

    fail_candidate_close["value"] = False
    await dispatcher.aclose()  # type: ignore[attr-defined]
    assert close_attempts["count"] == 4
    assert {entry.name for entry in storage_parent.iterdir()} == {"g0"}
