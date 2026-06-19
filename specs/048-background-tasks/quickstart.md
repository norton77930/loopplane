# Quickstart / Validation: Background Task Tools

See [contracts/background-task-tools.md](contracts/background-task-tools.md),
[data-model.md](data-model.md), and [ADR 0002](../../docs/adr/0002-background-task-execution.md).

## Run the unit tests

```powershell
pytest tests/unit/test_background_tasks.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new background-task tests. With
`max_background_tasks = 0` (default), behavior is byte-identical (no tools registered).

## Validation scenarios (mirror the acceptance scenarios)

1. **Non-blocking create** — with a supervisor (scripted child model), `task_create` returns
   an id without awaiting completion; the task then completes and `task_output` returns its
   result. (FR-002, SC-001)
2. **Status lifecycle** — `task_get` shows `running` → `completed`; `task_list` includes it. (FR-003)
3. **Stop** — `task_stop` on a running task → `stopped`. (FR-004)
4. **Count cap** — exceeding `max_background_tasks` → `task_create` denied (normalized error),
   no task started. (FR-005)
5. **Depth cap** — the 043 `subagent_depth` cap blocks a background task from nesting without
   bound. (FR-005)
6. **Containment** — a child whose run raises → status `failed` (public-safe), parent
   unaffected; no raise across the Gateway. (FR-006)
7. **Lifecycle** — pending tasks are cancelled when the supervisor scope exits (no leak). (FR-007)
8. **Default-off byte-identical** — `max_background_tasks = 0` → `describe()` registers no
   background-task tools; existing runs unchanged. (FR-008, SC-004)
9. **Unknown id** — `task_get`/`output`/`stop` on an unknown id → clear normalized error. (edge)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the public-safety scan (no private paths / secrets in the diff).
