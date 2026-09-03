# Feature Specification: Cluster Fair Turn

**Feature Branch**: `086-cluster-fair-turn`

**Created**: 2026-09-03

**Status**: Draft — **R2 (cross-process scheduling)**. **ADR 0021 MUST be authored at plan and
approved by the maintainer before any implementation begins.** This unit extends ADR 0013
(in-process fair model-turn permits) and ADR 0020 (cluster admission). It does not supersede them
and does not replace 085 ownership grants.

**Depends on**: 085-distributed-host-pool (Verified), 072-platform-fairness (Verified),
061-tenant-host-pool (Verified).

**Input**: User description: "Close the remaining G20 fair-*turn* slice that 085 explicitly deferred.
085 made in-flight and outstanding-work *caps* cluster-scoped. 072's model-turn scheduler is still
process-local: a noisy tenant that already holds a grant on one worker can monopolize that worker's
model-call starts. 086 adds opt-in cluster-wide interleaving of *already-admitted* model turns so
two ready principals on two workers both make progress. Weighted tenant tiers, live run migration,
G9 remote execution, and G11 Docker remain out of scope."

---

## ⚠️ Boundary note (read first)

**This is an R2 unit.** It coordinates *when* already-admitted work may start a model turn across
workers. The gates are non-negotiable:

- **ADR 0021 at plan, approved before implementation** — not written retroactively. The ADR extends
  0013 (in-process fairness) and 0020 (cluster admission). It must not relax `LoopPlaneHost._active`,
  must not move tool execution / events out of the Gateway / Event Bus, and must not pull a
  serving-layer store into the Phase-1 runtime as a hard import.
- **No new required dependency.** Reusing an existing extra (for example `loopplane[postgres]`) is
  allowed only when the ADR says so. A new queue / lock extra is a **GATE-§E stop**.
- **Final review requires `code-reviewer` and `architecture-reviewer`.** The unit changes how the
  fairness collaborator obtains a turn permit (an exposed runtime/serving seam).

**The seam this grows from** (in-process today):

| Location | Today |
| -------- | ----- |
| `loopplane.fairness` `model_turn` | Per-process fair permit before `ModelBoundary.stream_turn`. |
| ADR 0013 D3 | Quota admission is separate from model-turn scheduling. |
| ADR 0013 D8 | Distributed fairness / cross-process scheduling deferred. |
| ADR 0020 | Cluster *admission* (who may start a run). Explicitly does **not** cluster-schedule turns. |
| 085 FR-016 | Cluster-wide fair turn interleaving is out of scope of 085. |

**Two facts that bound the design:**

1. **085 closed "who may run".** Two workers cannot double-run a principal or multiply caps. That
   is unchanged. This unit is about *already-admitted* work taking turns for the next model call.
2. **`model_turn` sits inside the agent loop.** The fairness object is a Phase-1 collaborator.
   Serving-layer stores (085 grants) live in webapi. Phase-1 MUST NOT import webapi. The plan ADR
   must keep that boundary: an injectable permit collaborator on fairness, not a store import.

**What this unit must never do**: execute a tool, emit a new event type, relax per-host sequential
execution, migrate a live run between workers, ship a message-queue product, replace 085 grants,
or make cluster turn coordination a `RuntimeConfig` default-on knob.

---

## Why this exists

An operator who enabled 085 can scale web/API workers without doubling tenant caps. They still
cannot promise that two admitted principals on two workers will *share model-call starts*. 072 only
sees waiters inside one process. A bursty tenant on worker 1 can take every local start while
principal B on worker 2 waits behind that worker's own (possibly empty) local queue — there is no
cross-worker view.

This unit is that missing view, and only that: **cluster-wide fair interleaving of model turns for
work that is already admitted.** It is not remote execution (G9), not a container sandbox (G11),
and not live migration.

---

## Specify-time defaults (not open questions)

These are the informed defaults used to write a complete spec. They may be confirmed or overridden
at plan when ADR 0021 is authored. They are **not** `[NEEDS CLARIFICATION]` markers.

| Topic | Default | Why this is the default |
| ----- | ------- | ----------------------- |
| Slice | **Cluster-wide fair *turn* permits for already-admitted work.** Weighted tiers and live migration stay deferred. | Matches the 061 → 072 → 085 slicing: one independently testable G20 remaining slice. |
| Mechanism | **Injectable turn-permit collaborator on the existing fairness object** (recommended ADR fork). In-memory default = single-process equivalent. Durable backend optional and reuse-first. | Keeps Phase-1 free of webapi imports. Sticky routing cannot interleave starts. A new queue extra is GATE-§E. |
| Surfaces | **Web/API serving path when 072 fairness is also configured.** Desktop and local CLI stay single-process. | Only the web/API host is scaled as multiple workers. Fair-turn without 072 is a no-op (no local scheduler to extend). |
| Failure | **Degrade to local 072 scheduling if a cluster turn permit cannot be confirmed.** Already-admitted work MUST NOT wedge. | A false admit (085) is a double-run. A missed cluster turn is unfairness, not a double-run. Availability of in-flight work wins over perfect fairness during a control-plane outage. |
| Identity | **Existing principal id.** Same tenant key as 072 / 085. | ADR 0013 D4. |
| Relation to 085 | **Orthogonal.** Cluster turn permits do not replace ownership grants. Admission remains 085. | 085 FR-016; ADR 0020 consequences. |

**Plan FORK (maintainer consult, recorded as FR-020):**

- **A (recommended): injectable turn-permit collaborator** supplied to the existing fairness
  object. Phase-1 defines the permit Protocol; webapi (or the host) supplies the in-memory /
  optional durable implementation. 072 local scheduling remains defense in depth.
- **B: count starts only in the serving layer** — rejected as the sole mechanism; the loop would
  still take local turns without a cluster view, which is today's hole.
- **C: new external queue / lock extra** — GATE-§E; only if the maintainer explicitly chooses it.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two admitted principals both make model-turn progress (Priority: P1)

An operator runs two workers with cluster admission (085) and fairness (072) enabled, and this
unit's cluster turn collaborator on. Principal A is admitted on worker 1 and principal B on
worker 2. Both are ready for a model call. A's burst of turns does not starve B: B obtains model
starts without waiting for A to finish its entire burst on the other worker.

**Why this priority**: This is the hole 085 documented as remaining. Caps without turn
interleaving still let a noisy neighbor monopolize *starts*.

**Independent Test** (offline, no live cluster): two simulated workers share one turn-permit
collaborator. A and B are both admitted and ready. Over a burst of starts, both principals obtain
at least one start; A cannot take every start while B is ready.

**Acceptance Scenarios**:

1. **Given** the collaborator is enabled and A and B are both admitted and ready for a model turn,
   **When** a burst of starts occurs across two workers, **Then** both A and B obtain at least one
   start.
2. **Given** only A is ready, **When** A takes successive model turns, **Then** A is not blocked
   waiting for an absent B.

---

### User Story 2 - Default off is byte-identical (Priority: P1)

Deployments that do not configure the cluster turn collaborator keep today's 072 in-process
scheduler (and 085 admission, if that is configured). Existing fairness and admission tests stay
green.

**Why this priority**: Constitution X. Multi-worker turn fairness is opt-in.

**Independent Test**: collaborator absent → existing 072 and 085 suites unchanged.

**Acceptance Scenarios**:

1. **Given** no cluster turn collaborator is configured (default), **When** the web/API host runs
   with 072 fairness, **Then** model-turn scheduling matches today's in-process behaviour.
2. **Given** the collaborator is enabled with a single worker, **When** two principals take model
   turns, **Then** 072 outcomes still hold (no starvation inside that process; quota bounds
   unchanged).
3. **Given** the collaborator is enabled, **When** runtime events are emitted, **Then** event types,
   content shapes, termination reasons, and schema version are unchanged.

---

### User Story 3 - 085 admission is unchanged (Priority: P1)

This unit does not decide who may start a run. A principal still cannot double-run across workers.
Outstanding-work caps remain cluster-scoped at admission. Fair turns apply only to work that
already holds a grant (when 085 is on) or that 072 already admitted locally (when 085 is off and
this collaborator is nonetheless supplied in-process).

**Why this priority**: 086 must not weaken 085. Mixing grant take with turn permits would re-open
double-runs.

**Independent Test**: with 085 enabled, two workers, one principal, in-flight cap 1 → second run
still rejected. Cluster turn collaborator on or off does not change that.

**Acceptance Scenarios**:

1. **Given** 085 admission is enabled and principal A is in-flight on worker 1, **When** worker 2
   admits a run for A, **Then** the admit is still rejected (085 behaviour).
2. **Given** A and B are both admitted, **When** cluster turns are scheduled, **Then** neither
   principal's ownership grant is released or stolen as a side effect of a turn permit.

---

### User Story 4 - Different principals still run at the same time (Priority: P1)

Fair turn interleaving MUST NOT introduce a global "one model call for the whole worker group"
lock that serializes unrelated principals beyond the fairness policy. Two principals may hold
concurrent model calls up to the existing 072 active-call bound, interpreted consistently with
the ADR.

**Why this priority**: 061/072's reason to exist. Closing the noisy-neighbor hole must not
re-serialize the deployment.

**Independent Test**: two simulated workers, A and B both admitted; both may be in a model turn
when the configured active-call bound allows it; neither waits on a global single-flight lock
unless that bound is 1.

**Acceptance Scenarios**:

1. **Given** the collaborator is enabled and the active-call bound allows two, **When** A and B
   start model turns on different workers, **Then** both may proceed.
2. **Given** the configured bound is 1, **When** A holds a model turn, **Then** B waits for a
   permit and proceeds after A releases — not by stealing A's turn.

---

### User Story 5 - Control-plane outage does not wedge in-flight work (Priority: P2)

A worker already driving an admitted run cannot confirm a cluster turn permit (timeout, error,
unreachable store). The run MUST continue using the local 072 scheduler rather than hang until
the collaborator returns. Perfect cluster fairness is not required during an outage.

**Why this priority**: 085 fail-closes *new admits* because a false admit is a double-run. A missed
cluster *turn* is unfairness. Wedging an already-accepted session is worse.

**Independent Test**: collaborator raises or times out during `model_turn`; the run still obtains a
local 072 permit and completes; no new event type.

**Acceptance Scenarios**:

1. **Given** a run is already admitted and the cluster turn collaborator fails, **When** the next
   model turn is requested, **Then** the local 072 scheduler still grants or waits as today and the
   run does not hang indefinitely on the cluster collaborator.
2. **Given** the collaborator recovers, **When** later turns occur, **Then** cluster interleaving
   resumes without a schema or grant migration.

---

### Edge Cases

- Collaborator disabled (default): 072 local scheduler only; existing tests unchanged.
- Collaborator enabled, 072 fairness absent: no-op (nothing to extend); 085 admission if present
  still applies.
- Collaborator enabled, one worker: functionally equivalent to 072 for turn ordering.
- 085 off, collaborator on: in-process-only cluster view (tests may share one collaborator object
  across two simulated workers without 085 grants).
- Same principal, successive turns on one worker: not starved by an absent other principal.
- Unauthenticated / missing principal: existing auth runs first; this is not a second identity
  system.
- Cancellation, client disconnect, or run failure: any held turn permit releases exactly once.
- Desktop / local CLI / single shared host: unchanged.
- Weighted tiers requested by an operator: out of scope; equal principals.
- Live migration of an in-flight run: forbidden.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide an **opt-in cluster turn-permit collaborator** so already-admitted work on
  more than one web/API worker interleaves model-turn starts fairly by principal.
- **FR-002**: The collaborator MUST be **default-off / byte-identical**. With none configured, 072
  and 085 behave exactly as today.
- **FR-003**: When enabled, a ready principal MUST NOT be starved of model-turn starts by another
  ready principal's burst on a different worker. Equal principals; no weights in this unit.
- **FR-004**: Different principals MUST still be able to hold concurrent model turns up to the
  existing 072 active-call policy. A single global lock over all principals is forbidden unless
  that policy's bound is 1.
- **FR-005**: Cluster turn permits MUST NOT replace, steal, or loosen 085 ownership grants or
  cluster admission caps.
- **FR-006**: Turn permits MUST be released on turn completion, failure, cancellation, and
  collaborator expiry, exactly once.
- **FR-007**: Preserve **pool-above-host** and each host's sequential `_active` invariant. This unit
  MUST NOT relax `LoopPlaneHost` concurrent runs (ADR 0009 D4 remains).
- **FR-008**: MUST NOT change tool resolution, authorization, or execution (Constitution V); MUST
  NOT change runtime event vocabulary, content blocks, termination reasons, or schema version
  (Constitution VI).
- **FR-009**: Public-safe: no credentials, private paths, worker internals, queue depths, other
  principals' data, or raw exceptions in user-visible failures.
- **FR-010**: If a cluster turn permit cannot be confirmed, **already-admitted work MUST degrade to
  the local 072 scheduler** (no indefinite hang). This is deliberately different from 085
  fail-closed *new admits*.
- **FR-011**: Identity is the existing authenticated **principal id**.
- **FR-012**: **No new required dependency or extra.** Discovering that one is needed is a GATE-§E
  stop. Optional reuse of an already-shipped extra is allowed only as the ADR records.
- **FR-013**: Desktop, local CLI, and the default single shared host MUST remain behaviourally
  unchanged.
- **FR-014**: Weighted tenant tiers, live run migration / work stealing, remote agent execution
  (G9), and Docker sandbox (G11) are **out of scope**.
- **FR-015**: Tests MUST be deterministic and offline: two (or more) simulated workers sharing the
  collaborator; no live multi-process cluster required for the default gate.
- **FR-016**: Existing 061, 072, and 085 tests MUST pass with the collaborator absent.
- **FR-017**: Document rollback (Constitution X): removing the collaborator restores pre-086
  in-process scheduling; no event/content/schema migration.
- **FR-018** (**plan FORK — maintainer consult**): ADR 0021 chooses the mechanism — **A injectable
  turn-permit collaborator on fairness (recommended)** vs **B serving-layer start counting only**
  vs **C new queue/lock extra**. Implementation MUST NOT start until the ADR is **Accepted**.
- **FR-019**: Final review MUST include both `code-reviewer` and `architecture-reviewer`.
- **FR-020**: Phase-1 fairness MUST NOT import the webapi serving layer. The permit implementation
  is injected; the loop only sees the fairness public surface.

### Key Entities *(include if feature involves data)*

- **Cluster turn permit**: An ephemeral right for a principal to start one model turn. Not a
  session record, not a checkpoint, not an 085 ownership grant.
- **Turn-permit collaborator**: Host-supplied seam the fairness object asks before granting a
  model turn when this unit is enabled. Absent → today's 072 path.
- **Ready principal**: An already-admitted principal whose run is waiting to start or continue a
  model call.
- **Worker group**: The same deployment fact as 085; not a new public identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of covered two-worker / two-ready-principal burst scenarios, both principals
  obtain at least one model-turn start; one principal cannot take every start while the other is
  ready.
- **SC-002**: In 100% of covered 085 admission scenarios, enabling this collaborator does not allow
  a second in-flight run for a principal already at cap.
- **SC-003**: With the collaborator disabled, existing 061/072/085 behaviour remains unchanged in
  all covered regression tests.
- **SC-004**: In 100% of covered collaborator-outage scenarios during an already-admitted run, the
  run still progresses via local scheduling and does not hang indefinitely for a cluster permit.
- **SC-005**: In 100% of covered concurrent permit take/release scenarios, the result is never a
  leaked permit and never a stolen in-flight turn from a live holder.
- **SC-006**: Public-safety scans over changed artifacts find no credentials, private paths,
  internal worker details, raw backend errors, or other-tenant data leakage.
- **SC-007**: Rollback is removing the collaborator configuration: no data migration and no schema
  version change.

## Assumptions

- Reuses 072 fairness as the in-process scheduler (defense in depth) and, when present, 085
  admission as the run-start gate. This unit sits **beside** those objects for *turns*, not in
  front of `host.run` for *admits*.
- Tests simulate multiple workers in one process by sharing one collaborator. A live
  gunicorn/uvicorn cluster is not the default gate.
- "Fair" in this unit means **no starvation among equal, ready principals**, not weighted shares
  and not perfect global round-robin of every start.
- Load-balancer stickiness MAY remain an ops hint. It is never the fairness mechanism.
- Outward HTTP paths stay the existing session/run routes. This unit does not add a resource
  collection and does not invent a new public error phrase unless mapping onto an existing
  072 wait/reject is insufficient (ADR 0021 decides; default is: waiting is internal, no new
  HTTP status).
- Per Constitution IX the idea is borrowed from ordinary multi-tenant scheduling, not cloned from
  any private harness.

## Non-Goals

- Remote / cloud **agent execution** (gap G9).
- Docker / container sandbox (gap G11) and Windows jail.
- Weighted tenant tiers.
- Live migration / work stealing of an in-flight run.
- Replacing or loosening 085 ownership grants.
- External message queues, Redis, or other new extras unless the maintainer chooses fork C at ADR
  0021 (GATE-§E).
- Relaxing `LoopPlaneHost._active`.
- Event-schema, content-model, checkpoint-record, or Gateway SPI changes.
- Changing Desktop, local CLI, or Web UI presentation.
- A second identity or tenancy system.
