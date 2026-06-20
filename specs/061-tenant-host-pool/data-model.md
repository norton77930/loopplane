# Data Model: Per-Principal Host Pool

Additive; inside `loopplane.webapi`. No host/loop/gateway/event change (the pool layers above). Per
[ADR 0009](../../docs/adr/0009-tenant-host-pool.md).

## TenantHostPool (new — the per-principal host registry)

| Member | Type | Notes |
| ------ | ---- | ----- |
| `host_factory` | `Callable[..., LoopPlaneHost]` | builds a fresh per-principal host (the embedder supplies it). |
| `per_principal_in_flight` | `int` | the per-principal concurrent-run cap (bound; default a small N). |
| `max_principals` | `int \| None` | optional bound on the number of live principal hosts. |
| `host_for(principal_id, model=None)` | `-> LoopPlaneHost` | the principal's host (lazily created via the factory, reused); raises/bounds when a cap is exceeded. |

Per-principal state: the host instance(s) + an `anyio` semaphore/counter for in-flight runs. One
principal's host failure is isolated (per-principal entry).

## create_app (modified — additive)

| Param | Type | Notes |
| ----- | ---- | ----- |
| `host_pool` (or a factory) | `TenantHostPool \| None = None` | NEW — when set, the per-principal host resolution uses it; default None = the existing single shared `host` + `_select` (byte-identical). |

The per-principal session/run routes resolve the host via `pool.host_for(principal.id, model)` when a
pool is configured; otherwise the existing `_select(model)` shared host.

## Rules (from FRs + ADR 0009)

| Rule | Source |
| ---- | ------ |
| per-principal host pool above the host; principals run concurrently; lazily created + reused | FR-001, D1 |
| each principal's host keeps its sequential `_active` invariant (same-principal 2nd run rejected) | FR-002, D1 |
| default-off byte-identical (no pool → single shared host; the existing 409) | FR-003, D2 |
| bounded (per-principal in-flight cap + optional max-principals); excess rejected/bounded | FR-004, D3 |
| contained (one principal's host failure isolated) | FR-005, D3 |
| additive; host/loop/gateway/event UNCHANGED; pool layers above | FR-006, D4 |
| plan FORK = pool-above-host (maintainer); platform tail DEFERRED | FR-007, D5 |
