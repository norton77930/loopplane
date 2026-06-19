# Data Model: Agent Scheduling Tools

Additive; in-memory per-run state; reuses the 043/048 child run + ADR 0002 concurrency. No new
content block or event. Unit 004's `Clock` is unchanged.

## Sleeper (new seam)

An async "wait" abstraction so interval timing is deterministic in tests.

| Member | Type | Notes |
| ------ | ---- | ----- |
| `sleep` | `async (seconds: float) -> None` | Production: `anyio.sleep`. Tests: a controllable fake the test advances (no real sleep). |

## ScheduleSupervisor (new)

Owns the timer scope + registry for one run/session.

| Member | Type | Notes |
| ------ | ---- | ----- |
| task group | `anyio` task group | The unit-048 supervisor scope (ADR 0002); hosts each schedule's timer task. |
| registry | `dict[str, Schedule]` | `schedule_id → schedule record`. |
| `max_schedules` | int | Per-run count cap (`RuntimeConfig.max_schedules`). |
| sleeper | `Sleeper` | Injectable timing. |
| run_child | callable | Bounded child run (reuses the 043/048 `run_child`). |

Methods: `create(instruction, *, delay_seconds=None, interval_seconds=None, allowed_tools=None,
child_depth, working_scope) -> schedule_id | None` (deny at the count/depth cap or on a
non-positive cadence), `get(id)`, `list_schedules()`, `cancel(id)`, `cancel_all()` (scope exit).

## Schedule (registry record)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | str | Stable schedule id. |
| `cadence` | str | `delay:<n>` or `interval:<n>` (metadata). |
| `status` | enum | `active` → `cancelled` / `completed` (a one-shot delay → `completed` after it fires). |
| `occurrences` | int | How many times it has fired. |
| `last_result` | `str \| None` | The last occurrence's outcome (public-safe; failures → a fixed message). |
| (cancel handle) | internal | The timer task's cancel scope; used by `cancel`. |

## RunContext.schedules (new optional field)

- `schedules: ScheduleSupervisor | None = None` (additive; default `None`; per-run).
- A neutral `ScheduleSupervisor` Protocol is declared in `loopplane.context` (the 048
  `BackgroundSupervisor` pattern) so the controller/loop never import the tools layer.
- Set only in `RuntimeController.drive()` from the optional `schedule_supervisor` param.

## RuntimeConfig.max_schedules (new gate)

- `max_schedules: int = 0` (default 0 = off → no supervisor, no tools, byte-identical).
- `> 0` enables + caps the per-run schedule count; validated as a non-negative int; no secret.

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| 4 Gateway tools: create/get/list/cancel | FR-001 |
| `create` returns a handle without blocking; firings are async | FR-002 |
| Reuse 004 interval concepts + an injectable clock; deterministic tests (no real sleep) | FR-003 |
| list/get metadata-only; cancel stops firings; unknown id → clear error | FR-004 |
| Count cap + 043 depth cap; non-positive cadence → deny | FR-005 |
| Failure contained → occurrence status, never a raise | FR-006 |
| Active schedules cancelled at run/session end (no leak) | FR-007 |
| Default-off byte-identical (`max_schedules = 0`) | FR-008 |
| Concurrency/clock/lifecycle additive: reuse 048+ADR 0002, no 004 contract change, no new ADR | FR-009 |
