"""Worktree isolation tool tests (spec 051). Offline + deterministic: a fake
``GitRunner`` for the logic, plus one real-``git`` isolation test guarded by
git availability."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import anyio
import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.host.assembly import assemble
from loopplane.host.config import RuntimeConfig
from loopplane.model.boundary import ModelIncrement, ModelRequest
from loopplane.model.content import TextBlock
from loopplane.tools.worktree import (
    AnyioGitRunner,
    Worktree,
    WorktreeManager,
    WorktreeToolsAdapter,
    _within,
)

pytestmark = pytest.mark.anyio


class FakeGitRunner:
    """A deterministic git runner: records calls, simulates add/remove on disk."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._fail = fail

    async def run(self, args: Sequence[str]) -> tuple[int, str, str]:
        self.calls.append(list(args))
        if self._fail:
            return (1, "", "fatal: not a git repository")
        if len(args) >= 2 and args[0] == "worktree" and args[1] == "add":
            Path(args[-1]).mkdir(parents=True, exist_ok=True)
        elif len(args) >= 3 and args[0] == "worktree" and args[1] == "remove":
            target = Path(args[-1])
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
        return (0, "", "")


def _ctx(manager: WorktreeManager | None, scope: Path) -> RunContext:
    return RunContext(session_id="s", working_scope=scope, worktrees=manager)


async def _invoke(
    adapter: WorktreeToolsAdapter,
    name: str,
    call_input: dict[str, object],
    ctx: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, ctx)]


# --- US1: create an isolated worktree -----------------------------------------


async def test_create_returns_worktree_within_scope(tmp_path: Path) -> None:
    runner = FakeGitRunner()
    mgr = WorktreeManager(working_scope=tmp_path, runner=runner, max_worktrees=3)
    result = await mgr.create()
    assert isinstance(result, Worktree)
    # The record exposes ONLY the working-scope-relative path (public-safe).
    assert result.path == f".loopplane-worktrees/{result.id}"
    assert not Path(result.path).is_absolute()
    assert (tmp_path / ".loopplane-worktrees").exists()
    assert any("--detach" in call for call in runner.calls)


async def test_create_with_branch(tmp_path: Path) -> None:
    runner = FakeGitRunner()
    mgr = WorktreeManager(working_scope=tmp_path, runner=runner, max_worktrees=3)
    result = await mgr.create(branch="feature/x")
    assert isinstance(result, Worktree) and result.branch == "feature/x"
    assert any("-b" in call for call in runner.calls)


async def test_git_failure_is_contained(tmp_path: Path) -> None:
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(fail=True), max_worktrees=3
    )
    result = await mgr.create()  # never raises
    assert isinstance(result, str) and "failed" in result
    assert mgr.list_worktrees() == []


# --- US2: inspect & remove ----------------------------------------------------


async def test_list_and_remove(tmp_path: Path) -> None:
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(), max_worktrees=3
    )
    wt = await mgr.create()
    assert isinstance(wt, Worktree)
    assert [w.id for w in mgr.list_worktrees()] == [wt.id]
    assert await mgr.remove(wt.id) is None
    assert mgr.list_worktrees() == []


async def test_remove_unknown_id(tmp_path: Path) -> None:
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(), max_worktrees=3
    )
    err = await mgr.remove("nope")
    assert isinstance(err, str) and "unknown" in err


# --- US3: bounded, confined, lifecycle ----------------------------------------


async def test_count_cap_denies_create(tmp_path: Path) -> None:
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(), max_worktrees=1
    )
    first = await mgr.create()
    assert isinstance(first, Worktree)
    second = await mgr.create()
    assert isinstance(second, str) and "cap" in second
    assert len(mgr.list_worktrees()) == 1


def test_within_rejects_escaping_path(tmp_path: Path) -> None:
    scope = tmp_path.resolve()
    assert _within(scope / "a" / "b", scope)
    assert _within(scope, scope)
    assert not _within(scope.parent / "evil", scope)


async def test_cleanup_removes_all(tmp_path: Path) -> None:
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(), max_worktrees=3
    )
    await mgr.create()
    await mgr.create()
    assert len(mgr.list_worktrees()) == 2
    await mgr.cleanup()
    assert mgr.list_worktrees() == []


class _FailRemoveRunner:
    """Succeeds on add/prune; fails on ``worktree remove`` (the no-leak path)."""

    async def run(self, args: Sequence[str]) -> tuple[int, str, str]:
        if len(args) >= 2 and args[0] == "worktree" and args[1] == "add":
            Path(args[-1]).mkdir(parents=True, exist_ok=True)
            return (0, "", "")
        if len(args) >= 2 and args[0] == "worktree" and args[1] == "remove":
            return (1, "", "fatal: cannot remove")
        return (0, "", "")


async def test_failed_remove_does_not_leak_on_disk(tmp_path: Path) -> None:
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=_FailRemoveRunner(), max_worktrees=3
    )
    wt = await mgr.create()
    assert isinstance(wt, Worktree)
    wt_dir = tmp_path.resolve() / wt.path
    assert wt_dir.is_dir()
    err = await mgr.remove(wt.id)
    assert isinstance(err, str) and "failed" in err
    # Best-effort cleanup deleted the directory despite the git failure (no disk leak).
    assert not wt_dir.exists()
    assert mgr.list_worktrees() == []


# --- Adapter (Gateway surface) ------------------------------------------------


async def test_adapter_create_list_remove(tmp_path: Path) -> None:
    adapter = WorktreeToolsAdapter()
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(), max_worktrees=3
    )
    ctx = _ctx(mgr, tmp_path)
    (created,) = await _invoke(adapter, "worktree_create", {}, ctx)
    assert isinstance(created, TextBlock) and "worktree created" in created.text
    (listing,) = await _invoke(adapter, "worktree_list", {}, ctx)
    assert isinstance(listing, TextBlock)
    wt_id = mgr.list_worktrees()[0].id
    (removed,) = await _invoke(adapter, "worktree_remove", {"worktree_id": wt_id}, ctx)
    assert isinstance(removed, TextBlock) and "removed" in removed.text


async def test_adapter_create_error_surfaced(tmp_path: Path) -> None:
    adapter = WorktreeToolsAdapter()
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(fail=True), max_worktrees=3
    )
    (out,) = await _invoke(adapter, "worktree_create", {}, _ctx(mgr, tmp_path))
    assert isinstance(out, ErrorOutput)


async def test_adapter_errors_when_not_enabled(tmp_path: Path) -> None:
    adapter = WorktreeToolsAdapter()
    (err,) = await _invoke(adapter, "worktree_create", {}, _ctx(None, tmp_path))
    assert isinstance(err, ErrorOutput) and err.category == "validation"


async def test_output_is_public_safe_no_abspath_or_stderr(tmp_path: Path) -> None:
    # Public-safety (VII): adapter output + errors carry only the working-scope-relative
    # path + fixed messages — never the absolute scope path or raw git stderr.
    adapter = WorktreeToolsAdapter()
    scope_str = str(tmp_path.resolve())
    mgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(), max_worktrees=3
    )
    ctx = _ctx(mgr, tmp_path)
    (created,) = await _invoke(adapter, "worktree_create", {}, ctx)
    assert isinstance(created, TextBlock) and scope_str not in created.text
    (listing,) = await _invoke(adapter, "worktree_list", {}, ctx)
    assert isinstance(listing, TextBlock) and scope_str not in listing.text
    # A git failure surfaces a fixed message, not the runner's stderr / the scope path.
    failmgr = WorktreeManager(
        working_scope=tmp_path, runner=FakeGitRunner(fail=True), max_worktrees=3
    )
    (out,) = await _invoke(adapter, "worktree_create", {}, _ctx(failmgr, tmp_path))
    assert isinstance(out, ErrorOutput)
    assert "fatal:" not in out.message and scope_str not in out.message


def test_descriptors_shape() -> None:
    descriptors = {d.name: d for d in WorktreeToolsAdapter().describe()}
    assert set(descriptors) == {
        "worktree_create",
        "worktree_list",
        "worktree_remove",
    }
    assert descriptors["worktree_list"].read_only is True
    assert descriptors["worktree_create"].read_only is False


# --- Default-off assembly -----------------------------------------------------


class _StubModel:
    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        return
        yield  # pragma: no cover - never run; makes this an async generator


async def test_default_off_registers_no_worktree_tools() -> None:
    assembled = assemble(RuntimeConfig(model=_StubModel()))
    names = {d.name for d in assembled.gateway.descriptors()}
    assert "worktree_create" not in names


async def test_enabled_registers_the_three_tools() -> None:
    assembled = assemble(RuntimeConfig(model=_StubModel(), max_worktrees=2))
    names = {d.name for d in assembled.gateway.descriptors()}
    assert {"worktree_create", "worktree_list", "worktree_remove"} <= names


# --- Real git isolation (guarded) ---------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
async def test_real_git_worktree_isolation() -> None:
    # Use a system-temp repo, NOT pytest's tmp_path — on some setups the basetemp is
    # configured inside this project's own git tree, which makes the test repo a nested
    # repo and confuses real `git worktree`. A clean system-temp repo mirrors real use.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        scope = Path(tmp) / "repo"
        scope.mkdir()

        async def git(*args: str) -> None:
            await anyio.run_process(["git", "-C", str(scope), *args], check=False)

        await git("init")
        await git("config", "user.email", "t@example.com")
        await git("config", "user.name", "tester")
        (scope / "main.txt").write_text("main", encoding="utf-8")
        await git("add", "-A")
        await git("commit", "-m", "init")

        mgr = WorktreeManager(
            working_scope=scope, runner=AnyioGitRunner(scope), max_worktrees=2
        )
        result = await mgr.create()
        assert isinstance(result, Worktree), result
        # The record exposes a working-scope-RELATIVE path; reconstruct the absolute.
        assert result.path == f".loopplane-worktrees/{result.id}"
        wt_path = scope.resolve() / result.path
        assert wt_path.is_dir()
        assert wt_path.is_relative_to(scope.resolve())

        # A change inside the worktree does not touch the main working tree.
        (wt_path / "from_worktree.txt").write_text("isolated", encoding="utf-8")
        assert not (scope / "from_worktree.txt").exists()

        # Remove reports success (real git) and empties the registry.
        assert await mgr.remove(result.id) is None
        assert mgr.list_worktrees() == []
