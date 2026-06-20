"""Worktree isolation tools (spec 051): isolated git worktrees for agent work.

A :class:`WorktreeManager` creates / lists / removes managed git worktrees under a
managed area of the working scope (``<scope>/.loopplane-worktrees/<id>``), so the
001/002 working-scope confinement is **preserved** — a worktree never escapes the
scope. Git runs through the existing shell-execution path (``anyio.run_process``) via an
injectable :class:`GitRunner` (so tests are deterministic with a fake). There is **no
task group** (worktree ops are synchronous git/filesystem operations); the per-run
manager is built per-session from the working scope.

SAFE + additive: bounded (a count cap), contained (a non-git scope / git failure / bad
input is a normalized, public-safe error, never a raise), and lifecycle-bound
(``cleanup()`` removes the managed worktrees at the run/session scope exit). Reached via
``RunContext.worktrees``. Gateway-only (V); no event-schema / content-model change; no
new dependency. Registered only when ``max_worktrees >= 1`` (0 = off, byte-identical).
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anyio

from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock

_MANAGED_DIR = ".loopplane-worktrees"


class GitRunner(Protocol):
    """An async runner for a git argv within the working scope (so tests inject a fake).

    Returns ``(exit_code, stdout, stderr)``; an exit code != 0 signals failure.
    """

    async def run(self, args: Sequence[str]) -> tuple[int, str, str]: ...


# A bounded time for any single git invocation, so a hung git (lock contention, a
# blocked filesystem, a hook) can never block a turn or teardown indefinitely.
_GIT_TIMEOUT_SECONDS = 30.0


class AnyioGitRunner:
    """The production runner: ``git -C <scope> …`` via ``anyio.run_process``.

    Each call is **time-bounded** (``move_on_after``): a hung git is cancelled (the
    subprocess is terminated) and reported as a normalized failure (exit 124), never a
    hang. Public-safe: every caller discards the returned stderr — the manager surfaces
    only fixed messages, never raw git stderr.
    """

    def __init__(
        self, working_scope: Path, *, timeout: float = _GIT_TIMEOUT_SECONDS
    ) -> None:
        self._scope = working_scope
        self._timeout = timeout

    async def run(self, args: Sequence[str]) -> tuple[int, str, str]:
        try:
            with anyio.move_on_after(self._timeout):
                completed = await anyio.run_process(
                    ["git", "-C", str(self._scope), *args], check=False
                )
                return (
                    completed.returncode,
                    completed.stdout.decode("utf-8", errors="replace"),
                    completed.stderr.decode("utf-8", errors="replace"),
                )
        except OSError:  # git missing / cannot spawn
            return (127, "", "")
        # Reached only when the call timed out (the subprocess was terminated).
        return (124, "", "")


@dataclass
class Worktree:
    """One managed worktree's registry record (metadata only; no payloads)."""

    id: str
    path: str
    branch: str | None = None


def _within(path: Path, scope: Path) -> bool:
    """Whether ``path`` is inside ``scope`` (the working-scope confinement)."""

    return path == scope or path.is_relative_to(scope)


class WorktreeManager:
    """Owns the registry + working scope + git runner for one run/session (spec 051).

    No task group — git ops are synchronous and awaited directly.
    """

    def __init__(
        self, *, working_scope: Path, runner: GitRunner, max_worktrees: int
    ) -> None:
        self._scope = working_scope.resolve()
        self._runner = runner
        self._max = max_worktrees
        self._worktrees: dict[str, Worktree] = {}
        # The absolute path per worktree, kept INTERNAL (never surfaced) so git ops use
        # exactly the path created (no recompute drift on Windows). The public record
        # exposes only the working-scope-relative path (Constitution VII).
        self._abspaths: dict[str, Path] = {}

    def _managed_root(self) -> Path:
        return self._scope / _MANAGED_DIR

    async def create(self, *, branch: str | None = None) -> Worktree | str:
        """Create an isolated worktree under the managed area; a ``str`` on failure
        (count cap / out-of-scope / git error) — never raises."""

        if len(self._worktrees) >= self._max:
            return "worktree count cap reached; refusing to create a worktree"
        worktree_id = uuid.uuid4().hex
        path = (self._managed_root() / worktree_id).resolve()
        if not _within(path, self._scope):
            return "refusing to create a worktree outside the working scope"
        try:
            self._managed_root().mkdir(parents=True, exist_ok=True)
        except OSError:
            return "cannot prepare the worktree area"
        args = ["worktree", "add"]
        if branch:
            args += ["-b", branch]
        else:
            args.append("--detach")
        args.append(str(path))
        code, _out, _err = await self._runner.run(args)
        if code != 0:
            return "git worktree add failed"
        # Expose only the working-scope-RELATIVE path (public-safe, Constitution VII):
        # the absolute path stays internal and is recomputed for git ops in remove().
        rel_path = f"{_MANAGED_DIR}/{worktree_id}"
        record = Worktree(id=worktree_id, path=rel_path, branch=branch)
        self._worktrees[worktree_id] = record
        self._abspaths[worktree_id] = path
        return record

    def list_worktrees(self) -> list[Worktree]:
        return list(self._worktrees.values())

    async def remove(self, worktree_id: str) -> str | None:
        """Remove a managed worktree; ``None`` on success, a ``str`` error otherwise.

        Uses the internal absolute path (the record exposes only a relative one); on a
        git failure, best-effort deletes the directory so it never leaks on disk."""

        if worktree_id not in self._worktrees:
            return f"unknown worktree id: {worktree_id}"
        abspath = self._abspaths.get(worktree_id, self._managed_root() / worktree_id)
        code, _out, _err = await self._runner.run(
            ["worktree", "remove", "--force", str(abspath)]
        )
        if code != 0:
            # Best-effort: delete the directory so a failed remove never leaks on disk.
            shutil.rmtree(abspath, ignore_errors=True)
        self._worktrees.pop(worktree_id, None)
        self._abspaths.pop(worktree_id, None)
        await self._runner.run(["worktree", "prune"])
        if code != 0:
            return "git worktree remove failed"
        return None

    async def cleanup(self) -> None:
        """Remove every managed worktree at the run/session scope exit (best-effort,
        so a git/IO failure never breaks teardown)."""

        for worktree_id in list(self._worktrees):
            try:
                # Shielded so teardown still runs (and cannot hang — the git runner caps
                # each call) even when the surrounding scope is being cancelled.
                with anyio.CancelScope(shield=True):
                    await self.remove(worktree_id)
            except Exception:  # noqa: BLE001 - cleanup is best-effort
                self._worktrees.pop(worktree_id, None)


def make_worktree_manager(
    working_scope: Path, *, runner: GitRunner | None = None, max_worktrees: int
) -> WorktreeManager:
    """Build a manager bound to a session's working scope (the production git runner is
    used unless a runner is injected, e.g. by a test)."""

    return WorktreeManager(
        working_scope=working_scope,
        runner=runner or AnyioGitRunner(working_scope),
        max_worktrees=max_worktrees,
    )


def make_worktree_manager_factory(
    max_worktrees: int,
) -> Callable[[Path], WorktreeManager]:
    """Bind the count cap into a closure the scope owner calls with the session's
    working scope, returned to the host assembly so the controller can hold an opaque
    factory and stay tool-agnostic (Constitution V)."""

    def factory(working_scope: Path) -> WorktreeManager:
        return make_worktree_manager(working_scope, max_worktrees=max_worktrees)

    return factory


_DESCRIPTORS = [
    ToolDescriptor(
        name="worktree_create",
        description=(
            "Create an isolated git worktree (a separate checkout under a managed area "
            "of the working scope) so changes can be made without disturbing the main "
            "working tree. Returns the worktree id + path; optionally pass 'branch' to "
            "create + check out a new branch (otherwise the worktree is detached at "
            "HEAD). Inspect with worktree_list; clean up with worktree_remove."
        ),
        input_schema={
            "type": "object",
            "properties": {"branch": {"type": "string"}},
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="worktree_list",
        description="List this run's managed worktrees with their path and branch.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="worktree_remove",
        description="Remove a managed worktree by id (deletes the checkout + prunes).",
        input_schema={
            "type": "object",
            "properties": {"worktree_id": {"type": "string"}},
            "required": ["worktree_id"],
            "additionalProperties": False,
        },
    ),
]


class WorktreeToolsAdapter:
    """A Tool Gateway adapter exposing the three worktree tools (spec 051).

    Stateless: the per-run state lives in the ``WorktreeManager`` reached via
    ``RunContext.worktrees``.
    """

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(_DESCRIPTORS)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        manager = context.worktrees
        if manager is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message="worktrees are not enabled for this run",
            )
            return
        if name == "worktree_create":
            raw_branch = call_input.get("branch")
            branch = raw_branch if isinstance(raw_branch, str) and raw_branch else None
            result = await manager.create(branch=branch)
            if isinstance(result, str):
                yield ErrorOutput(category=ErrorCategory.VALIDATION, message=result)
                return
            yield TextBlock(text=f"worktree created: {result.id} at {result.path}")
            return
        if name == "worktree_list":
            worktrees = manager.list_worktrees()
            if not worktrees:
                yield TextBlock(text="no worktrees")
                return
            lines = [
                f"{w.id}: {w.path}" + (f" ({w.branch})" if w.branch else "")
                for w in worktrees
            ]
            yield TextBlock(text="\n".join(lines))
            return
        # worktree_remove
        worktree_id = str(call_input["worktree_id"])
        error = await manager.remove(worktree_id)
        if error is not None:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=error)
            return
        yield TextBlock(text=f"worktree removed: {worktree_id}")

    async def shutdown(self) -> None:
        return None
