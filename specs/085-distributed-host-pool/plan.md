# Implementation Plan: Distributed Host Pool

**Branch**: `085-distributed-host-pool` (artifact directory; current checkout may still be
`084-mcp-interactive-oauth`) | **Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/085-distributed-host-pool/spec.md`

**Boundary**: settled by **[ADR 0020](../../docs/adr/0020-distributed-host-pool.md)** — authored at
this plan step and **`Accepted`** (2026-09-02). This is an **R2** unit (cross-process concurrency /
serving-layer coordination). Specify-time defaults are closed: fork A (ownership collaborator),
web/API only, fail-closed admits, 072 turn scheduler stays local.

## Summary

Make the 061/072 serving guarantees hold when the web/API host is run as more than one worker.

Today `TenantHostPool` and `PlatformFairness` are process-local dictionaries. Two workers can run
the same principal twice and can multiply every cap by the worker count. 085 adds an opt-in
**admission collaborator** in front of every run-start path: take a cluster-scoped grant, heartbeat
it, release it. The in-memory store is the default (tests share one object across two simulated
workers). Multi-worker production uses Postgres via the existing `loopplane[postgres]` extra. No
new dependency, no File/SQLite admission backend, no `RuntimeConfig` knob, no Event Bus / Gateway /
`_active` change.

Default `create_app(admission=None)` is byte-identical. Fail-closed: a store that cannot confirm a
take rejects the new run with the existing 409/429 phrases. Cluster-wide fair *turn* interleaving,
G9, and G11 stay out of scope.

## Technical Context

**Language/Version**: Python 3.12+ (same as the web/API host).

**Primary Dependencies**: none new. `anyio` (base). Optional `psycopg` via existing
`loopplane[postgres]`, lazy-imported, `anyio.to_thread` (ADR 0008).

**Storage**: in-memory grants by default. Optional Postgres lease tables (not checkpoint/ledger
rows). No File/SQLite admission backend.

**Testing**: pytest, offline. Two simulated workers share one `InMemoryAdmissionStore`. Postgres
via the existing stub/contract pattern, not a required live cluster for the default gate.

**Target Platform**: `loopplane.webapi` serving layer (multi-worker). Desktop / local CLI
unchanged.

**Project Type**: Library/runtime with web/API integration.

**Performance Goals**: Admit/reject is a single uncontended store round-trip plus a periodic
heartbeat; not on the Gateway or model-call path.

**Constraints**: additive; default-off byte-identical; fail-closed; public-safe 409/429 phrases
only; no Tool Gateway change; no Event Bus / content / termination-reason / schema change; no new
extra; GATE-§E if a new dependency appears; ADR 0009 D4 (`_active` stays).

**Scale/Scope**: new `webapi/admission.py` (+ optional postgres module); `create_app` / router /
streaming / session drive wiring; focused unit tests; api-reference + TARGET §3 additive sentence
on implementation.

## Constitution Check

*GATE: evaluated before Phase 0 research and re-checked after Phase 1 design.*

- **I. Spec-First**: traces to `spec.md` FR-001…FR-021 and ADR 0020. ✅
- **III. Bounded opt-in**: a serving-layer concurrency primitive, default-off, capped, fail-closed. ✅
- **IV. Runtime Boundary Clarity**: the collaborator sits **above** `LoopPlaneHost` (with the 061
  pool). `_active` is not relaxed. Grants are serving leases, not session records (G3). ADR 0020 D9
  records the additive TARGET §3 sentence so the boundary definition moves with the code, which is
  what this principle requires. ✅
- **V. Tool Gateway Ownership**: admission is not a tool and does not authorize, resolve, or
  execute tools. Heartbeat/fencing does not cancel an in-flight Gateway call. ✅
- **VI. Runtime Event Bus Ownership**: no event-schema change, no `SCHEMA_VERSION` bump, no
  content-model change, no new termination reason. Rejects reuse existing HTTP/SSE error phrases. ✅
- **VII. Public-Safe Documentation**: 409/429 details stay the existing phrases; DSN/holder/grant
  never logged or returned. ✅
- **X. Testable Evolution**: additive, default-off, offline two-worker tests, reversible by
  omitting `admission=`. ✅

**Result**: **PASS, conditional on the R2 gate.** No constitution violation. Implementation may not
begin until ADR 0020 is Accepted.

**Post-design re-check**: unchanged PASS. Phase 1 did not add a Gateway stage, an event type, a
new extra, or a default change.

## Project Structure

### Documentation (this feature)

```text
specs/085-distributed-host-pool/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md
├── contracts/distributed-host-pool.md
├── checklists/requirements.md
└── tasks.md                      # /speckit-tasks — only after ADR 0020 Accepted
docs/adr/0020-distributed-host-pool.md   # R2 boundary decision (Proposed)
```

### Source Code (repository root)

```text
src/loopplane/webapi/admission.py          # NEW: AdmissionStore Protocol, AdmissionGrant,
                                           #   AdmissionRejected, AdmissionCoordinator.hold,
                                           #   InMemoryAdmissionStore
src/loopplane/webapi/admission_postgres.py # NEW: PostgresAdmissionStore (lazy psycopg,
                                           #   anyio.to_thread, DSN never echoed)
src/loopplane/webapi/app.py                # MODIFIED: create_app(admission=None); stash on
                                           #   app.state like host_pool
src/loopplane/webapi/__init__.py           # MODIFIED: export Protocol, coordinator, stores,
                                           #   AdmissionRejected (api-reference bijection)
src/loopplane/webapi/routers/interaction.py  # MODIFIED: wrap POST /runs with hold(); catch
                                             #   AdmissionRejected before RuntimeError
src/loopplane/webapi/streaming.py          # MODIFIED: wrap drive() with hold(); same mapping
src/loopplane/webapi/sessions.py           # MODIFIED: wrap run_session drive with hold()
docs/api-reference.md                      # MODIFIED: new public names under loopplane.webapi
docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md  # MODIFIED: §3 additive sentence (D9)

tests/unit/test_webapi_admission.py        # NEW: two simulated workers, fail-closed, TTL,
                                           #   concurrent take, default-off
tests/unit/test_tenant_host_pool.py        # EXTEND: admission=None still byte-identical
tests/unit/test_webapi.py                  # EXTEND: 409/429 phrases on cluster reject
```

**Structure Decision**: keep the seam **inside `loopplane.webapi`**, next to `TenantHostPool`,
rather than a new top-level package. Only this host is multi-worker; fairness must not import
webapi; a new TARGET block would over-claim reuse. Split Postgres into `admission_postgres.py` so
`admission.py` imports without `psycopg` (the 060/071 lazy-extra pattern).

`hold()` is the single chokepoint for run-start (ADR 0020 D8). Local `in_flight` remains as
defense in depth and is applied on the streaming and session paths as well, so the process-local
cap is not bypassed when admission is off.

Caps are arguments to `hold`, sourced at the call site from `TenantHostPool`'s in-flight cap and,
when present, `PlatformFairnessPolicy.max_outstanding_per_tenant`. They are not a second
`RuntimeConfig` policy.

## Complexity Tracking

> The Constitution Check passes. One fencing-window residual is recorded rather than hidden.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None (constitution) | N/A | N/A |
| Residual: a worker whose grant expired mid-`host.run` may overlap a successor until `host.run` returns (research R8) | Killing the run from the heartbeat would require a new cancellation reason or a Gateway abort — both VI/V | TTL ≫ one turn and heartbeat ≪ TTL; fencing is at admit, not inside the Gateway. Documented; no schema change. |

## Phase 0 / Phase 1 outputs

- [research.md](research.md) — forks, call sites, storage honesty, fail-closed
- [data-model.md](data-model.md) — grant, store Protocol, coordinator
- [contracts/distributed-host-pool.md](contracts/distributed-host-pool.md)
- [quickstart.md](quickstart.md) — embedder/operator validation (gated on ADR)

## Next Spec Kit step

**Verified.** Spec Kit flow complete. FR-021: code-reviewer pass; architecture-reviewer
GO after G5 `hold_local` default-off fix (`admission=None` does not expand 061
`in_flight` onto streaming/session).
