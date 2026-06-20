# Research: Per-Principal Host Pool

Settled by the maintainer (pool-above-host) + **[ADR 0009](../../docs/adr/0009-tenant-host-pool.md)**.
No open `NEEDS CLARIFICATION`.

## Decision 1 — Pool-above-host (maintainer-chosen; ADR 0009 D1)

**Decision**: A per-principal host pool above the web/API serving layer: each principal gets its own
`LoopPlaneHost` (lazily built via a host factory, reused), so different principals run concurrently
while each principal's host keeps its sequential `_active` invariant unchanged. The pool wraps the
existing `_select(model)` host selection, keyed by principal.

**Rationale**: Concurrency ACROSS principals without touching the host/loop/gateway; the per-host
sequential invariant (the host's per-run state) is preserved.

**Alternatives considered**: relax the `_active` gate (concurrent runs on one shared host) — REJECTED
by the maintainer: the host's per-run state (history, the active session) is not built for
concurrency and would risk data races.

## Decision 2 — Default-off byte-identity (ADR 0009 D2)

**Decision**: `create_app` gains an OPTIONAL host pool/factory; absent (the default) the existing
single shared `host` + `_select` path is used verbatim (one shared host; the existing 409 on a
concurrent run). The pool is opt-in.

**Rationale**: Impose nothing on existing single-tenant deployments; the existing tests pass
unchanged.

## Decision 3 — Bounded + contained (ADR 0009 D3)

**Decision**: The pool bounds per-principal in-flight runs (an `anyio` semaphore/counter) + an
optional max-principals bound; exceeding a cap is rejected/bounded. A per-principal host is created
on first use + reused; one principal's host failure is isolated from others.

**Rationale**: Prevent resource exhaustion + cross-tenant failure spread.

## Decision 4 — Additive; host/loop/gateway unchanged (ADR 0009 D4)

**Decision**: The pool lives in `loopplane.webapi` (the multi-tenant serving concern), built on the
existing `LoopPlaneHost` via a factory; no change to `LoopPlaneHost`, the agent loop, the gateway, or
the event schema. The pool never makes the controller/loop import the tools layer.

**Rationale**: Reuse-first; the boundary stays clean (the audit is satisfied; the pool is serving-
layer, not loop/controller).

## Out of scope (the G20 platform tail; ADR 0009 D5)

Resource fairness / fair model-call scheduling / anti-noisy-neighbor; per-tenant quota; many-writer
durability (entangled with G19); cross-process / distributed pooling. This is the additive
per-principal isolation SLICE only.
