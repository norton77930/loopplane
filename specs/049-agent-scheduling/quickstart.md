# Quickstart / Validation: Agent Scheduling Tools

See [contracts/scheduling-tools.md](contracts/scheduling-tools.md),
[data-model.md](data-model.md), and [research.md](research.md). Reuses the unit-048 supervisor
(ADR 0002) + the unit-004 interval concepts + an injectable `Sleeper`.

## Run the unit tests

```powershell
pytest tests/unit/test_agent_scheduling.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new scheduling tests. With `max_schedules = 0`
(default), behavior is byte-identical (no tools registered).

## Validation scenarios (mirror the acceptance scenarios)

1. **Non-blocking create** — with a supervisor + a fake `Sleeper`, `schedule_create(interval)`
   returns an id without awaiting a firing. (FR-002, SC-001)
2. **Interval firing (deterministic)** — advancing the fake sleeper N periods fires the bounded
   child run N times; `occurrences` reflects it. (FR-003, SC-001)
3. **One-shot delay** — a delay schedule fires once then → `completed`. (FR-003)
4. **Inspect/cancel** — `schedule_get`/`schedule_list` show cadence + status; `schedule_cancel`
   stops further firings → `cancelled`; unknown id → clear error. (FR-004, SC-002)
5. **Count cap** — exceeding `max_schedules` → denied (normalized error), nothing scheduled. (FR-005)
6. **Depth cap** — the 043 `subagent_depth` cap blocks scheduled child runs from nesting without
   bound. (FR-005)
7. **Bad cadence** — non-positive / both / neither delay+interval → normalized error. (FR-005, edge)
8. **Containment** — an occurrence whose child raises → recorded on that occurrence; the
   schedule + parent continue (no raise across the Gateway). (FR-006)
9. **Lifecycle** — active schedules' timers are cancelled when the supervisor scope exits (no
   leak). (FR-007)
10. **Default-off byte-identical** — `max_schedules = 0` → `describe()` registers no scheduling
    tools; existing runs unchanged. (FR-008, SC-004)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`,
`test_public_safety`) and the public-safety scan over the diff.
