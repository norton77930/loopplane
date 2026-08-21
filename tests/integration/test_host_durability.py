"""US4: the reference runner end-to-end as a deterministic smoke test —
determinism, durable checkpoint, artifact offload/retrieval, and the example
runner (spec US4; SC-002/004, FR-024/030–033/042).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.artifacts.store import ArtifactSessionDeletion
from loopplane.checkpoint import FileCheckpointStore, SqliteCheckpointStore
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig, assemble
from loopplane.model import TextBlock

from .conftest import (
    BIG_TOOL,
    ECHO_DESCRIPTOR,
    ECHO_TOOL,
    EventCollector,
    big_tool_model,
    text_model,
    tool_then_text_model,
)

pytestmark = pytest.mark.anyio

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from host_quickstart import run_scenario  # noqa: E402


class _RevocableStorageLease:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.valid = True
        self.closed = False
        self.close_failures = 0

    def validate(self) -> None:
        if not self.valid:
            raise RuntimeError("storage authority revoked")

    def close(self) -> None:
        if self.close_failures:
            self.close_failures -= 1
            raise OSError("injected storage authority close failure")
        self.closed = True


class _RevocableStorageAuthority:
    def __init__(self) -> None:
        self.leases: list[_RevocableStorageLease] = []

    def acquire(self, root: Path) -> _RevocableStorageLease:
        lease = _RevocableStorageLease(root)
        self.leases.append(lease)
        return lease


async def test_same_scenario_twice_is_identical(tmp_path: Path) -> None:
    def make_host() -> LoopPlaneHost:
        return LoopPlaneHost(
            RuntimeConfig(model=tool_then_text_model(), tools=(ECHO_TOOL,)),
            working_scope=tmp_path,
        )

    first = EventCollector()
    outcome_one = await make_host().run("go", first)
    second = EventCollector()
    outcome_two = await make_host().run("go", second)

    assert first.types == second.types
    assert outcome_one.termination_reason == outcome_two.termination_reason
    assert outcome_one.turns_taken == outcome_two.turns_taken


async def test_checkpoint_records_are_durable_and_resumable(tmp_path: Path) -> None:
    root = tmp_path / "data"
    host = LoopPlaneHost(
        RuntimeConfig(
            model=tool_then_text_model(),
            tools=(ECHO_TOOL,),
            storage=StorageConfig(root=root),
        ),
        working_scope=tmp_path,
    )
    outcome = await host.run("go", EventCollector())

    # A fresh host over the same storage reconstructs the session from records
    # alone — proving the run was durably recorded (reuses the Phase-1 guarantee).
    reopened = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            tools=(ECHO_TOOL,),
            storage=StorageConfig(root=root),
        ),
        working_scope=tmp_path,
    )
    await reopened.resume(outcome.session_id)
    restored = reopened.history_snapshot(outcome.session_id)

    assert [entry.role for entry in restored] == [
        entry.role for entry in outcome.history
    ]
    assert restored != ()


def test_default_storage_uses_the_file_backend(tmp_path: Path) -> None:
    assembled = assemble(
        RuntimeConfig(model=text_model("x"), storage=StorageConfig(root=tmp_path))
    )
    assert isinstance(assembled.checkpoint_store, FileCheckpointStore)


def test_sqlite_backend_is_selected_when_requested(tmp_path: Path) -> None:
    assembled = assemble(
        RuntimeConfig(
            model=text_model("x"),
            storage=StorageConfig(root=tmp_path, checkpoint_backend="sqlite"),
        )
    )
    assert isinstance(assembled.checkpoint_store, SqliteCheckpointStore)


@pytest.mark.parametrize(
    "operation", ["checkpoint", "artifact", "capability", "snapshot"]
)
async def test_retained_storage_authority_guards_each_store_use(
    tmp_path: Path, operation: str
) -> None:
    authority = _RevocableStorageAuthority()
    root = tmp_path / "data"
    if operation == "snapshot":
        SqliteCheckpointStore(root / "checkpoints.sqlite3").initialize()
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            storage=StorageConfig(
                root=root,
                checkpoint_backend="sqlite",
                authority=authority,
            ),
        )
    )
    lease = authority.leases[-1]
    if operation == "snapshot":
        host.enable_desktop_portable_snapshot()
    lease.valid = False
    try:
        if operation == "capability":
            status = host.capability_settings_status(principal_id="principal")
            assert status.storage_available is False
        elif operation == "snapshot":
            destination = tmp_path / "snapshot"
            destination.mkdir()
            result = host.export_portable_snapshot(destination)
            assert result.ok is False
        else:
            with pytest.raises(RuntimeError, match="storage authority revoked"):
                if operation == "checkpoint":
                    host.list_sessions()
                else:
                    host.retrieve_artifact("session", "reference")
    finally:
        await host.aclose()

    assert lease.closed is True


async def test_host_close_retries_pending_artifact_deletion_before_storage_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX retained-member retry contract")
    authority = _RevocableStorageAuthority()
    root = tmp_path / "data"
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            storage=StorageConfig(
                root=root,
                checkpoint_backend="sqlite",
                authority=authority,
            ),
        )
    )
    lease = authority.leases[-1]
    session_id = host._assembled.controller.create_session(
        working_scope=tmp_path,
        principal_id="owner",
    )
    await host._assembled.artifact_store.offload(
        session_id=session_id,
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    original_commit = host._assembled.artifact_store.commit_session_deletion
    failures = 2

    def fail_twice(deletion: ArtifactSessionDeletion) -> None:
        nonlocal failures
        if failures:
            failures -= 1
            raise OSError("injected artifact erase failure")
        original_commit(deletion)

    monkeypatch.setattr(
        host._assembled.artifact_store,
        "commit_session_deletion",
        fail_twice,
    )
    with pytest.raises(OSError, match="erase failure"):
        host.delete_session(session_id)

    with pytest.raises(OSError, match="erase failure"):
        await host.aclose()
    assert lease.closed is False

    await host.aclose()
    assert lease.closed is True


async def test_host_close_retries_failed_prepare_cleanup_before_storage_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    import loopplane.artifacts.store as artifact_store_module

    authority = _RevocableStorageAuthority()
    root = tmp_path / "data"
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            storage=StorageConfig(
                root=root,
                checkpoint_backend="sqlite",
                authority=authority,
            ),
        )
    )
    lease = authority.leases[-1]
    session_id = host._assembled.controller.create_session(
        working_scope=tmp_path,
        principal_id="owner",
    )
    await host._assembled.artifact_store.offload(
        session_id=session_id,
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    store = host._assembled.artifact_store
    original_validate = store._validate_staged_tree
    original_anchor_close = artifact_store_module._windows_close_directory_anchor
    original_os_close = os.close
    # Windows cannot move a directory that still has open handles, so the failed
    # prepare retains its authority without ever attempting a close and the
    # single injected failure lands on the close retry. POSIX rolls the staged
    # move back with the anchors still open, so the cleanup close does run during
    # the delete and the same descriptor has to refuse a second time.
    failures = 1 if sys.platform == "win32" else 2
    target_authority: int | None = None

    def fail_validation(*args: object, **kwargs: object) -> None:
        original_validate(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("validation failed")

    monkeypatch.setattr(store, "_validate_staged_tree", fail_validation)
    if sys.platform == "win32":

        def fail_once(handle: int) -> None:
            nonlocal failures, target_authority
            if target_authority is None:
                target_authority = handle
            if handle == target_authority and failures:
                failures -= 1
                raise OSError("injected prepare close failure")
            original_anchor_close(handle)

        monkeypatch.setattr(
            artifact_store_module,
            "_windows_close_directory_anchor",
            fail_once,
        )
    else:

        def fail_once(descriptor: int) -> None:
            nonlocal failures, target_authority
            if target_authority is None:
                target_authority = descriptor
            if descriptor == target_authority and failures:
                failures -= 1
                raise OSError("injected prepare close failure")
            original_os_close(descriptor)

        monkeypatch.setattr(os, "close", fail_once)

    with pytest.raises(RuntimeError, match="rollback blocked"):
        host.delete_session(session_id)

    with pytest.raises(OSError, match="prepare close failure"):
        await host.aclose()
    assert lease.closed is False

    await host.aclose()
    assert lease.closed is True


async def test_storage_authority_close_failure_remains_retryable(
    tmp_path: Path,
) -> None:
    authority = _RevocableStorageAuthority()
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            storage=StorageConfig(
                root=tmp_path / "data",
                checkpoint_backend="sqlite",
                authority=authority,
            ),
        )
    )
    lease = authority.leases[-1]
    lease.close_failures = 1

    with pytest.raises(OSError, match="close failure"):
        await host.aclose()
    assert lease.closed is False

    await host.aclose()
    assert lease.closed is True


async def test_sqlite_backend_records_are_durable_and_resumable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    host = LoopPlaneHost(
        RuntimeConfig(
            model=tool_then_text_model(),
            tools=(ECHO_TOOL,),
            storage=StorageConfig(root=root, checkpoint_backend="sqlite"),
        ),
        working_scope=tmp_path,
    )
    outcome = await host.run("go", EventCollector())

    # Persisted to the SQLite database, not per-session files.
    assert (root / "checkpoints.sqlite3").is_file()

    reopened = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            tools=(ECHO_TOOL,),
            storage=StorageConfig(root=root, checkpoint_backend="sqlite"),
        ),
        working_scope=tmp_path,
    )
    await reopened.resume(outcome.session_id)
    restored = reopened.history_snapshot(outcome.session_id)

    assert [entry.role for entry in restored] == [
        entry.role for entry in outcome.history
    ]
    assert restored != ()


async def test_oversized_output_is_offloaded_and_retrievable(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=big_tool_model(),
            tools=(BIG_TOOL,),
            storage=StorageConfig(root=tmp_path / "data"),
        ),
        working_scope=tmp_path,
    )
    sink = EventCollector()

    outcome = await host.run("go", sink)

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.artifact_reference is not None
    full = host.retrieve_artifact(
        outcome.session_id, completed.payload.artifact_reference
    )
    assert full is not None
    assert len(full) >= 200_000


async def test_example_runner_drives_a_deterministic_scenario(tmp_path: Path) -> None:
    outcome_one = await run_scenario("tool", working_scope=tmp_path)
    outcome_two = await run_scenario("tool", working_scope=tmp_path)
    assert outcome_one.termination_reason == "natural-completion"
    assert outcome_one.termination_reason == outcome_two.termination_reason


async def test_example_runner_reports_a_clear_message_on_unknown_scenario(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError) as excinfo:
        await run_scenario("does-not-exist", working_scope=tmp_path)
    assert "unknown scenario" in str(excinfo.value)


def test_example_uses_the_single_assembly_path() -> None:
    # The facade and the example reach the runtime through the same assemble()
    # path — the example embeds via LoopPlaneHost, never a parallel wiring of the
    # Runtime Controller (FR-024).
    import host_quickstart

    source = Path(host_quickstart.__file__).read_text(encoding="utf-8")
    assert "LoopPlaneHost" in source
    assert "RuntimeController" not in source


def test_example_echo_tool_matches_the_test_fixture() -> None:
    # The example intentionally defines its own self-contained echo tool (so it
    # stays copy-pasteable); this guards it against silently drifting from the
    # test fixture's contract (review #8).
    from host_quickstart import _ECHO

    assert _ECHO.name == ECHO_DESCRIPTOR.name
    assert _ECHO.input_schema == ECHO_DESCRIPTOR.input_schema


async def test_sqlite_turn_audit_reopens_from_checkpoints_without_writing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "audit-data"
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("done"),
            storage=StorageConfig(root=root, checkpoint_backend="sqlite"),
        ),
        working_scope=tmp_path,
    )
    outcome = await host.run("durable-private-audit-prompt", EventCollector())
    checkpoint = root / "checkpoints.sqlite3"
    bytes_before = checkpoint.read_bytes()
    original = host.list_turn_audit(outcome.session_id)

    reopened = LoopPlaneHost(
        RuntimeConfig(
            model=text_model("unused"),
            storage=StorageConfig(root=root, checkpoint_backend="sqlite"),
        ),
        working_scope=tmp_path,
    )
    restored = reopened.list_turn_audit(outcome.session_id)

    assert restored == original
    assert restored[0].state == "completed"
    assert restored[0].termination_reason == outcome.termination_reason
    assert "durable-private-audit-prompt" not in repr(restored)
    assert checkpoint.read_bytes() == bytes_before
