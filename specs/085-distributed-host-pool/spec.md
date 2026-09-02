# Feature Specification: Distributed Host Pool

**Feature Branch**: `085-distributed-host-pool`

**Created**: 2026-09-02

**Status**: Draft — **R2 (cross-process concurrency / serving-layer coordination)**. **ADR 0020 MUST
be authored at plan and approved by the maintainer before any implementation begins.** This unit
extends ADR 0009 and ADR 0013; it does not supersede them.

**Depends on**: 061-tenant-host-pool (Verified), 072-platform-fairness (Verified). Reference only:
060-postgres-checkpoint and 062-usd-ledger (existing many-writer stores for *other* records, not a
substitute for this unit's ownership seam).

**Input**: User description: "Close the remaining G20 distributed tail from
`docs/gap-analysis.md` C4 P1: cross-process / multi-worker execution above the per-principal host
pool — many-writer durability and distributed pooling / scheduling. Unit 061 shipped in-process
per-principal isolation (ADR 0009). Unit 072 shipped in-process fairness and outstanding-work quota
(ADR 0013 D8: distributed / cross-process / many-writer deferred). Unit 071 made SSE replay durable
across workers, but *execution itself* is still in-process single-worker. 085 takes over that
explicitly deferred slice, and only that."

---

## ⚠️ Boundary note (read first)

**This is an R2 unit.** It introduces cross-process coordination of who may run for a principal.
The gates are non-negotiable:

- **ADR 0020 at plan, approved before implementation** — not written retroactively. The ADR extends
  0009 (pool-above-host) and 0013 (in-process fairness); it must not relax `LoopPlaneHost._active`
  or move tool execution / events out of the Gateway / Event Bus.
- **No new required dependency.** If planning discovers a genuinely new library or extra is needed
  (a message queue, a lock service, a new database driver), that is a **GATE-§E stop**, not a silent
  addition. Reusing an existing extra (for example `loopplane[postgres]`) is allowed only when the
  ADR says so.
- **Final review requires `code-reviewer` and `architecture-reviewer`.** Both: this unit changes
  the serving-layer contract above the host (an exposed interface).

**The seam this grows from** (in-process today):

| Location | Today |
| -------- | ----- |
| `webapi/pool.py` `TenantHostPool` | Per-process `dict` of hosts keyed by `(principal, model)` plus an `anyio.Semaphore` keyed by `principal_id`. In-flight cap **rejects** (does not block) when exceeded. |
| ADR 0009 D1 / D4 | Pool-above-host. Each principal keeps a sequential `_active` host. Relaxing `_active` was **rejected**. |
| ADR 0009 D5 | Deferred: many-writer durability and cross-process / distributed pooling. |
| `loopplane.fairness` (072) | In-process outstanding-work quota + fair model-turn permits. |
| ADR 0013 D8 | Deferred: distributed fairness, cross-process scheduling, external queues, database-backed reservations, many-writer durable ordering, weighted tenant tiers. |
| Durable stores already shipped | Checkpoint / ledger / event-replay Postgres backends are many-writer for *those* records. They do **not** coordinate host-pool ownership or fairness admission. |

**Two facts that bound the design:**

1. **The 061/072 guarantees are process-local.** Two workers of the same web/API host each have
   their own pool and their own fairness object. A principal can therefore hold an active run on
   worker A and another on worker B at the same time, and a configured outstanding-work cap can be
   multiplied by the worker count. Operators who scale out the web/API host silently lose the
   multi-tenant promises those units already documented.
2. **The valuable 061 property must survive.** Different principals must still run at the same
   time. This unit must not re-serialize the whole deployment through a single global lock.

**What this unit must never do**: execute a tool, emit a new event type, relax per-host sequential
execution, migrate a live run between workers, ship a message-queue product, or treat load-balancer
stickiness as a substitute for the invariant (stickiness is an ops hint; a mis-routed request must
still be safe).

---

## Why this exists

LoopPlane can already serve two principals at once *inside one process*, and can bound one noisy
principal *inside one process*. It cannot keep those promises when the operator runs more than one
worker. That is the remaining G20 tail: not "add a cloud", and not G9 remote agent execution (agents
still run in the host that accepted the work).

071 closed durable *replay* across workers. 060/062 closed many-writer *records* for checkpoints and
spend. The serving layer — who owns a principal's in-flight run, and whether a cap is global — is
still a per-process dictionary. This unit makes that layer honest across workers.

---

## Specify-time defaults (not open questions)

These are the informed defaults used to write a complete spec. They may be confirmed or overridden
at plan when ADR 0020 is authored. They are **not** `[NEEDS CLARIFICATION]` markers.

| Topic | Default | Why this is the default |
| ----- | ------- | ----------------------- |
| Slice | **Cross-process ownership + global admission caps.** Cluster-wide fair *turn interleaving* stays deferred (the 072 scheduler remains local to a worker). | Matches how 061 then 072 sliced G20: one independently testable slice, not the whole remaining tail in one unit. |
| Mechanism | **Host-supplied ownership collaborator above the pool** (recommended ADR fork). In-memory default = single-process equivalent. Durable backend optional and reuse-first. | Preserves pool-above-host. Sticky routing alone cannot enforce the invariant. A new queue extra is GATE-§E. |
| Surfaces | **Web/API serving path.** Desktop sidecar and local CLI stay single-process; 079 remote CLI is a client of web/API and inherits the invariant. | Only the web/API host is scaled as multiple workers today. |
| Failure | **Fail-closed on admit.** If ownership cannot be confirmed, do not start a second run. | A false admit is a double-run (correctness). A false reject is availability. Control-plane default is fail-closed. |
| Identity | **Existing principal id.** Ownership and caps are per principal (matching 061 in-flight), not a new tenant concept. | ADR 0013 D4. |

**Plan FORK (maintainer consult, recorded as FR-020):**

- **A (recommended): shared ownership / lease collaborator** above `TenantHostPool`, with a store
  Protocol, an in-memory default, and an optional durable backend that reuses an existing extra.
- **B: sticky routing only** — rejected as the sole mechanism; it cannot make a mis-routed request
  safe.
- **C: new external queue / lock extra** — GATE-§E; only if the maintainer explicitly chooses it.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One principal, two workers, still sequential (Priority: P1)

An operator runs two workers of the same web/API host with the distributed pool enabled. Principal A
already has an in-flight run on worker 1. Principal A submits another run that lands on worker 2.
The second run is rejected. The first run continues. Principal A never has two active runs at once.

**Why this priority**: This is the hole 061 documented as process-local. Without it, scaling out
breaks the per-principal sequential invariant.

**Independent Test** (offline, no live cluster): two simulated workers share one ownership
collaborator. Start a run for A on worker 1; start a second run for A on worker 2 → rejected;
worker 1's run is unaffected.

**Acceptance Scenarios**:

1. **Given** the coordinator is enabled and principal A is in-flight on worker 1, **When** worker 2
   admits a run for A, **Then** the admit is rejected and worker 1 keeps the run.
2. **Given** principal A's run on worker 1 completes, fails, or is cancelled, **When** worker 2 then
   admits a run for A, **Then** the admit succeeds.

---

### User Story 2 - Two principals still run at the same time (Priority: P1)

With the coordinator enabled, principal A on worker 1 and principal B on worker 2 both proceed.
The unit must not introduce a global "one run for the whole process group" lock.

**Why this priority**: 061's reason to exist. Closing the cross-process hole must not undo
multi-principal concurrency.

**Independent Test**: two simulated workers, A on one and B on the other, both proceed; neither
waits for the other.

**Acceptance Scenarios**:

1. **Given** the coordinator is enabled, **When** A and B start runs on different workers,
   **Then** both proceed.
2. **Given** A is in-flight, **When** B starts a run on any worker, **Then** B is not rejected
   because of A.

---

### User Story 3 - Caps are global, not multiplied by worker count (Priority: P1)

An operator configures a per-principal in-flight cap and, when fairness is also enabled, an
outstanding-work quota. Those numbers are the cluster totals. Two workers do not grant two times
the cap.

**Why this priority**: Otherwise an operator who scales from 1 to N workers silently loosens
every tenant bound they already set.

**Independent Test**: configure cap = 1 (or a small outstanding-work quota). Fill it via worker 1.
A further admit on worker 2 is rejected. Completing the first work releases the cap for reuse on
either worker.

**Acceptance Scenarios**:

1. **Given** a per-principal in-flight cap of 1 and a run already in-flight on worker 1, **When**
   worker 2 admits another run for that principal, **Then** it is rejected as over cap.
2. **Given** fairness outstanding-work quota is configured and already full for a principal on
   worker 1, **When** worker 2 admits more outstanding work for that principal, **Then** the excess
   is rejected and does not enter that worker's local scheduler.
3. **Given** the occupying work completes, fails, or is cancelled, **When** either worker admits
   new work for that principal, **Then** the released cap can be reused.

---

### User Story 4 - Default off is byte-identical (Priority: P1)

Deployments that do not configure the coordinator keep today's 061/072 in-process behavior. Existing
single-worker tests stay green. Enabling the coordinator on a single worker does not change who may
run relative to 061/072; it only makes the same rules hold if a second worker appears.

**Why this priority**: Constitution X. Multi-worker safety is opt-in and must not tax single-process
hosts.

**Independent Test**: coordinator absent → existing tenant-host-pool and fairness suites unchanged.
Coordinator present with one simulated worker → 061/072 outcomes preserved.

**Acceptance Scenarios**:

1. **Given** no coordinator is configured (default), **When** the web/API host runs, **Then**
   behavior matches today's in-process pool (and fairness, if that is configured).
2. **Given** the coordinator is enabled with a single worker, **When** two principals run,
   **Then** 061/072 outcomes still hold (cross-principal concurrency; same-principal sequential;
   quota bounds).
3. **Given** the coordinator is enabled, **When** runtime events are emitted, **Then** event types,
   content shapes, termination reasons, and schema version are unchanged.

---

### User Story 5 - A dead worker does not pin a principal forever (Priority: P2)

A worker that holds a principal's ownership crashes or is killed. After the ownership grant expires
or is otherwise released, another worker may admit that principal. During the grant, no other worker
may start a second run. Expiry must not create a double-run with a worker that is actually still
alive.

**Why this priority**: Cross-process ownership without liveness is an outage (a principal stuck
until restart of the whole group). Liveness without fencing is a double-run.

**Independent Test**: grant ownership on worker 1; simulate worker 1 gone without a clean release;
after expiry, worker 2 admits successfully. Separately: worker 1 still alive past a stale clock →
worker 2 still rejected (no double-run).

**Acceptance Scenarios**:

1. **Given** worker 1 holds A and then disappears without a clean release, **When** the grant is
   no longer valid, **Then** worker 2 may admit A.
2. **Given** worker 1 still holds a valid grant for A, **When** worker 2 sees a stale or confusing
   clock, **Then** worker 2 still must not admit a second run for A.
3. **Given** ownership is released by completion, failure, cancellation, or expiry, **When** a
   later admit occurs, **Then** the previous grant cannot be reused (single-use of a released
   grant).

---

### User Story 6 - Many-writer ownership is not last-write-wins (Priority: P2)

Two workers try to take or release the same principal's ownership at the same time. One wins; the
other sees the loss. A release cannot vanish because another worker wrote a stale grant. Lost
updates are defects, not "eventual" behavior.

**Why this priority**: ADR 0009 deferred many-writer durability for this exact class of state.
A coordinator that drops a release re-creates the stuck-principal outage; one that drops a take
re-creates the double-run.

**Independent Test**: concurrent take from two simulated workers → exactly one success. Concurrent
release and take → no double-hold. A stale writer cannot resurrect a released grant.

**Acceptance Scenarios**:

1. **Given** A is free, **When** two workers take ownership concurrently, **Then** exactly one
   succeeds.
2. **Given** worker 1 holds A, **When** worker 1 releases and worker 2 takes concurrently,
   **Then** the resulting state is either "released then taken by 2" or "still held then released",
   never "held by both" and never "lost the release".
3. **Given** a grant was released, **When** a stale worker writes an old grant, **Then** that write
   does not restore ownership.

---

### Edge Cases

- Coordinator disabled (default): in-process 061/072 only; existing tests unchanged.
- Coordinator enabled, one worker: functionally equivalent to 061/072 for admit/reject.
- Coordinator configured but unreachable or raising: **fail-closed** — new admits rejected with a
  public-safe capacity/conflict response; in-flight work on a worker that already holds a grant
  continues; no silent fallback to uncoordinated in-process admits.
- Same principal, different model selections: ownership and in-flight caps remain **per principal**
  (matching 061's in-flight semaphore), not per `(principal, model)` host entry.
- Unauthenticated / missing principal: existing default-deny auth runs first; the coordinator is
  not a second identity system.
- Fairness disabled, coordinator enabled: global in-flight cap still holds; 072 outstanding-work
  quota is simply unused.
- Fairness enabled, coordinator enabled: outstanding-work quota is cluster-scoped at *admission*;
  fair turn interleaving among already-admitted work on one worker remains the 072 local scheduler.
- Worker restart with a still-valid grant: the restarted worker must not assume it still owns the
  principal; it re-takes or respects whoever holds the grant.
- Cancellation, client disconnect, or run failure: ownership and cap reservations release exactly
  once.
- Desktop / local CLI / single shared host (no pool): unchanged.
- File/SQLite vs a networked durable backend for the ownership store: File/SQLite remain
  single-process-honest (document loudly); a multi-process deployment that needs the invariant
  must use a backend the ADR names as cross-process-safe.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide an **opt-in cross-process ownership collaborator** layered **above** the
  existing per-principal host pool so more than one worker of the same web/API host can serve
  without breaking 061's per-principal sequential invariant.
- **FR-002**: The collaborator MUST be **default-off / byte-identical**. With no coordinator
  configured, the web/API host, `TenantHostPool`, and 072 fairness behave exactly as today.
- **FR-003**: When the coordinator is enabled, a principal MUST have **at most one in-flight run
  across the whole worker group**, unless the configured in-flight cap (already ≥ 1) explicitly
  allows more — and that cap is **cluster-scoped**, not per-worker.
- **FR-004**: Different principals MUST still be able to run **concurrently** on different workers.
  A single global lock over all principals is forbidden.
- **FR-005**: When 072 outstanding-work quota is also configured, that quota MUST be
  **cluster-scoped at admission**. Excess MUST be rejected and MUST NOT enter a worker's local
  scheduler. The 072 in-process fair *turn* scheduler MAY remain local to a worker for work that
  was already admitted.
- **FR-006**: Ownership and cap reservations MUST be released on completion, failure, cancellation,
  and grant expiry, exactly once, so a principal is not permanently blocked.
- **FR-007**: Preserve **pool-above-host** and each host's sequential `_active` invariant. This unit
  MUST NOT relax `LoopPlaneHost` to allow concurrent runs on one host (ADR 0009 D4 remains).
- **FR-008**: MUST NOT change tool resolution, authorization, or execution (Constitution V); MUST
  NOT change runtime event vocabulary, content blocks, termination reasons, or schema version
  (Constitution VI). Rejection uses existing public-safe capacity/conflict responses (the 061
  in-flight reject and/or the 072 `capacity exceeded` mapping — exact status chosen at plan).
- **FR-009**: Rejections and coordinator failures MUST be **public-safe**: no credentials, private
  paths, worker/host internals, queue depths, tenant ids beyond the already-authenticated caller,
  raw exceptions, or other principals' data.
- **FR-010**: When the coordinator cannot confirm ownership (timeout, error, unreachable store),
  a **new admit MUST fail closed**. It MUST NOT fall back to uncoordinated in-process admission.
- **FR-011**: Ownership records MUST be **many-writer safe**: concurrent take/release MUST NOT
  produce a double-hold or a lost release (US6).
- **FR-012**: A grant MUST have a **liveness bound** so a dead worker cannot pin a principal
  forever, without allowing a live holder to be overwritten into a double-run (US5).
- **FR-013**: Identity is the existing authenticated **principal id**. No second tenant namespace.
- **FR-014**: **No new required dependency or extra.** Discovering that one is needed is a GATE-§E
  stop. Optional reuse of an already-shipped extra is allowed only as the ADR records.
- **FR-015**: Desktop, local CLI, and the default single shared host (no pool) MUST remain
  behaviorally unchanged.
- **FR-016**: Cluster-wide fair *turn interleaving*, weighted tenant tiers, work stealing / live
  run migration, remote agent execution (G9), and Docker sandbox (G11) are **out of scope**.
- **FR-017**: Tests MUST be deterministic and offline: two (or more) simulated workers sharing the
  collaborator; no live multi-process cluster required for the default gate.
- **FR-018**: Existing 061 and 072 tests MUST pass with the coordinator absent. A focused suite
  MUST cover US1–US6, fail-closed admit, public-safety of reject paths, and default byte-identity.
- **FR-019**: Document rollback (Constitution X): removing the coordinator configuration restores
  pre-085 in-process behavior; no event/content/schema migration.
- **FR-020** (**plan FORK — maintainer consult**): ADR 0020 chooses the mechanism — **A shared
  ownership collaborator (recommended)** vs **B sticky routing only** vs **C new queue/lock extra**.
  Implementation MUST NOT start until the ADR is **Accepted**.
- **FR-021**: Final review MUST include both `code-reviewer` and `architecture-reviewer`.

### Key Entities *(include if feature involves data)*

- **Worker group**: The set of web/API workers that should share 061/072 serving guarantees. Not a
  new public identity; an operator deployment fact.
- **Principal ownership grant**: A cluster-scoped record that a principal's in-flight capacity is
  held: who holds it, until when, and how it is released. Opaque principal id only.
- **Cluster in-flight cap**: The 061 per-principal in-flight bound interpreted across the worker
  group rather than inside one process.
- **Cluster outstanding-work quota**: The 072 outstanding-work bound interpreted at admission
  across the worker group. Distinct from local fair-turn scheduling of already-admitted work.
- **Ownership collaborator**: The host-supplied seam the pool asks before admitting work when the
  coordinator is enabled. Absent → today's in-process path.
- **Ownership store**: Where grants live. In-memory default (single-process honest). A durable
  backend, if any, is an ADR 0020 decision and MUST be many-writer safe for that deployment mode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of covered two-worker / one-principal scenarios, a second concurrent run for
  that principal is rejected; the first run is unaffected.
- **SC-002**: In 100% of covered two-worker / two-principal scenarios, both principals proceed
  without waiting on each other.
- **SC-003**: In 100% of covered cap scenarios, in-flight and (when configured) outstanding-work
  bounds are not exceeded across the worker group; completing/failing/cancelling work releases the
  bound for reuse on any worker.
- **SC-004**: With the coordinator disabled, existing 061/072 and web/API behavior remains unchanged
  in all covered regression tests.
- **SC-005**: In 100% of covered coordinator-outage admit attempts, the new run is rejected
  (fail-closed); no uncoordinated second run starts.
- **SC-006**: In 100% of covered concurrent take/release scenarios, the result is never a
  double-hold and never a lost release.
- **SC-007**: Public-safety scans over changed artifacts find no credentials, private paths,
  internal worker details, raw backend errors, or other-tenant data leakage.
- **SC-008**: Rollback is removing the coordinator configuration: no data migration and no schema
  version change.

## Assumptions

- Reuses `TenantHostPool` and, when present, 072 fairness as the local scheduler. The new seam
  sits **above** those objects (Constitution IV), the same way 061 sits above `LoopPlaneHost`.
- Tests simulate multiple workers in one process by giving them a shared collaborator (or two
  collaborators over a shared store double). A live gunicorn/uvicorn cluster is not the default
  gate; an optional manual/ops note may describe it.
- File/SQLite ownership durability, if offered at all, is single-process-honest — the same honesty
  bar as File/SQLite ledger (062). Multi-worker production uses a backend ADR 0020 names as
  cross-process-safe, or it does not enable the coordinator.
- Load-balancer stickiness MAY be recommended in ops docs as a performance hint. It is never the
  enforcement mechanism.
- Outward HTTP paths stay the existing session/run routes. This unit maps coordinator rejects onto
  the existing public-safe capacity/conflict language; it does not add a new resource collection.
- Per Constitution IX the idea is borrowed from ordinary multi-worker admission control, not cloned
  from any private harness.

## Non-Goals

- Remote / cloud **agent execution** (gap G9). Children still run in the host that admitted the
  work. 079 remains remote *control*.
- Docker / container sandbox (gap G11) and Windows jail.
- Cluster-wide fair **turn** interleaving, weighted tenant tiers, or replacing 072's in-process
  scheduler.
- Live migration / work stealing of an in-flight run from one worker to another.
- External message queues, Redis, or other new extras unless the maintainer chooses fork C at ADR
  0020 (GATE-§E).
- Relaxing `LoopPlaneHost._active` or allowing concurrent runs on one host.
- Event-schema, content-model, checkpoint-record, or Gateway SPI changes.
- File/SQLite **ledger** cross-process atomicity (a separate P2 item in gap-analysis C4).
- Changing Desktop, local CLI, or Web UI presentation.
- A second identity or tenancy system.
