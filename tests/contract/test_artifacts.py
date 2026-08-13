"""Contract tests for Artifact Storage (contracts/artifacts.md).

Asserts threshold offload with a bounded preview and stable reference,
retrieval by reference, and the aggregate replacement budget staying frozen
across resume (FR-090–FR-093).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loopplane.artifacts import ArtifactStore, ReplacementLedger
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.model import (
    OutputBlock,
    TextBlock,
    ToolCallRequest,
    ToolDescriptor,
)

pytestmark = pytest.mark.anyio


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


async def test_offload_persists_full_content_and_returns_preview_and_reference(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path, preview_chars=64)
    big = "x" * 10_000

    reference, preview = await store.offload(
        session_id="s1", call_id="c1", outputs=[TextBlock(text=big)]
    )

    assert reference
    assert len(preview) < len(big)
    assert store.retrieve("s1", reference) == big

    metadata = store.metadata("s1", reference)
    assert metadata is not None
    assert metadata.call_id == "c1"
    assert metadata.size == len(big.encode("utf-8"))
    assert metadata.media_kind == "text"


def test_unknown_reference_is_a_normal_not_found(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    assert store.retrieve("s1", "never-issued") is None
    assert store.metadata("s1", "never-issued") is None


async def test_gateway_offloads_oversized_results_through_the_handoff(
    tmp_path: Path,
) -> None:
    """Acceptance 3.3 at the gateway seam: the full output is preserved as
    an artifact and the result carries preview + stable reference (FR-090,
    FR-091).
    """
    artifact_store = ArtifactStore(tmp_path, preview_chars=64)

    async def handoff(
        call: ToolCallRequest, outputs: list[OutputBlock], context: RunContext
    ) -> tuple[str, str]:
        return await artifact_store.offload(
            session_id=context.session_id, call_id=call.call_id, outputs=outputs
        )

    big = "line of output\n" * 2_000

    async def big_tool(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        return [TextBlock(text=big)]

    gateway = ToolGateway(output_limit_bytes=512, artifact_handoff=handoff)
    gateway.register(
        ToolDescriptor(
            name="big",
            description="produces a lot of output",
            input_schema={"type": "object"},
        ),
        big_tool,
    )

    results = await gateway.execute_batch(
        [ToolCallRequest(call_id="c1", tool_name="big", input={})],
        parallel=False,
        context=RunContext(session_id="s1", working_scope=tmp_path),
        emitter=EventEmitter(
            session_id="s1", sequencer=EventSequencer(), sink=_Collector()
        ),
    )

    (result,) = results
    assert result.outcome == "success"
    assert result.artifact_reference is not None
    preview_text = "".join(
        block.text for block in result.outputs if isinstance(block, TextBlock)
    )
    assert len(preview_text) < len(big)
    assert artifact_store.retrieve("s1", result.artifact_reference) == big


async def test_session_cleanup_does_not_unlink_through_mutable_parent_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detached cleanup must anchor erasure to opened, no-follow authorities."""

    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    original_unlink = Path.unlink
    truncated = False

    def verify_erasure_before_unlink(path: Path, missing_ok: bool = False) -> None:
        nonlocal truncated
        if ".d" in path.parts:
            assert path.stat().st_size == 0
            truncated = True
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", verify_erasure_before_unlink)

    store.delete_session("s1")

    assert (tmp_path / "s1").exists() is False
    if os.name != "nt":
        assert truncated is True
        assert (tmp_path / ".d").exists() is False


async def test_shared_session_rollback_anchors_parent_during_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback must not restore artifacts through a replaced session path."""

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    replacement = tmp_path / "replacement"

    if os.name == "nt":
        original_replace = os.replace
        replacement_blocked = False

        def replace_during_rollback(source: Path, destination: Path) -> None:
            nonlocal replacement_blocked
            try:
                session.rename(replacement)
            except PermissionError:
                replacement_blocked = True
            original_replace(source, destination)

        monkeypatch.setattr(os, "replace", replace_during_rollback)
        store.rollback_session_deletion(deletion)
        assert replacement_blocked is True
        assert (session / "artifacts").is_dir()
        assert replacement.exists() is False
        return

    original_rename = os.rename
    replacement_attempted = False

    def rename_during_rollback(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal replacement_attempted
        if src_dir_fd is not None and not replacement_attempted:
            replacement_attempted = True
            original_rename(session, replacement)
        original_rename(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "rename", rename_during_rollback)
    with pytest.raises(RuntimeError, match="artifact deletion rollback blocked"):
        store.rollback_session_deletion(deletion)

    assert replacement_attempted is True
    assert (replacement / "artifacts").exists() is False
    assert (deletion.staged / "artifacts").is_dir()


async def test_shared_session_commit_erases_exact_detached_staging_tree(
    tmp_path: Path,
) -> None:
    """Commit erases the retained tree without touching a path replacement."""

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    moved = tmp_path / "moved-staging"

    try:
        deletion.staged.rename(moved)
    except PermissionError:
        replacement_blocked = True
    else:
        replacement_blocked = False
        replacement_artifacts = deletion.staged / "artifacts"
        replacement_artifacts.mkdir(parents=True)
        unrelated = replacement_artifacts / "unrelated.txt"
        unrelated.write_text("unrelated", encoding="utf-8")

    store.commit_session_deletion(deletion)

    if replacement_blocked:
        assert deletion.staged.exists() is False
        return
    assert unrelated.read_text(encoding="utf-8") == "unrelated"
    assert moved.is_dir()
    assert all(member.stat().st_size == 0 for member in (moved / "artifacts").iterdir())


async def test_shared_session_prepare_rejects_artifacts_child_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The moved child must be the exact directory validated before prepare."""

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    original_artifacts = session / "original-artifacts"
    replacement_file: Path | None = None

    if os.name == "nt":
        original_replace = os.replace
        replaced = False

        def replace_child(source: Path, destination: Path) -> None:
            nonlocal replaced, replacement_file
            if not replaced and Path(source) == session / "artifacts":
                replaced = True
                original_replace(source, original_artifacts)
                Path(source).mkdir()
                replacement_file = Path(source) / "unrelated.txt"
                replacement_file.write_text("unrelated", encoding="utf-8")
            original_replace(source, destination)

        monkeypatch.setattr(os, "replace", replace_child)
    else:
        original_rename = os.rename
        replaced = False

        def rename_child(
            source: str,
            destination: str,
            *,
            src_dir_fd: int | None = None,
            dst_dir_fd: int | None = None,
        ) -> None:
            nonlocal replaced, replacement_file
            if src_dir_fd is not None and not replaced:
                replaced = True
                original_rename(session / "artifacts", original_artifacts)
                (session / "artifacts").mkdir()
                replacement_file = session / "artifacts" / "unrelated.txt"
                replacement_file.write_text("unrelated", encoding="utf-8")
            original_rename(
                source,
                destination,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
            )

        monkeypatch.setattr(os, "rename", rename_child)

    with pytest.raises(RuntimeError, match="artifact deletion"):
        store.prepare_session_deletion("s1")

    assert replaced is True
    assert original_artifacts.is_dir()
    assert replacement_file is not None
    quarantined_replacement = next((tmp_path / ".d").glob("*/artifacts/unrelated.txt"))
    assert quarantined_replacement.read_text(encoding="utf-8") == "unrelated"


async def test_commit_close_never_erases_replaced_member(
    tmp_path: Path,
) -> None:
    """Exact-member cleanup erases only the retained object."""

    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    artifact = next((deletion.staged / "artifacts").glob("*.txt"))
    moved = artifact.with_name("owned-moved.txt")

    try:
        artifact.rename(moved)
    except PermissionError:
        replacement_blocked = True
    else:
        replacement_blocked = False
        artifact.write_text("unrelated", encoding="utf-8")

    if replacement_blocked:
        store.commit_session_deletion(deletion)
        assert artifact.exists() is False
        return

    with pytest.raises(RuntimeError, match="artifact deletion authority changed"):
        store.commit_session_deletion(deletion)
    assert artifact.read_text(encoding="utf-8") == "unrelated"
    assert moved.exists()


async def test_windows_partial_member_delete_remains_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial Windows delete keeps exact handles and resumes by phase."""

    if os.name != "nt":
        pytest.skip("Windows retained-member retry contract")
    import loopplane.artifacts.store as artifact_store_module

    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    original_ctypes = artifact_store_module._windows_ctypes
    calls = 0

    class _FailingKernel32:
        def __init__(self, real: object) -> None:
            self._real = real

        def __getattr__(self, name: str) -> object:
            target = getattr(self._real, name)
            if name != "SetFileInformationByHandle":
                return target

            def fail_second(*args: object) -> object:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected member delete failure")
                return target(*args)

            return fail_second

    class _FailingCtypes:
        def __getattr__(self, name: str) -> object:
            if name == "WinDLL":

                def win_dll(*args: object, **kwargs: object) -> _FailingKernel32:
                    return _FailingKernel32(original_ctypes().WinDLL(*args, **kwargs))

                return win_dll
            return getattr(original_ctypes(), name)

    monkeypatch.setattr(
        artifact_store_module,
        "_windows_ctypes",
        lambda: _FailingCtypes(),
    )
    with pytest.raises(OSError, match="member delete failure"):
        store.commit_session_deletion(deletion)

    assert deletion.members_delete_pending is True
    assert deletion.member_handles
    monkeypatch.setattr(
        artifact_store_module,
        "_windows_ctypes",
        original_ctypes,
    )
    store.commit_session_deletion(deletion)
    assert deletion.erased is True
    assert deletion.has_retained_authority is False
    assert (tmp_path / ".d").exists() is False


async def test_windows_partial_directory_delete_remains_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows resumes after members or artifacts were already deleted."""

    if os.name != "nt":
        pytest.skip("Windows retained-directory retry contract")
    import loopplane.artifacts.store as artifact_store_module

    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    original_ctypes = artifact_store_module._windows_ctypes
    calls = 0

    class _FailingKernel32:
        def __init__(self, real: object) -> None:
            self._real = real

        def __getattr__(self, name: str) -> object:
            target = getattr(self._real, name)
            if name != "SetFileInformationByHandle":
                return target

            def fail_session(*args: object) -> object:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("injected session delete failure")
                return target(*args)

            return fail_session

    class _FailingCtypes:
        def __getattr__(self, name: str) -> object:
            if name == "WinDLL":

                def win_dll(*args: object, **kwargs: object) -> _FailingKernel32:
                    return _FailingKernel32(original_ctypes().WinDLL(*args, **kwargs))

                return win_dll
            return getattr(original_ctypes(), name)

    monkeypatch.setattr(
        artifact_store_module,
        "_windows_ctypes",
        lambda: _FailingCtypes(),
    )
    with pytest.raises(OSError, match="session delete failure"):
        store.commit_session_deletion(deletion)

    assert deletion.members_delete_pending is False
    assert deletion.artifacts_delete_pending is False
    assert deletion.session_delete_pending is True
    assert deletion.staged.exists()
    monkeypatch.setattr(
        artifact_store_module,
        "_windows_ctypes",
        original_ctypes,
    )
    store.commit_session_deletion(deletion)
    assert deletion.erased is True
    assert deletion.has_retained_authority is False
    assert deletion.staged.exists() is False


async def test_posix_member_race_truncates_retained_object_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POSIX cleanup never unlinks a same-name replacement."""

    if os.name == "nt":
        pytest.skip("POSIX retained-member contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    artifact = next((deletion.staged / "artifacts").glob("*.txt"))
    moved = artifact.with_name("owned-moved.txt")
    replacement = b"unrelated"
    original_ftruncate = os.ftruncate
    injected = False

    def replace_before_truncate(descriptor: int, length: int) -> None:
        nonlocal injected
        if not injected:
            injected = True
            artifact.rename(moved)
            artifact.write_bytes(replacement)
        original_ftruncate(descriptor, length)

    monkeypatch.setattr(os, "ftruncate", replace_before_truncate)
    store.commit_session_deletion(deletion)

    assert injected is True
    assert artifact.read_bytes() == replacement
    assert moved.read_bytes() == b""


async def test_posix_partial_erase_failure_remains_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial POSIX erase retains authority for an exact retry."""

    if os.name == "nt":
        pytest.skip("POSIX retained-member retry contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    original_ftruncate = os.ftruncate
    failures = 1

    def fail_once(descriptor: int, length: int) -> None:
        nonlocal failures
        if failures:
            failures -= 1
            raise OSError("injected erase failure")
        original_ftruncate(descriptor, length)

    monkeypatch.setattr(os, "ftruncate", fail_once)
    with pytest.raises(OSError, match="erase failure"):
        store.commit_session_deletion(deletion)

    assert deletion.member_descriptors
    store.commit_session_deletion(deletion)
    assert not deletion.member_descriptors


async def test_posix_deletions_leave_no_quarantine_metadata(
    tmp_path: Path,
) -> None:
    """Committed POSIX deletions cannot accumulate names or directory shells."""

    if os.name == "nt":
        pytest.skip("POSIX quarantine cleanup contract")
    store = ArtifactStore(tmp_path)
    for session_id in ("s1", "s2"):
        await store.offload(
            session_id=session_id,
            call_id=f"c-{session_id}",
            outputs=[TextBlock(text=f"{session_id} artifact")],
        )
        deletion = store.prepare_session_deletion(session_id)
        assert deletion is not None
        assert (tmp_path / session_id).exists() is False

        store.commit_session_deletion(deletion)

        assert deletion.staged.exists() is False
        assert (tmp_path / ".d").exists() is False


async def test_posix_rollback_never_replaces_unvalidated_destination(
    tmp_path: Path,
) -> None:
    """Rollback cannot remove a same-name object created after detach."""

    if os.name == "nt":
        pytest.skip("POSIX rollback replacement contract")
    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    replacement = session / "artifacts"
    replacement.mkdir()

    with pytest.raises(RuntimeError, match="rollback blocked"):
        store.rollback_session_deletion(deletion)

    assert replacement.is_dir()
    assert list(replacement.iterdir()) == []
    assert (deletion.staged / "artifacts").is_dir()
    assert deletion.has_retained_authority is True
    replacement.rmdir()
    store.rollback_session_deletion(deletion)
    assert (session / "artifacts").is_dir()


async def test_posix_shared_second_deletion_still_rolls_back(
    tmp_path: Path,
) -> None:
    """An earlier committed shell cannot consume a later rollback authority."""

    if os.name == "nt":
        pytest.skip("POSIX quarantine isolation contract")
    store = ArtifactStore(tmp_path)
    first_session = tmp_path / "s1"
    first_session.mkdir()
    (first_session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="first artifact")],
    )
    first = store.prepare_session_deletion("s1")
    assert first is not None
    store.commit_session_deletion(first)

    second_session = tmp_path / "s2"
    second_session.mkdir()
    (second_session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s2",
        call_id="c2",
        outputs=[TextBlock(text="second artifact")],
    )
    second = store.prepare_session_deletion("s2")
    assert second is not None
    assert (second_session / "artifacts").exists() is False

    store.rollback_session_deletion(second)

    restored = next((second_session / "artifacts").glob("*.txt"))
    assert restored.read_text(encoding="utf-8") == "second artifact"


async def test_posix_cleanup_revalidates_every_member_before_unlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cleanup stops before unlink when any retained name was replaced."""

    if os.name == "nt":
        pytest.skip("POSIX cleanup replacement contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    members = sorted((deletion.staged / "artifacts").iterdir())
    first, second = members
    original_lstat = os.lstat
    second_checks = 0
    injected = False

    def replace_second_before_its_unlink(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        nonlocal injected, second_checks
        if Path(path) == second:
            second_checks += 1
            if second_checks == 3:
                injected = True
                second.rename(second.with_name("owned-second"))
                second.write_text("unrelated", encoding="utf-8")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", replace_second_before_its_unlink)
    with pytest.raises(RuntimeError, match="authority changed"):
        store.commit_session_deletion(deletion)

    assert injected is True
    assert first.exists()
    assert second.read_text(encoding="utf-8") == "unrelated"


async def test_posix_cleanup_never_unlinks_after_last_identity_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-name replacement after validation cannot be path-unlinked."""

    if os.name == "nt":
        pytest.skip("POSIX cleanup replacement contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    member = next((deletion.staged / "artifacts").iterdir())
    moved = member.with_name(f"{member.name}.owned")
    replacement = b"unrelated"
    original_unlink = Path.unlink
    injected = False

    def replace_at_unlink(path: Path, missing_ok: bool = False) -> None:
        nonlocal injected
        if path == member and not injected:
            injected = True
            path.rename(moved)
            path.write_bytes(replacement)
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", replace_at_unlink)
    store.commit_session_deletion(deletion)

    assert injected is False
    assert member.exists() is False
    assert moved.exists() is False
    assert deletion.staged.exists() is False


async def test_posix_partial_metadata_cleanup_remains_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial quarantine cleanup retains authority and finishes on retry."""

    if os.name == "nt":
        pytest.skip("POSIX metadata retry contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    original_unlink = os.unlink
    failures = 1

    def fail_second(name: str, *, dir_fd: int | None = None) -> None:
        nonlocal failures
        if failures and name.endswith(".txt"):
            failures -= 1
            raise OSError("injected metadata cleanup failure")
        original_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", fail_second)
    with pytest.raises(OSError, match="metadata cleanup failure"):
        store.commit_session_deletion(deletion)

    assert deletion.erased is True
    assert deletion.has_retained_authority is True
    store.commit_session_deletion(deletion)
    assert deletion.has_retained_authority is False
    assert deletion.staged.exists() is False
    assert (tmp_path / ".d").exists() is False


async def test_posix_rollback_move_cannot_replace_late_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback uses one no-replace move, not a check-then-rename window."""

    if os.name == "nt":
        pytest.skip("POSIX rollback replacement contract")
    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    replacement = session / "artifacts"
    original_move = store._move_anchored_directory
    injected = False

    def create_destination_before_move(*args: object, **kwargs: object) -> None:
        nonlocal injected
        if not injected:
            injected = True
            replacement.mkdir()
        original_move(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        store,
        "_move_anchored_directory",
        create_destination_before_move,
    )
    object.__setattr__(deletion, "rollback_required", True)
    with pytest.raises(RuntimeError, match="rollback blocked"):
        store.rollback_session_deletion(deletion)

    assert replacement.is_dir()
    assert list(replacement.iterdir()) == []
    assert (deletion.staged / "artifacts").is_dir()


async def test_rollback_compensation_failure_resumes_from_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-move failure records destination authority for a later close retry."""

    if os.name == "nt":
        pytest.skip("POSIX rollback phase contract")
    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    import loopplane.artifacts.store as artifact_store_module

    original_parent_check = artifact_store_module._directory_path_matches_anchor
    checks = 0

    def fail_post_move(anchor: object) -> bool:
        nonlocal checks
        if anchor is deletion.original_parent_anchor:
            checks += 1
            if checks == 2:
                return False
        return original_parent_check(anchor)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "loopplane.artifacts.store._directory_path_matches_anchor",
        fail_post_move,
    )
    original_move = store._move_anchored_directory
    moves = 0

    def fail_compensation(*args: object, **kwargs: object) -> None:
        nonlocal moves
        moves += 1
        if moves == 2:
            raise OSError("injected compensation failure")
        original_move(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "_move_anchored_directory", fail_compensation)
    object.__setattr__(deletion, "rollback_required", True)
    with pytest.raises(RuntimeError, match="compensation blocked"):
        store.rollback_session_deletion(deletion)

    assert deletion.rollback_applied is True
    assert (session / "artifacts").is_dir()
    monkeypatch.setattr(store, "_move_anchored_directory", original_move)
    store.retry_session_deletion(deletion)
    assert deletion.rollback_required is False
    assert deletion.has_retained_authority is False


async def test_posix_commit_never_removes_session_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POSIX cleanup retains directory authority instead of pathname rmdir."""

    if os.name == "nt":
        pytest.skip("POSIX retained-directory contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    moved = deletion.staged.with_name("owned-staging-moved")
    replacement_file = deletion.staged / "unrelated.txt"
    original_ftruncate = os.ftruncate
    injected = False

    def replace_before_truncate(descriptor: int, length: int) -> None:
        nonlocal injected
        if not injected:
            injected = True
            deletion.staged.rename(moved)
            deletion.staged.mkdir()
            replacement_file.write_text("unrelated", encoding="utf-8")
        original_ftruncate(descriptor, length)

    monkeypatch.setattr(os, "ftruncate", replace_before_truncate)
    store.commit_session_deletion(deletion)

    assert injected is True
    assert replacement_file.read_text(encoding="utf-8") == "unrelated"
    assert moved.is_dir()


async def test_close_failure_retains_authority_for_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Erasure success cannot discard a failed authority close."""

    if os.name == "nt":
        pytest.skip("POSIX retained-member close contract")
    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    retained = deletion.member_descriptors[0]
    original_close = os.close
    failures = 1

    def fail_once(descriptor: int) -> None:
        nonlocal failures
        if descriptor == retained and failures:
            failures -= 1
            raise OSError("injected authority close failure")
        original_close(descriptor)

    monkeypatch.setattr(os, "close", fail_once)
    with pytest.raises(OSError, match="close failure"):
        store.commit_session_deletion(deletion)

    assert deletion.erased is True
    assert deletion.member_descriptors == (retained,)
    store.commit_session_deletion(deletion)
    assert not deletion.member_descriptors


async def test_commit_preflight_failure_closes_retained_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed commit preflight cannot leak retained directory authority."""

    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None

    def reject_root() -> None:
        raise RuntimeError("root unavailable")

    monkeypatch.setattr(store, "_require_root", reject_root)
    with pytest.raises(RuntimeError, match="root unavailable"):
        store.commit_session_deletion(deletion)

    for anchor in (
        deletion.original_parent_anchor,
        deletion.quarantine_root_anchor,
        deletion.staged_parent_anchor,
        deletion.detached_anchor,
        deletion.artifacts_anchor,
    ):
        assert anchor._handle is None
        assert anchor._descriptor is None


async def test_rollback_compensation_failure_remains_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restored tree with failed compensation resumes from original."""

    import loopplane.artifacts.store as artifact_store_module

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    original_move = store._move_anchored_directory
    original_path_matches = artifact_store_module._directory_path_matches_anchor
    moves = 0
    path_checks = 0

    def fail_post_move_parent_check(anchor: object) -> bool:
        nonlocal path_checks
        path_checks += 1
        if path_checks == 2:
            return False
        return original_path_matches(anchor)  # type: ignore[arg-type]

    def fail_compensation(*args: object, **kwargs: object) -> None:
        nonlocal moves
        moves += 1
        if moves == 2:
            raise RuntimeError("compensation blocked")
        original_move(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        artifact_store_module,
        "_directory_path_matches_anchor",
        fail_post_move_parent_check,
    )
    monkeypatch.setattr(store, "_move_anchored_directory", fail_compensation)
    object.__setattr__(deletion, "rollback_required", True)

    with pytest.raises(RuntimeError, match="compensation blocked"):
        store.rollback_session_deletion(deletion)

    assert (session / "artifacts").is_dir()
    assert deletion.rollback_required is True
    store.retry_session_deletion(deletion)
    assert deletion.rollback_required is False
    assert deletion.has_retained_authority is False


async def test_rollback_close_failure_remains_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restored tree keeps failed close authority until a later retry."""

    import loopplane.artifacts.store as artifact_store_module

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    original_close = artifact_store_module._windows_close_directory_anchor
    retained_handle = deletion.original_parent_anchor._handle
    retained_descriptor = deletion.original_parent_anchor._descriptor
    failures = 1

    if os.name == "nt":

        def fail_once(handle: int) -> None:
            nonlocal failures
            if handle == retained_handle and failures:
                failures -= 1
                raise OSError("injected rollback close failure")
            original_close(handle)

        monkeypatch.setattr(
            artifact_store_module,
            "_windows_close_directory_anchor",
            fail_once,
        )
    else:
        original_os_close = os.close

        def fail_once(descriptor: int) -> None:
            nonlocal failures
            if descriptor == retained_descriptor and failures:
                failures -= 1
                raise OSError("injected rollback close failure")
            original_os_close(descriptor)

        monkeypatch.setattr(os, "close", fail_once)

    object.__setattr__(deletion, "rollback_required", True)
    with pytest.raises(OSError, match="rollback close failure"):
        store.rollback_session_deletion(deletion)

    assert (session / "artifacts").is_dir()
    assert deletion.rollback_required is True
    assert deletion.has_retained_authority is True
    store.retry_session_deletion(deletion)
    assert deletion.rollback_required is False
    assert deletion.has_retained_authority is False


async def test_shared_session_rollback_preflight_failure_closes_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct rollback preflight failure releases caller-owned authority."""

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    deletion = store.prepare_session_deletion("s1")
    assert deletion is not None
    anchor = deletion.shared_parent_anchor
    assert anchor is not None

    def reject_root() -> None:
        raise RuntimeError("root unavailable")

    monkeypatch.setattr(store, "_require_root", reject_root)
    with pytest.raises(RuntimeError, match="root unavailable"):
        store.rollback_session_deletion(deletion)

    assert anchor._handle is None
    assert anchor._descriptor is None


async def test_prepare_close_failure_releases_all_other_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prepare reports close failure without leaving unrelated anchors open."""

    import loopplane.artifacts.store as artifact_store_module

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    original_validate = store._validate_staged_tree
    original_close = artifact_store_module._windows_close_directory_anchor
    original_os_close = os.close
    failures = 2
    target_authority: int | None = None

    def fail_validation(*args: object, **kwargs: object) -> None:
        original_validate(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("validation failed")

    monkeypatch.setattr(store, "_validate_staged_tree", fail_validation)
    if os.name == "nt":

        def fail_twice(handle: int) -> None:
            nonlocal failures, target_authority
            if target_authority is None:
                target_authority = handle
            if handle == target_authority and failures:
                failures -= 1
                raise OSError("injected prepare close failure")
            original_close(handle)

        monkeypatch.setattr(
            artifact_store_module,
            "_windows_close_directory_anchor",
            fail_twice,
        )
    else:

        def fail_twice(descriptor: int) -> None:
            nonlocal failures, target_authority
            if target_authority is None:
                target_authority = descriptor
            if descriptor == target_authority and failures:
                failures -= 1
                raise OSError("injected prepare close failure")
            original_os_close(descriptor)

        monkeypatch.setattr(os, "close", fail_twice)

    with pytest.raises(RuntimeError, match="rollback blocked"):
        store.prepare_session_deletion("s1")

    assert (session / "artifacts").is_dir()
    with pytest.raises(OSError, match="prepare close failure"):
        store.retry_pending_authority_cleanups()
    store.retry_pending_authority_cleanups()
    session.rename(tmp_path / "session-moved")


async def test_prepare_compensation_failure_remains_store_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed prepare rollback keeps exact authority for Store retry."""

    store = ArtifactStore(tmp_path)
    session = tmp_path / "s1"
    session.mkdir()
    (session / "records.jsonl").write_text("record\n", encoding="utf-8")
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    original_validate = store._validate_staged_tree
    original_move = store._move_anchored_directory
    moves = 0

    def fail_validation(*args: object, **kwargs: object) -> None:
        original_validate(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("validation failed")

    def fail_compensation(*args: object, **kwargs: object) -> None:
        nonlocal moves
        moves += 1
        if moves == 2:
            raise RuntimeError("compensation blocked")
        original_move(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "_validate_staged_tree", fail_validation)
    monkeypatch.setattr(store, "_move_anchored_directory", fail_compensation)

    with pytest.raises(RuntimeError, match="rollback blocked"):
        store.prepare_session_deletion("s1")

    assert (session / "artifacts").exists() is False
    assert next((tmp_path / ".d").glob("*/artifacts")).is_dir()
    store.retry_pending_authority_cleanups()
    assert (session / "artifacts").is_dir()
    assert (tmp_path / ".d").exists() is False


async def test_replacement_budget_replaces_largest_results_first(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path, preview_chars=32)
    ledger = ReplacementLedger(budget_bytes=300, store=store, session_id="s1")

    assert await ledger.track("small", [TextBlock(text="s" * 100)]) == []
    assert await ledger.track("medium", [TextBlock(text="m" * 150)]) == []
    decisions = await ledger.track("large", [TextBlock(text="L" * 200)])

    assert decisions, "exceeding the budget must produce replacement decisions"
    assert decisions[0].replaced_call_id == "large"
    assert len(decisions[0].preview) < 200
    assert store.retrieve("s1", decisions[0].artifact_reference) == "L" * 200


async def test_replacement_decisions_are_frozen_across_resume(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, preview_chars=32)
    ledger = ReplacementLedger(budget_bytes=300, store=store, session_id="s1")
    await ledger.track("a", [TextBlock(text="a" * 200)])
    decisions = list(await ledger.track("b", [TextBlock(text="b" * 250)]))
    assert decisions

    # Resume: a fresh ledger restores the recorded decisions instead of
    # re-deciding; the replacement state reproduces exactly (FR-092).
    resumed = ReplacementLedger(budget_bytes=300, store=store, session_id="s1")
    resumed.restore(ledger.decisions)

    assert resumed.decisions == ledger.decisions
    assert {d.replaced_call_id for d in resumed.decisions} == {
        d.replaced_call_id for d in ledger.decisions
    }
