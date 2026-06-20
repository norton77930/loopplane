# Research: Worktree Isolation

The Tier-2 boundary question (confinement + mechanism) is resolved **additively** — no new ADR, no
contract break (see plan.md "Boundary review"). Decisions below; no open `NEEDS CLARIFICATION`.

## Decision 1 — A per-run WorktreeManager (no task group)

**Decision**: A per-run `WorktreeManager` holds a registry (`worktree_id → path + branch`), the
per-run cap, the working scope, and an injectable git runner. `worktree_create` / `_list` /
`_remove` run synchronous git ops. **No `anyio` task group** is needed (unlike 048/049/050) —
worktree operations complete synchronously; there is no long-running concurrent work.

**Rationale**: Reuse-first; the simplest manager that satisfies the FRs. Filesystem/git ops are
synchronous, so the supervisor-task-group machinery from 048-050 is unnecessary here.

**Alternatives considered**: running each worktree op in a task group (rejected — needless
complexity; ops are synchronous).

## Decision 2 — Worktrees under a managed area of the working scope (confinement preserved)

**Decision**: Managed worktrees live under `<working_scope>/.loopplane-worktrees/<id>`. The
manager rejects any path that would escape the working scope. The 001/002 working-scope
confinement is therefore **preserved, not changed** — no boundary crossing, no ADR.

**Rationale**: Git worktrees are normally siblings of the main tree, which would escape the working
scope. Placing them under a managed dot-dir of the scope keeps the existing confinement invariant
intact while still giving an isolated checkout.

**Alternatives considered**: worktrees as siblings outside the scope (rejected — breaks the
working-scope confinement, a 001/002 contract change requiring an ADR + maintainer approval).

## Decision 3 — Git via an injectable runner (deterministic offline tests)

**Decision**: The manager runs git through an injectable runner (production: the existing
shell-execution path running `git -C <scope> worktree add/list/remove …`; tests: a throwaway
`git init` repo fixture, or a fake runner asserting the commands). No new library dependency.

**Rationale**: Reuses the `run_command` shell seam; an injectable runner keeps tests deterministic
+ offline (no network; git only when the feature is exercised).

## Decision 4 — Threading (the 048/049/050 pattern; controller tool-agnostic)

**Decision**: A neutral `WorktreeManager` Protocol in `loopplane.context`; the controller /
dispatcher reference it (NOT `loopplane.tools`). The concrete manager is produced by an opaque
factory built in `host/assembly` and threaded as `RunContext.worktrees` via
`RuntimeController.drive(..., worktree_manager=None)`. The Dispatcher / one-shot `host.run` build
it + call `cleanup()` at scope exit (remove managed worktrees).

**Rationale**: The proven 048/049/050 wiring keeps the boundary audit green.

## Decision 5 — Default-off, bounded, contained, lifecycle (cleanup)

**Decision**: `RuntimeConfig.max_worktrees` (default `0`) gates + caps it: `0` → no manager, no
tools, byte-identical. Exceeding the cap → `worktree_create` denied (normalized error), nothing
created. A non-git scope / git failure / bad input / out-of-scope path → a normalized, public-safe
error (never a raise). At the run/session scope exit, the manager's `cleanup()` removes all managed
worktrees (directories + git prune); nothing leaks on disk.

**Rationale**: Mirrors the proven 048/049/050 default-off + fail-safe + lifecycle posture (with
`cleanup()` in place of `cancel_all()`).

## Decision 6 — Tool surface

**Decision**: Three Gateway tools — `worktree_create([branch])`, `worktree_list()`,
`worktree_remove(worktree_id)`. `create` returns the id + path; `list` reports id + path + branch;
`remove` deletes + prunes; an unknown id → a normalized error.

**Rationale**: Matches the reference harness's enter/list/exit surface, mapped to create/list/remove.

**Alternatives considered**: auto-merge/PR of worktree changes back to the main branch (deferred —
out of scope).
