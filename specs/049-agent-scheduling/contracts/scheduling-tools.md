# Contract: Agent Scheduling Tools

Four Gateway tools backed by a per-run `ScheduleSupervisor` (reusing the unit-048 supervisor +
ADR 0002 + the unit-004 interval concepts + an injectable `Sleeper`). Registered only when
`RuntimeConfig.max_schedules > 0` (default 0 → none; byte-identical).

## Tools

| Tool | Input | Result |
| ---- | ----- | ------ |
| `schedule_create` | `instruction: str`; exactly one of `delay_seconds: number>0` / `interval_seconds: number>0`; optional `allowed_tools: list[str]` | A schedule id (returned immediately, non-blocking). |
| `schedule_get` | `schedule_id: str` | The schedule's cadence + status + occurrence count (metadata only). |
| `schedule_list` | — | The run's schedules: ids + cadence + status. |
| `schedule_cancel` | `schedule_id: str` | Cancels the schedule (stops further firings); reports the resulting status. |

- `schedule_create` / `schedule_cancel` are `read_only=False`; `schedule_get` / `schedule_list`
  are `read_only=True`. All `concurrency_safe=False` (they touch the registry).

## Behavior

| Case | Result |
| ---- | ------ |
| `schedule_create` (under caps, valid cadence) | Start a timer task in the supervisor scope; return an id without blocking. |
| Delay elapses (one-shot) | Fire one bounded child run; status → `completed`; `last_result` set. |
| Interval elapses (recurring) | Fire a bounded child run each period; `occurrences` increments; stays `active`. |
| At the count cap / 043 depth cap | `ErrorOutput` (normalized); **no** schedule started. |
| Non-positive / both / neither delay+interval | `ErrorOutput` (normalized); nothing scheduled. |
| An occurrence's child raises / over-runs / empty | Recorded on that occurrence (public-safe `last_result`); the schedule + parent continue (no raise across the Gateway). |
| `schedule_cancel` on an active schedule | Cancel its timer; status → `cancelled`; no further firings. |
| `get`/`cancel` on an unknown id | A clear normalized error (no crash). |
| Run/session ends with active schedules | Timers cancelled at the supervisor scope exit (no leak). |
| Feature disabled (`max_schedules = 0`) | No tools registered; byte-identical to today. |

## Invariants

- Reachable only through the Tool Gateway (V); child runs reuse the 043/048 seam.
- No event-schema / `SCHEMA_VERSION` / content-model change (VI); child events captured, never
  on the parent bus. No unit-004 `Clock` contract change. No new ADR (reuses ADR 0002).
- Bounded (count + 043 depth), contained (failures → status), lifecycle-bound (cancel at exit).
- Deterministic in tests via the injectable `Sleeper` (no real sleeping).
- Default-off (`max_schedules = 0`) is byte-identical to pre-049 (proven by a test).
- No bundled secret; normalized errors leak no internals (VII).
