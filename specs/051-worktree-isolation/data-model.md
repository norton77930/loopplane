# Data Model: Worktree Isolation

Additive; in-memory per-run registry + on-disk managed git checkouts (removed at scope exit). No
new content block or event. No task group (synchronous ops).

## GitRunner (new seam)

An injectable runner for git commands so tests are deterministic + offline.

| Member | Type | Notes |
| ------ | ---- | ----- |
| `run` | `async (args: Sequence[str]) -> (exit_code, stdout, stderr)` | Production: the existing shell-execution path running `git -C <scope> …`. Tests: a throwaway repo / a fake. |

## WorktreeManager (new)

Owns the registry + cap + working scope + runner for one run/session.

| Member | Type | Notes |
| ------ | ---- | ----- |
| working_scope | `Path` | The run's working scope; the managed area is `<scope>/.loopplane-worktrees/`. |
| registry | `dict[str, Worktree]` | `worktree_id → worktree record`. |
| `max_worktrees` | int | Per-run cap (`RuntimeConfig.max_worktrees`). |
| runner | `GitRunner` | Injectable git runner. |

Methods: `create(branch=None) -> Worktree | error` (deny at the cap; `git worktree add` under the
managed area; reject escaping paths), `list_worktrees() -> list[Worktree]`, `remove(worktree_id)
-> bool | error` (`git worktree remove` + prune), `cleanup()` (remove all managed worktrees at
scope exit).

## Worktree (registry record)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | str | Stable worktree id. |
| `path` | str | The checkout path (under `<scope>/.loopplane-worktrees/<id>`, within the working scope). |
| `branch` | `str \| None` | The branch the worktree is on (or detached). |

## RunContext.worktrees (new optional field)

- `worktrees: WorktreeManager | None = None` (additive; default `None`; per-run).
- A neutral `WorktreeManager` Protocol is declared in `loopplane.context` (the 048/049/050
  pattern) so the controller/loop never import the tools layer.
- Set only in `RuntimeController.drive()` from the optional `worktree_manager` param.

## RuntimeConfig.max_worktrees (new gate)

- `max_worktrees: int = 0` (default 0 = off → no manager, no tools, byte-identical).
- `> 0` enables + caps the per-run worktree count; validated as a non-negative int; no secret.

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| 3 Gateway tools: create/list/remove | FR-001 |
| created worktree is an isolated checkout; main tree unchanged | FR-002 |
| worktrees under a managed area of the working scope; escaping path rejected | FR-003 |
| list metadata-only; remove deletes + prunes; unknown id → clear error | FR-004 |
| count cap; exceed → deny, nothing created | FR-005 |
| failure (non-git / git error / bad input) contained → normalized error, never a raise | FR-006 |
| managed worktrees cleaned up at run/session end (`cleanup()`; no leak) | FR-007 |
| default-off byte-identical (`max_worktrees = 0`) | FR-008 |
| reuse the shell-exec seam + working-scope + the 048/049/050 threading; no new dep / no ADR | FR-009 |
