# Quickstart / Validation: Worktree Isolation

See [contracts/worktree-tools.md](contracts/worktree-tools.md), [data-model.md](data-model.md),
and [research.md](research.md). Reuses the shell-execution seam + the working-scope confinement +
the 048/049/050 per-run-manager threading; **no task group** (synchronous git ops).

## Run the unit tests

```powershell
pytest tests/unit/test_worktree_isolation.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new worktree tests. With `max_worktrees = 0`
(default), behavior is byte-identical (no tools registered).

## Validation scenarios (mirror the acceptance scenarios)

1. **Isolated checkout** — in a throwaway `git init` repo, `worktree_create` makes an isolated
   checkout under `<scope>/.loopplane-worktrees/<id>`; a change inside it leaves the main working
   tree unmodified. (FR-002, SC-001)
2. **List / remove** — `worktree_list` shows id + path + branch; `worktree_remove` deletes +
   prunes; it no longer appears. (FR-004, SC-002)
3. **Confinement** — a requested path that would escape the working scope is rejected with a
   normalized error. (FR-003)
4. **Count cap** — exceeding `max_worktrees` → `worktree_create` denied (normalized error), nothing
   created. (FR-005)
5. **Non-git / git failure** — a non-git working scope or a failing git command → a normalized,
   public-safe error (no crash, no traceback). (FR-006)
6. **Unknown id** — `worktree_remove` on an unknown id → a clear normalized error. (FR-004, edge)
7. **Lifecycle cleanup** — managed worktrees are removed at the run/session scope exit
   (`cleanup()`); nothing leaks on disk. (FR-007)
8. **Default-off byte-identical** — `max_worktrees = 0` → `describe()` registers no worktree tools;
   existing runs unchanged. (FR-008, SC-004)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`,
`test_public_safety`) and the public-safety scan over the diff.
