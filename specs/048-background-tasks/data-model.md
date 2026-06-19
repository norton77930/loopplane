# Data Model: Background Task Tools

Per [ADR 0002](../../docs/adr/0002-background-task-execution.md). No new content block or
event; in-memory per-run state only.

## BackgroundTaskSupervisor (new)

Owns the concurrency scope + registry for one run/session.

| Member | Type | Notes |
| ------ | ---- | ----- |
| task group | `anyio` task group | The concurrency scope; created by the scope owner (Dispatcher / one-shot `host.run`). |
| registry | `dict[str, BackgroundTask]` | `task_id → task record`. |
| `max_tasks` | int | The per-run count cap (`RuntimeConfig.max_background_tasks`). |
| child factory | callable | Builds a depth-incremented child run (reuses the 043 factory). |

Methods: `create(instruction, allowed_tools=None) -> task_id` (start_soon a child run; deny
at the count/depth cap), `get(task_id)`, `list()`, `stop(task_id)` (cancel), `output(task_id)`.

## BackgroundTask (registry record)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | str | Stable task id. |
| `status` | enum | `running` → `completed` / `failed` / `stopped`. |
| `result` | `str \| None` | The child's final text when `completed`; a public-safe message when `failed`; `None` while `running`. |
| (cancel handle) | internal | Used by `stop`. |

## RunContext.background_tasks (new optional field)

- `background_tasks: BackgroundTaskSupervisor | None = None` (additive; default `None`).
- Set only in `RuntimeController.drive()` from the optional `background_supervisor` param
  (the 043 `subagent_depth` threading pattern); per-run, never process-global.

## RuntimeConfig.max_background_tasks (new gate)

- `max_background_tasks: int = 0` (default 0 = off → no supervisor, no tools, byte-identical).
- `> 0` enables the feature and caps the per-run task count; coerced/validated in
  `from_mapping`/`validate_config` (a non-negative int), carries no secret.

## Rules (from FRs + ADR 0002)

| Rule | Source |
| ---- | ------ |
| 5 Gateway tools: create/get/list/stop/output | FR-001 |
| `create` returns an id without blocking on completion | FR-002, D1 |
| Result retrievable by id; `list` enumerates run tasks (metadata + requested result) | FR-003 |
| `stop` cancels a running task; no-op/clear error otherwise | FR-004 |
| Count cap + 043 depth cap; exceed → deny, no task started | FR-005, D5 |
| Failure contained → `failed` status, never a raise | FR-006, D5 |
| Pending tasks cancelled at run/session end (no leak) | FR-007, D6 |
| Default-off byte-identical (`max_background_tasks = 0`) | FR-008, D4 |
| No event-schema/content-model change | FR-009, D6 |
