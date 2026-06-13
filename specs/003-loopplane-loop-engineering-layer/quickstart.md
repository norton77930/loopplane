# Quickstart & Validation Guide: Loop Engineering Layer

**Feature**: `003-loopplane-loop-engineering-layer` | **Spec**: [spec.md](./spec.md) |
**Plan**: [plan.md](./plan.md)

This guide documents the runnable scenarios that prove the Loop Engineering Layer works end-to-end
through the **public** surface only. It is a validation/run guide — implementation lives in `tasks.md`
and the implementation phase. Every scenario uses the credential-free `ScriptedModel` and scripted
validators/evaluators, so all are deterministic (NFR-002) and public-safe (NFR-004).

## Prerequisites

- Phases 1 and 2 merged (`loopplane` + `loopplane.host` importable).
- Dev install: `pip install -e .[dev]` (Phase-1 toolchain: pytest + anyio).
- No credentials, no network — the scripted model is the test instrument.

## Run the validation suite

```powershell
pytest tests/unit/test_engineering_core.py `
       tests/integration/test_loop_us1.py `
       tests/integration/test_loop_us2.py `
       tests/integration/test_loop_us3.py `
       tests/integration/test_loop_us4.py `
       tests/integration/test_loop_us5.py `
       tests/contract/test_engineering_boundary.py
```

Or the whole suite: `pytest`.

## Minimal example (design intent)

`examples/loop_quickstart.py` (delivered in the implementation phase) defines a single-iteration loop
over a scripted host and triggers it manually:

```python
from loopplane.host import RuntimeConfig
from loopplane.engineering import (
    LoopDefinition, HostRuntimeProfile, ManualTrigger, ValidationPolicy,
    RetryPolicy, RepairPolicy, ArtifactPolicy, ApprovalPolicy, ObservationPolicy,
    stop_on_pass, always_pass, run_loop,
)

definition = LoopDefinition(
    loop_id="echo-once",
    trigger=ManualTrigger(),
    input_source=...,                       # "please echo hello"
    host_profile=HostRuntimeProfile(config=RuntimeConfig(model=scripted_model, tools=(...,))),
    validation_policy=ValidationPolicy(validator=always_pass()),
    retry_policy=RetryPolicy(max_retries=0),
    repair_policy=RepairPolicy(enabled=False),
    stop_condition=stop_on_pass(),
    artifact_policy=ArtifactPolicy(reuse=False),
    approval_policy=ApprovalPolicy(),
    observation_policy=ObservationPolicy(emit_loop_events=True),
)

outcome = await run_loop(definition, on_loop_event=print_event)
assert outcome.terminal_event == "loop_completed"
```

Expected ordered Loop Events: `loop_started` → `loop_iteration_started` →
`loop_iteration_completed` → `validation_completed` → `loop_completed`.

## Scenario → requirement map

| # | Scenario | Asserts | Maps to |
|---|---|---|---|
| 1 | Define + manual-run a single-iteration loop | exactly one Agent Run via `host.run`; Loop State references `session_id` + artifacts; ordered Loop Events | US1, SC-001, FR-011 |
| 2 | Boundary audit | the run was started **only** through the Host Interface; no Phase-1 internal called | US1.4, SC-002, NFR-003 |
| 3 | Determinism | same loop run twice ⇒ identical Loop Event stream + identical outcome | US1.3, SC-002, NFR-002 |
| 4 | Gate on `pass` | `validation_completed` then `loop_completed` | US2.1, SC-003 |
| 5 | Gate on `needs_repair` | `validation_completed` → `repair_requested` → repair iteration | US2.2, SC-003 |
| 6 | Gate on `needs_human_review` | `human_review_requested`; loop pauses, no further Agent Run | US2.3, SC-003, SC-007 |
| 7 | Validator fault | fail-safe to human review (or `loop_failed`), diagnostic, never silent pass | US2.4, SC-003, FR-034 |
| 8 | Retry exhaustion | `max_retries=2` + always-`fail` ⇒ ≤3 Agent Runs, `retry_scheduled` ×2 w/ backoff delay, `loop_failed` | US3.1, SC-004 |
| 9 | Repair input content | repair iteration's submitted input contains the repair instruction + prior-run context; definition unchanged | US3.2, SC-005, FR-052 |
| 10 | Artifact reuse by reference | repair references the prior artifact via `host.retrieve_artifact`, not a copy | US3.3, FR-053 |
| 11 | Checkpoint reuse-or-reset | default reset (fresh run); reuse only by reference when configured | US3.4, FR-054 |
| 12 | Evaluator score-threshold stop | score ≥ threshold ⇒ `evaluation_completed` then `loop_completed` | US4.1, FR-007 |
| 13 | Evaluation is non-gating | low score + `pass` ⇒ control follows validator/stop, not evaluation | US4.2, FR-041 |
| 14 | No evaluation policy | no evaluation step, no `evaluation_completed` event | US4.3, FR-042 |
| 15 | Evaluator error | non-fatal diagnostic; iteration proceeds on validation result | US4.4, FR-043 |
| 16 | Manual trigger only | manual trigger starts exactly one Loop Run; no daemon | US5.1, SC-008 |
| 17 | Interval/condition driver | a host-supplied driver enacts a tick / satisfied predicate via the manual entry point | US5.2, SC-008 |
| 18 | Human-review pause/resume | `needs_human_review` pauses; a supplied decision resumes or terminates; never strands a run | US5.3–4, SC-007 |
| 19 | Event-sufficiency reconstruction | `reconstruct_state(events, outcomes)` rebuilds Loop State from the stream alone | SC-006, FR-062 |
| 20 | Observation parity | observation off vs on ⇒ identical decisions + terminal outcome | SC-009, NFR-005 |
| 21 | Public-safety scan | committed Phase-3 files contain zero private references; no internal re-implemented | SC-010, NFR-004 |

## Rollback

The `loopplane.engineering` package is **purely additive** over Phases 1–2. Reverting the feature's
commits removes the package, examples, docs, and tests and leaves the Phase-1/2 runtime and all on-disk
records untouched (the loop layer introduces no storage format and owns no runtime state). Observation
defaults off, so a partial revert can never change core-loop behavior.
