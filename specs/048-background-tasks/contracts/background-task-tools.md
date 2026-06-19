# Contract: Background Task Tools

Five Gateway tools backed by a per-run `BackgroundTaskSupervisor`
([ADR 0002](../../docs/adr/0002-background-task-execution.md)). Registered only when
`RuntimeConfig.max_background_tasks > 0` (default 0 → none; byte-identical).

## Tools

| Tool | Input | Result |
| ---- | ----- | ------ |
| `task_create` | `instruction: str`, optional `allowed_tools: list[str]` | A task id (returned immediately, non-blocking). |
| `task_get` | `task_id: str` | The task's status (and result if completed) — metadata only. |
| `task_list` | — | The run's tasks: ids + statuses. |
| `task_stop` | `task_id: str` | Cancels a running task; reports the resulting status. |
| `task_output` | `task_id: str` | The child's final text if `completed`, else the current status. |

- `task_create` / `task_stop` are `read_only=False`; `task_get` / `task_list` /
  `task_output` are `read_only=True`. All `concurrency_safe=False` (they touch the registry).

## Behavior

| Case | Result |
| ---- | ------ |
| `task_create` (under caps) | Start a concurrent child run (043 `run_loop`); return an id without blocking. |
| `task_create` at the count cap or 043 depth cap | `ErrorOutput` (normalized); **no** task started. |
| Child completes | Status `completed`; `task_output` returns the child's final text. |
| Child raises / over-runs / empty | Status `failed` with a fixed public-safe message; parent unaffected (no raise across the Gateway). |
| `task_stop` on a running task | Cancel it; status `stopped`. |
| `task_get`/`output`/`stop` on an unknown id | A clear normalized error (no crash). |
| `task_output` before completion | Returns the current status (e.g., `running`); does not block. |
| Run/session ends with tasks pending | Pending tasks cancelled at the supervisor scope exit (no leak). |
| Feature disabled (`max_background_tasks = 0`) | No tools registered; byte-identical to today. |

## Invariants

- Reachable only through the Tool Gateway (V); child runs reuse the 043 seam.
- No event-schema / `SCHEMA_VERSION` / content-model change (VI); child events captured,
  never on the parent bus.
- Bounded (count + 043 depth caps) and contained (failures → status, never a raise).
- Default-off (`max_background_tasks = 0`) is byte-identical to pre-048 (proven by a test).
- No bundled secret; normalized errors leak no internals (VII).
