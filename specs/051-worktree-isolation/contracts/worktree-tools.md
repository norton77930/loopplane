# Contract: Worktree Tools

Three Gateway tools backed by a per-run `WorktreeManager` (a registry + an injectable git runner;
no task group). Registered only when `RuntimeConfig.max_worktrees > 0` (default 0 → none;
byte-identical). Worktrees live under `<working_scope>/.loopplane-worktrees/` (the working-scope
confinement is preserved).

## Tools

| Tool | Input | Result |
| ---- | ----- | ------ |
| `worktree_create` | optional `branch: str` | The worktree's id + path (an isolated checkout under the managed area). |
| `worktree_list` | — | The run's managed worktrees: id + path + branch. |
| `worktree_remove` | `worktree_id: str` | Removes the checkout + prunes git metadata; confirms. |

- `worktree_create` / `worktree_remove` are `read_only=False`; `worktree_list` is `read_only=True`.
  All `concurrency_safe=False` (they touch the registry + the filesystem).

## Behavior

| Case | Result |
| ---- | ------ |
| `worktree_create` (under the cap, git scope) | `git worktree add` under `<scope>/.loopplane-worktrees/<id>`; return id + path; the main working tree is unchanged. |
| `worktree_create` at the count cap | `ErrorOutput` (normalized); **no** worktree created. |
| working scope is not a git repo / git unavailable / git fails | A normalized, public-safe error; no crash. |
| a requested path would escape the working scope | Rejected with a normalized error (confinement preserved). |
| `worktree_list` | The managed worktrees (id + path + branch); metadata only. |
| `worktree_remove` (known id) | `git worktree remove` + prune; the checkout is gone; confirm. |
| `worktree_remove`/`create` on an unknown id / bad input | A clear normalized error (no crash). |
| Run/session ends with managed worktrees | `cleanup()` removes them (directories + git prune) at scope exit (no leak). |
| Feature disabled (`max_worktrees = 0`) | No tools registered; byte-identical to today. |

## Invariants

- Reachable only through the Tool Gateway (V); git runs via the existing shell-execution seam
  within the working scope.
- **Working-scope confinement preserved** (001/002): worktrees live under a managed area of the
  scope; a path escaping the scope is rejected. No boundary crossing, no ADR.
- No event-schema / `SCHEMA_VERSION` / content-model change (VI); no new dependency.
- Bounded (count cap) and contained (git/IO failure → normalized error, never a raise).
- Lifecycle-bound: managed worktrees cleaned up at run/session end (`cleanup()`).
- Default-off (`max_worktrees = 0`) is byte-identical to pre-051 (proven by a test).
- No bundled secret; normalized errors leak no internals/paths beyond the metadata-safe id+path
  (VII). The controller/dispatcher reference only the neutral `WorktreeManager` Protocol (the
  boundary audit).
