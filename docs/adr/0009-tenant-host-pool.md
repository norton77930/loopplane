# ADR 0009: Per-principal host pool (G20-A, the isolation slice)

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (chose **pool-above-host** at the 061 plan consult); spec 061
  (tenant-host-pool). The LAST unit of the G22 + Tier-4 batch.
- **Related**: Constitution **III** (a bounded, opt-in concurrency primitive), **IV** (a serving
  layer ABOVE the host — the host/loop/gateway are unchanged), **X** (additive, default-off
  byte-identical, reversible), **VII** (principal ids are opaque). Builds on unit 022 (the
  `Principal`) + `LoopPlaneHost`. Ninth ADR (after 0001–0008).

## Context

The web/API host shares a SINGLE `LoopPlaneHost`; its `_active` flag (host.py:280-284) serializes
runs — a second concurrent run raises `RuntimeError("a run is already active…")` (a 409). Because the
host is shared across principals, this serializes runs **across principals** (principal A blocks
principal B). Gap G20-A wants **concurrent multi-principal** execution. The design fork was: layer a
**per-principal host pool ABOVE the host** vs **relax the `_active` gate** on the shared host.

## Decision

- **D1 — Pool-above-host (MAINTAINER-CHOSEN).** Layer a **per-principal host pool/registry** above the
  host: each principal gets its OWN `LoopPlaneHost` (lazily created via a host factory, reused across
  that principal's requests). Different principals run **concurrently** (independent hosts); each
  principal's host keeps its **per-host sequential `_active` invariant** unchanged (a second
  concurrent run for the SAME principal is still rejected). The pool wraps the existing host
  selection (incl. the per-model host registry) keyed by principal; the host internals, the agent
  loop, the gateway, and the event schema are **UNCHANGED**.
- **D2 — Default-off, byte-identical.** With no pool configured (the default — a single shared host /
  a single-host factory) the web/API host behaves EXACTLY as today: one shared host, sequential, the
  existing 409 on a concurrent run. The existing tests pass unchanged. The pool is opt-in (a host
  factory + caps supplied where the app is created).
- **D3 — Bounded + contained.** A per-principal **in-flight cap** (and/or a max-principals bound)
  bounds resource use — exceeding a cap is rejected/bounded (no unbounded host/run growth). One
  principal's host failure is **isolated** (per-principal containment); it does not affect others.
- **D4 — Additive; relax-`_active` REJECTED.** No change to `LoopPlaneHost`, the agent loop, the
  gateway, or the event schema — the pool layers above. Relaxing the `_active` gate (concurrent runs
  on one shared host) was **rejected**: the host's per-run state (history, the active session) is not
  built for concurrency and would risk data races.
- **D5 — Deferred (the G20 platform tail).** Resource fairness / fair model-call scheduling /
  anti-noisy-neighbor; per-tenant quota; many-writer durability (entangled with G19);
  cross-process / distributed pooling. This unit is the additive per-principal **isolation slice**
  only.

## Consequences

- **Enables G20-A**: concurrent multi-principal execution (the isolation slice) without touching the
  host/loop/gateway/event contracts; each principal's per-host sequential invariant is preserved.
  Additive + default-off byte-identical + reversible (remove the pool/factory → the single shared
  host).
- **Bounded + contained**: per-principal in-flight caps prevent resource exhaustion; per-principal
  isolation prevents cross-tenant failure spread.
- **Deferred (documented)**: the G20 platform tail (fairness/quota/many-writer/distributed). Out of
  scope unless a future unit + ADR revisits it. This completes the maintainer-authorized G22 + Tier-4
  batch (055–061) as the additive multi-tenant foundation, not the full platform.
