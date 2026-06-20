# Contract: Per-Principal Host Pool

An optional per-principal host pool above the web/API host. Per
[ADR 0009](../../docs/adr/0009-tenant-host-pool.md). Default (no pool) is byte-identical (a single
shared host). The host/loop/gateway/event are unchanged; the pool layers above.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `loopplane.webapi.TenantHostPool` | a per-principal host registry over a host factory | NEW (additive `__all__`). |
| `create_app(..., host_pool=None)` | optional pool/factory | NEW optional param; default None = the existing shared host. |

## Behavior

| Case | Result |
| ---- | ------ |
| No pool configured (default) | One shared `host` + `_select` — byte-identical to today (sequential; the existing 409 on a concurrent run). |
| Pool + two principals run concurrently | Both proceed (per-principal hosts; no cross-principal blocking). |
| Pool + same principal, 2nd concurrent run | Rejected — that principal's host keeps its sequential `_active` invariant (as today). |
| Pool + a new/unknown principal | A host is created on first use (lazily) via the factory + reused; bounded by `max_principals` if set. |
| Pool + a per-principal in-flight cap exceeded | Rejected/bounded — no unbounded host/run growth. |
| Pool + one principal's host fails | Contained — other principals are unaffected (per-principal isolation). |

## Invariants

- The pool layers ABOVE the host: `LoopPlaneHost`, the agent loop, the gateway, and the event schema
  are UNCHANGED; each principal's host keeps its per-host sequential `_active` invariant (preserved,
  not relaxed — the maintainer-chosen fork).
- Default (no pool) is byte-identical to pre-061 (a single shared host; the existing 409); the
  existing webapi/host tests pass unchanged. The pool is opt-in.
- Bounded: a per-principal in-flight cap (+ optional max-principals); excess rejected/bounded.
- Contained: one principal's host failure does not affect other principals.
- Additive; confined to `loopplane.webapi`; the pool never makes the controller/loop import the tools
  layer (V/VI intact); principal ids are opaque (public-safe, VII).
- Out of scope (deferred — the G20 platform tail): resource fairness / fair scheduling / quota /
  many-writer durability / cross-process pooling.
