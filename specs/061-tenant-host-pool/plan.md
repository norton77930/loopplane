# Implementation Plan: Per-Principal Host Pool

**Branch**: `061-tenant-host-pool` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/061-tenant-host-pool/spec.md`

**Maintainer DECISION (consulted at plan, FR-007)**: **pool-above-host** — a per-principal
`LoopPlaneHost` pool above the host; each host keeps its sequential `_active` invariant; default
single-host byte-identical. Recorded in **[ADR 0009](../../docs/adr/0009-tenant-host-pool.md)**.
Relaxing `_active` was rejected.

## Summary

Layer a per-principal host pool above the web/API serving layer so different principals run
concurrently while each principal's host keeps its sequential `_active` invariant. `create_app` today
shares a single `host` (+ an optional `models` catalog of single-model hosts) across all principals
via `_select(model) -> host`; this serializes runs across principals. Add an OPTIONAL host **factory
+ pool**: when supplied, the caller's host is resolved **per principal** (`pool.host_for(principal_id,
model)` → a per-principal `LoopPlaneHost`, lazily created via the factory, reused, bounded by a
per-principal in-flight cap + an optional max-principals bound). With no pool/factory (the default)
the existing shared-host behavior is **byte-identical** (one shared host; the existing 409 on a
concurrent run). The host internals, the agent loop, the gateway, and the event schema are
UNCHANGED; the pool layers above. The G20 platform tail (fairness/quota/many-writer) is deferred.

## Technical Context

**Language/Version**: Python 3.11+; `anyio` (locks/semaphores already used).

**Primary Dependencies**: none new — reuses `LoopPlaneHost`, the existing `create_app` /
`_select(model)` host selection, the per-principal session registry (022), `anyio`.

**Storage**: in-memory pool (`principal_id → host(s)`); no persistence.

**Testing**: pytest, offline/in-process: with a pool + a host factory, two principals run
concurrently (neither raises "a run is already active"); a same-principal second concurrent run is
rejected; default (no pool) is byte-identical (single shared host; the existing 409); the per-principal
in-flight cap bounds; one principal's host failure is isolated.

**Target Platform**: the web/API host (`loopplane.webapi`).

**Constraints**: additive; the pool layers ABOVE the host (host/loop/gateway/event UNCHANGED — the
per-host `_active` invariant preserved); default single-host byte-identical; bounded + contained;
principal ids opaque (public-safe); no new dependency. ADR 0009. The platform tail deferred.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007 + ADR 0009. ✅
- **III. Bounded opt-in**: a per-principal concurrency primitive, default-off, with in-flight caps. ✅
- **IV. Boundary**: A serving layer ABOVE the host; `LoopPlaneHost`/the loop/the gateway are
  unchanged (the per-host `_active` invariant is preserved); recorded in ADR 0009. ✅
- **V. Tool Gateway**: N/A — no tool/execution path; the pool never makes the controller/loop import
  the tools layer (the pool is webapi/host-level). ✅
- **VI. Event Bus**: No event-schema/SCHEMA_VERSION/content change. ✅
- **VII. Public-safe**: Principal ids are opaque keys; no secrets. ✅
- **X. Testable Evolution**: Additive; default-off byte-identical; reversible; offline-tested. ✅

**Result**: PASS — additive; the maintainer chose pool-above-host so there is **no breaking host/001
contract change** (the `_active` invariant is preserved, not relaxed); ADR 0009 records it. Complexity
Tracking n/a (the platform tail is explicitly deferred).

## Project Structure

### Documentation (this feature)

```text
specs/061-tenant-host-pool/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/tenant-host-pool.md
└── checklists/requirements.md
docs/adr/0009-tenant-host-pool.md   # the fork decision (pool-above-host)
```

### Source Code (repository root)

```text
src/loopplane/webapi/pool.py        # NEW: TenantHostPool — principal_id -> LoopPlaneHost via a host
                                    #   factory; lazily created + reused; per-principal in-flight cap
                                    #   + optional max-principals; contained per-principal isolation
src/loopplane/webapi/app.py         # MODIFIED: create_app gains an optional host pool/factory; the
                                    #   per-principal host resolution wraps the existing _select
                                    #   (default None -> the existing shared host, byte-identical)
src/loopplane/webapi/__init__.py    # MODIFIED: export TenantHostPool (additive __all__)
docs/api-reference.md               # MODIFIED: + TenantHostPool under loopplane.webapi
tests/<webapi pool tests>           # NEW: concurrent-principals, same-principal-sequential,
                                    #   default-off byte-identity, in-flight cap, isolation
```

**Structure Decision**: `TenantHostPool` (a new `loopplane.webapi` class) maps `principal_id` (×
the selected model) to a `LoopPlaneHost` built by a host **factory** the embedder supplies; it caches
+ reuses per principal, bounds per-principal in-flight runs (an `anyio` semaphore / counter) + an
optional max-principals, and isolates failures per principal. `create_app` gains an OPTIONAL pool (or
factory) param; when absent (default) the existing single shared `host` + `_select` path is used
verbatim (byte-identical). When present, the per-principal session/run routes resolve the host via
`pool.host_for(principal.id, model)` instead of the shared `_select`. The host/loop/gateway are
untouched (the per-host `_active` invariant is preserved — that is exactly why pool-above-host was
chosen over relaxing `_active`). No change outside `loopplane.webapi`.

## Complexity Tracking

> A per-principal pool above the existing host selection — additive, default-off byte-identical, the
> per-host invariant preserved (the maintainer-chosen fork). A bounded + contained registry; one
> optional `create_app` param; ADR 0009. The platform tail (fairness/quota/many-writer/distributed)
> is explicitly DEFERRED. Not a Constitution violation.
