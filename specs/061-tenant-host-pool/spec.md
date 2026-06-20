# Feature Specification: Per-Principal Host Pool

**Feature Branch**: `061-tenant-host-pool`

**Created**: 2026-06-20

**Status**: Draft — **plan STOPs to consult the maintainer (pool vs relax-`_active` FORK) + authors an ADR**

**Input**: User description: "A per-principal host pool (gap G20-A): layer a host pool/registry ABOVE the host so different principals can run concurrently, while EACH principal's host keeps its per-host sequential invariant (the `_active` gate). Per-principal in-flight caps. Unit 061, Tier-4 (the LAST unit of the batch). Default single-host = byte-identical. An ADR + a maintainer FORK at plan: pool-above-host (recommended) vs relax the `_active` gate. The platform tail (resource fairness / quota / many-writer durability) is DEFERRED."

## ⚠️ Boundary note (read first)

Today the web/API host shares a SINGLE `LoopPlaneHost`; its `_active` flag (host.py:280-284)
serializes runs — a second concurrent run raises `RuntimeError("a run is already active…")` (a 409).
This serializes runs ACROSS principals (principal A's run blocks principal B). G20-A wants
**concurrent multi-principal** execution. This is a **maintainer FORK at plan** — (A) **pool-above-
host** (recommended): a per-principal `LoopPlaneHost` pool/registry ABOVE the host, so each principal
gets an isolated host that keeps its own sequential `_active` invariant, with per-principal in-flight
caps — **the per-host sequential invariant is preserved**; vs (B) **relax the `_active` gate** (allow
concurrent runs on one host — risky: the host's per-run state was not built for concurrency). An
**ADR** records the choice. **Default single-host = byte-identical** (the pool is opt-in). The
**platform tail (resource fairness / quota / many-writer durability) is DEFERRED.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two principals run concurrently (Priority: P1)

With the pool enabled, principal A and principal B each run at the same time without blocking each
other; each principal's own runs remain sequential (one at a time per principal).

**Why this priority**: This is gap G20-A — today one shared host serializes ALL runs across all
principals, so a second user is blocked by the first; the pool gives per-principal concurrency.

**Independent Test** (offline, in-process): with the pool enabled, start a run for principal A and a
run for principal B concurrently → both proceed (neither raises "a run is already active"); a SECOND
concurrent run for principal A → rejected (its host's sequential invariant holds).

**Acceptance Scenarios**:

1. **Given** the pool enabled, **When** principals A and B run concurrently, **Then** both proceed
   (per-principal hosts; no cross-principal blocking).
2. **Given** principal A already running, **When** A starts a second concurrent run, **Then** it is
   rejected (A's host stays sequential — the per-host invariant is preserved).

---

### User Story 2 - Default single-host byte-identical (Priority: P1)

With the pool disabled (the default) the web/API host behaves EXACTLY as today — a single shared host
serializing runs; no behavior change.

**Why this priority**: The pool must be opt-in and impose nothing on existing single-tenant
deployments.

**Independent Test**: with no pool configured, behavior + the existing webapi tests are unchanged
(single shared host; a concurrent run → the existing 409).

**Acceptance Scenarios**:

1. **Given** no pool configured (default), **When** runs execute, **Then** behavior is byte-identical
   to today (one shared host; sequential; the existing 409 on a concurrent run).

---

### User Story 3 - Bounded + contained (Priority: P2)

The pool is bounded — a per-principal in-flight cap (and/or a max-principals cap) bounds resource use;
a per-principal host is created on first use and reused. Pool/host lifecycle is contained (a failing
principal does not affect others — per-principal isolation).

**Why this priority**: An unbounded pool would be a resource-exhaustion risk; the pool must bound
in-flight work and isolate principals.

**Independent Test**: with the pool + an in-flight cap, exceeding the cap for a principal is rejected
(not unbounded); one principal's failure leaves others available.

**Acceptance Scenarios**:

1. **Given** the pool + a per-principal in-flight cap, **When** a principal exceeds it, **Then** the
   excess is rejected/bounded (no unbounded growth).
2. **Given** the pool, **When** one principal's host errors, **Then** other principals are unaffected.

---

### Edge Cases

- **pool disabled (default)**: single shared host, byte-identical.
- **same principal, 2nd concurrent run**: rejected (the per-host sequential invariant holds).
- **unknown / new principal**: a host is created on first use (lazily), bounded by a max-principals
  cap if configured.
- **in-flight cap exceeded**: rejected/bounded, never unbounded.
- **one principal's host fails**: contained; other principals continue.
- **the platform tail (fairness/quota/many-writer)**: DEFERRED — not in this unit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide a **per-principal host pool/registry** (layered ABOVE the host) so different
  principals run **concurrently**; each principal's host is created on first use + reused.
- **FR-002**: Each principal's host MUST keep its **per-host sequential invariant** (the `_active`
  gate) — a second concurrent run for the SAME principal is rejected exactly as today.
- **FR-003**: The feature MUST be **default-off / byte-identical**: with no pool configured the
  web/API host behaves exactly as today (a single shared host; the existing 409 on a concurrent run);
  the existing tests pass unchanged.
- **FR-004**: The pool MUST be **bounded** — a per-principal in-flight cap (and/or a max-principals
  cap); exceeding a cap is rejected/bounded (no unbounded host/run growth).
- **FR-005**: The pool MUST be **contained** — one principal's host failure does not affect other
  principals (per-principal isolation).
- **FR-006**: The capability MUST be **additive** — no breaking change to `LoopPlaneHost`, the agent
  loop, the gateway, the event schema, or the content model; the pool layers ABOVE the host. An
  **ADR** records the model (the maintainer FORK: pool-above-host vs relax-`_active`).
- **FR-007** (**plan FORK — maintainer consult**): the model — **pool-above-host** (recommended) vs
  **relax the `_active` gate** — MUST be confirmed by the maintainer at plan. **The platform tail
  (resource fairness / quota / many-writer durability) is DEFERRED.**

### Key Entities *(include if feature involves data)*

- **Host pool/registry**: `principal_id → LoopPlaneHost` (lazily created, reused), with per-principal
  in-flight caps + an optional max-principals bound; default disabled (a single shared host).
- **Per-principal host**: an isolated `LoopPlaneHost` keeping its own sequential `_active` invariant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the pool enabled, two principals run concurrently without blocking each other,
  while a second concurrent run for one principal is rejected — in 100% of covered scenarios
  (offline/in-process).
- **SC-002**: With the pool disabled (default), behavior is byte-identical to today (single shared
  host; the existing 409); the existing webapi/host tests pass unchanged.
- **SC-003**: The pool is bounded (in-flight / max-principals caps enforced) + contained (one
  principal's failure isolated); no breaking host/loop/gateway/event change; the four gates pass.

## Assumptions

- Reuses the existing `LoopPlaneHost` (each principal gets its own instance via a host factory) + the
  webapi principal→session mapping; the pool layers ABOVE the host (the recommended fork) so the
  per-host sequential `_active` invariant + all host internals are unchanged. The pool is built where
  the webapi app is created (a host factory / pool), default disabled (a single shared host).
- **Plan FORK (maintainer consult, FR-007)**: pool-above-host vs relax-`_active`.
- **Out of scope / DEFERRED (the G20 platform tail)**: resource fairness / fair model-call
  scheduling / anti-noisy-neighbor; per-tenant quota; many-writer durability (entangled with G19);
  cross-process / distributed pooling. This unit is the additive per-principal isolation SLICE only.
- Additive; default-off byte-identical; offline-testable; public-safe (principal ids are opaque, no
  secrets). The plan authors the ADR. Per Constitution IX the concept is borrowed but re-derived.
