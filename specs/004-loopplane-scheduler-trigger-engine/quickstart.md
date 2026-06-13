# Quickstart & Validation Guide: Scheduler & Trigger Engine

**Feature**: `004-loopplane-scheduler-trigger-engine` | **Spec**: [spec.md](./spec.md) |
**Plan**: [plan.md](./plan.md)

Runnable scenarios that prove the Scheduler works end-to-end through the **public** surface — starting
every Loop Run via the Phase-3 `run_loop` and driving time with a deterministic `VirtualClock`. This is a
validation/run guide; implementation lives in `tasks.md`. Every scenario is credential-free and uses no
real sleeping (NFR-002, SC-008).

## Prerequisites

- Phases 1–3 merged (`loopplane.engineering` importable, incl. `run_loop`).
- Dev install: `pip install -e .[dev]` (pytest + anyio).
- The scheduling tests reuse the Phase-3 loop helpers (scripted host, scripted validator).

## Run the validation suite

```powershell
pytest tests/unit/test_scheduling_core.py `
       tests/integration/test_scheduler_us1.py `
       tests/integration/test_scheduler_us2.py `
       tests/integration/test_scheduler_us3.py `
       tests/integration/test_scheduler_us4.py `
       tests/integration/test_scheduler_us5.py `
       tests/contract/test_scheduling_boundary.py
```

## Minimal example (design intent)

```python
from loopplane.scheduling import Scheduler, VirtualClock

clock = VirtualClock()
scheduler = Scheduler(clock)
scheduler.register_interval("nightly", my_definition, interval_seconds=60.0)

clock.advance(180.0)            # 3 periods
outcomes = await scheduler.poll()
assert len(outcomes) == 3       # fired once per elapsed period (default policy)
```

## Scenario → requirement map

| # | Scenario | Asserts | Maps to |
|---|---|---|---|
| 1 | Register + start a manual trigger | exactly one `run_loop`; Trigger State records the fire | US1, SC-001, FR-020 |
| 2 | Unknown trigger id | `SchedulerError`; no Loop Run started | US1.3, FR-004 |
| 3 | Boundary audit | the run started only through `run_loop`; no Phase-1/2/3 internal called | US1.4, SC-002, NFR-003 |
| 4 | Interval over a virtual clock | period P, advance 3P ⇒ 3 fires at the due ticks | US2.1, SC-003 |
| 5 | Interval next-due advances | each fire advances next-due by one period, fire_count += 1 | US2.2, FR-031 |
| 6 | Interval determinism | identical clock scripts ⇒ identical firing sequences | US2.3, SC-008, NFR-002 |
| 7 | start_immediately | fires at t0 then every period | US2.4, FR-032 |
| 8 | Condition false | predicate false ⇒ no run | US3.1, FR-040 |
| 9 | Condition becomes true | rising edge ⇒ exactly one run | US3.2, SC-004 |
| 10 | Condition edge vs level | edge fires once across a true plateau; level fires each poll | US3.3, FR-041 |
| 11 | Condition predicate raises | `condition_error` event; no spurious run; scheduler continues | US3.4, FR-042 |
| 12 | Missed-run: skip | clock jumps K ticks ⇒ 1 run; next-due past the jump | US4.1, SC-005 |
| 13 | Missed-run: catch-up-once | 1 make-up run; missed-tick count recorded | US4.2, SC-005 |
| 14 | Missed-run: coalesce | 1 collapsed run; next-due re-based | US4.3, SC-005 |
| 15 | Trigger State reconstruction | `reconstruct_states(events)` rebuilds state from the stream alone | US4.4, SC-006, FR-052 |
| 16 | Pause / resume | paused trigger fires nothing; resumes after resume | US5.1, FR-071 |
| 17 | Serialization | two due triggers never run concurrently; one-in-flight | US5.2, SC-007, FR-072 |
| 18 | Drain | in-flight run finishes; no new run starts; clean stop | US5.3, FR-070 |
| 19 | Stopped scheduler | a due trigger starts nothing; next-due unchanged | US5.4, FR-071 |
| 20 | Observation parity | observation off vs on ⇒ identical decisions + outcomes | SC-009, NFR-005 |
| 21 | Public-safety scan | committed Phase-4 files contain zero private references | SC-010, NFR-004 |

## Rollback

The `loopplane.scheduling` package is **purely additive** over Phases 1–3. Reverting the feature's
commits removes the package, example, docs, and tests and leaves the Phase-1/2/3 layers and all on-disk
records untouched (the scheduler owns no runtime/loop state and no storage format). Observation defaults
off, so a partial revert can never change scheduling behavior.
