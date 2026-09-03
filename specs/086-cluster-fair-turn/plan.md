# Implementation Plan: Cluster Fair Turn

**Branch**: `086-cluster-fair-turn` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/086-cluster-fair-turn/spec.md`

**Boundary**: settled by **[ADR 0021](../../docs/adr/0021-cluster-fair-turn.md)** — authored at
this plan step and **`Accepted`** (2026-09-03). This is an **R2** unit (cross-process scheduling).
Specify-time defaults are closed: fork A (injectable turn-permit collaborator), web/API when 072
is on, degrade-to-local on collaborator failure, 085 grants unchanged.

## Summary

Make 072's model-turn policy hold when the web/API host is run as more than one worker.

Today `PlatformFairness.model_turn` is a process-local waiter list. 085 already cluster-scoped
*who may start a run*. 086 cluster-scopes *who may start the next model call* for
already-admitted work, via an optional collaborator on `PlatformFairness`. Local 072 remains
defense in depth. `create_app` does not gain a new argument. No new extra. No Event Bus /
Gateway / `_active` change.

Default `PlatformFairness(policy)` is byte-identical. If the cluster permit store cannot confirm,
already-admitted work degrades to local 072 (does not hang). Weighted tiers, live migration, G9,
and G11 stay out of scope.

## Technical Context

**Language/Version**: Python 3.12+ (same as fairness / web/API host).

**Primary Dependencies**: none new. `anyio` (base). Optional `psycopg` via existing
`loopplane[postgres]`, lazy-imported, `anyio.to_thread` (ADR 0008) if a durable permit store is
shipped.

**Storage**: in-memory permits by default. Optional Postgres permit tables (not checkpoint,
ledger, or 085 grant rows). No File/SQLite permit backend.

**Testing**: pytest, offline. Two `PlatformFairness` instances share one `InMemoryTurnPermitStore`.
Postgres via the existing stub/contract pattern, not a required live cluster.

**Target Platform**: `loopplane.fairness` used by the web/API serving path (multi-worker).
Desktop / local CLI unchanged.

**Project Type**: Library/runtime with web/API integration.

**Performance Goals**: Permit take is one uncontended store round-trip plus optional heartbeat
on the model-turn path (already a wait in 072). Not on the Gateway execute path.

**Constraints**: additive; default-off byte-identical; degrade-not-hang on store failure;
no Tool Gateway change; no Event Bus / content / termination-reason / schema change; no new
extra; GATE-§E if a new dependency appears; ADR 0009 D4 (`_active` stays); Phase-1 MUST NOT
import webapi.

**Scale/Scope**: additive constructor on `PlatformFairness`; permit Protocol + in-memory store;
optional Postgres module; focused unit tests; api-reference if a helper is exported.

## Constitution Check

*GATE: evaluated before Phase 0 research and re-checked after Phase 1 design.*

- **I. Spec-First**: traces to `spec.md` FR-001…FR-020 and ADR 0021. ✅
- **III. Bounded opt-in**: a fairness collaborator, default-off, capped, reversible. ✅
- **IV. Runtime Boundary Clarity**: fairness stays Phase-1; stores are injected. `_active` is
  not relaxed. Permits are not session records (G3). ✅
- **V. Tool Gateway Ownership**: turn permits are not tools and do not authorize, resolve, or
  execute tools. ✅
- **VI. Runtime Event Bus Ownership**: no event-schema change, no `SCHEMA_VERSION` bump, no
  content-model change, no new termination reason. ✅
- **VII. Public-Safe Documentation**: no new HTTP phrase; DSN/holder/permit never logged or
  returned. ✅
- **X. Testable Evolution**: additive, default-off, offline two-worker tests, reversible by
  omitting `turn_permits=`. ✅

**Result**: **PASS, conditional on the R2 gate.** No constitution violation. Implementation may
not begin until ADR 0021 is Accepted.

**Post-design re-check**: unchanged PASS. Phase 1 did not add a Gateway stage, an event type, a
new extra, a `create_app` argument, or a default change.

## Project Structure

### Documentation (this feature)

```text
specs/086-cluster-fair-turn/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md
├── contracts/cluster-fair-turn.md
├── checklists/requirements.md
└── tasks.md                      # /speckit-tasks — only after ADR 0021 Accepted
docs/adr/0021-cluster-fair-turn.md   # R2 boundary decision (Accepted)
```

### Source Code (repository root)

```text
src/loopplane/fairness.py                 # MODIFIED: optional turn_permits= on
                                          #   PlatformFairness; Protocol; in-memory store
                                          #   (or split if the module would grow too far)
src/loopplane/fairness_postgres.py        # OPTIONAL NEW: PostgresTurnPermitStore
                                          #   (lazy psycopg; only if ADR D2 ships it)
src/loopplane/loop/loop.py                # UNCHANGED: still calls fairness.model_turn
src/loopplane/webapi/app.py               # UNCHANGED: no new create_app argument
src/loopplane/host/host.py                # UNCHANGED except if a public read is required
docs/api-reference.md                     # MODIFIED only if a helper is exported

tests/unit/test_fairness_core.py          # EXTEND: cluster permit two-worker burst;
                                          #   default-off; degrade on store error
tests/unit/test_webapi_admission.py       # EXTEND: 085 scenarios still hold with
                                          #   turn_permits configured
```

**Structure Decision**: keep the Protocol and in-memory store next to `PlatformFairness`
(Phase-1). Inject implementations; do not import webapi. Do not add `create_app` wiring —
the embedder already supplies `platform_fairness`. Split Postgres only if the ADR ships it
in this unit (same lazy-extra pattern as 085).

`model_turn` is the single chokepoint (ADR 0021 D8). Local 072 scheduling always runs;
cluster take wraps the granted turn when the collaborator is set.

Caps are read from `PlatformFairnessPolicy`, not duplicated on the store.

## Complexity Tracking

> The Constitution Check passes. One degrade residual is recorded rather than hidden.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None (constitution) | N/A | N/A |
| Residual: during a permit-store outage, cluster fairness is lost until recovery (research R4) | Fail-closed would wedge already-admitted runs (V/VI if we invented a cancel reason) | Degrade to local 072 (spec FR-010 / ADR 0021 D5). Documented. |

## Phase 0 / Phase 1 outputs

- [research.md](research.md) — forks, call site, storage honesty, degrade polarity
- [data-model.md](data-model.md) — permit, store Protocol, constructor
- [contracts/cluster-fair-turn.md](contracts/cluster-fair-turn.md)
- [quickstart.md](quickstart.md) — embedder validation (gated on ADR)

## Next Spec Kit step

**Verified.** Spec Kit flow complete. FR-019: code-reviewer pass (after `hold_turn` /
shared `schedule()` / typed `TurnPermitUnavailable`); architecture-reviewer GO,
0 blocking.
