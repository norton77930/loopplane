# Feature Specification: Scheduler & Trigger Engine

**Feature Branch**: `004-loopplane-scheduler-trigger-engine`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Define the Scheduler & Trigger Engine layer (unit 004) on top of the
completed Loop Engineering Layer (003), the Host Interface (002), and the Runtime Foundation (001).
This phase turns the Phase-3 trigger contracts (ManualTrigger implemented; IntervalTrigger and
ConditionTrigger defined as host-driven contracts only) into usable local scheduling and condition-watch
behavior, all driving Loop Runs exclusively through the Phase-3 manual entry point (run_loop). In scope:
a local in-process Scheduler, an executable interval trigger driver (virtual clock, no real sleeping), an
executable condition trigger driver, a manual trigger registry, Trigger State, a missed-run policy, and
scheduler lifecycle. Reserved (named, not built): distributed/durable queue, multi-process scheduling,
persistent trigger state, cron parsing, background OS daemon. Out of scope: distributed queue/worker
systems, cloud deployment, web/UI, multi-user tenancy, cron syntax, wall-clock guarantees. Public-safe
and English. Determinism is mandatory under a virtual clock."

## Feature Overview

LoopPlane's third phase delivered the **Loop Engineering Layer** — an outer control loop that defines a
loop, validates and evaluates each iteration, retries, repairs, and stops, driving every Agent Run
through the Phase-2 Host Application Interface (see
[`../003-loopplane-loop-engineering-layer/spec.md`](../003-loopplane-loop-engineering-layer/spec.md)).
That phase implemented a **manual trigger** and deliberately left **interval** and **condition** triggers
as *contracts only* — host-drivable shapes with no executable scheduler — and named a production
scheduler as a reserved extension point.

Phase 4 builds the local, in-process **Scheduler & Trigger Engine** that makes those trigger contracts
executable. It introduces a **Scheduler** that owns registered triggers, an injectable **Clock**, an
**Interval trigger driver** and a **Condition trigger driver**, a **Manual trigger registry**,
per-trigger **Trigger State**, a **Missed-run policy**, and a scheduler **lifecycle**. Every Loop Run the
scheduler starts goes through the **Phase-3 manual entry point (`run_loop`)** — the scheduler never
bypasses the loop layer and never reaches into Phase-1/2 internals. It adds no distributed queue, no
persistence, no cron parsing, and no OS daemon; those are named reserved extension points.

This phase keeps the single-process, single-in-flight-Loop-Run posture of Phase 3: the Scheduler
serializes the Loop Runs it starts (one at a time) unless a host explicitly opts into its own
concurrency. Determinism is mandatory — with an injected virtual clock and scripted loops, the scheduler
produces an identical trigger-firing order and identical outcomes on every run, with no real sleeping or
wall-clock dependency in tests.

### Core Distinctions

This phase adds a scheduling layer that sits **above** the loop layer, not inside it. The following
distinctions are normative — every requirement below preserves them.

| # | Phase-3 concept (loop) | Phase-4 concept (scheduler) |
|---|---|---|
| 1 | **Trigger** — a declarative shape: `ManualTrigger` (executable) plus `IntervalTrigger` / `ConditionTrigger` *contracts* with no executor. | **Trigger Driver** — the executable that enacts a trigger by deciding *when* to start a Loop Run and calling `run_loop` for it. |
| 2 | **`run_loop`** — the manual entry point that runs exactly one Loop Run to a terminal outcome (or human-review pause). | **Scheduler** — owns a registry of triggers and a clock, decides which trigger fires next, and starts each Loop Run **only** by calling `run_loop`. |
| 3 | **Loop Run** — one execution of a Loop Definition. | **Scheduled Loop Run** — a Loop Run started by the Scheduler from a registered trigger, recorded against that trigger's Trigger State. |
| 4 | **Loop State** — the in-process record of one Loop Run, reconstructable from Loop Events. | **Trigger State** — the in-process record of one *registered trigger* (last fired, next due, fire count, enabled), reconstructable from Scheduler Events. |
| 5 | — | **Clock** — an injectable time source; a virtual clock advances deterministically in tests, a real clock is used in production, with identical scheduler decisions. |

**Implemented this phase vs reserved extension points**:

- **Implemented**: Scheduler with a trigger registry, an injectable Clock, an executable interval driver,
  an executable condition driver, a manual trigger registry, in-process Trigger State, a missed-run
  policy (skip / catch-up-once / coalesce), scheduler lifecycle (start / stop / pause / resume / drain),
  serialized single-in-flight Loop Runs, and `run_loop`-only invocation.
- **Reserved (named, not built)**: a distributed or durable queue, multi-process or cross-host
  scheduling, persistent Trigger State across process restarts, cron-expression parsing, and a background
  OS daemon.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register and start loops through a manual registry (Priority: P1)

A scheduler user registers one or more Loop Definitions under stable trigger ids in the **Scheduler**,
then starts a named loop on demand. The Scheduler starts exactly one **Scheduled Loop Run** by calling
the Phase-3 `run_loop` for that definition, records the run against the trigger's **Trigger State**
(incrementing its fire count and last-fired time from the injected **Clock**), and returns the loop
outcome — without the scheduler touching any Phase-1/2 internal or bypassing the loop layer.

**Why this priority**: This is the minimum viable scheduler and the foundation every other trigger type
builds on. A registry that can start a registered loop through `run_loop` and track its Trigger State is
the smallest useful unit and is independently demonstrable with a scripted loop and a fake clock.

**Independent Test**: Register a Loop Definition under a trigger id, start it by id, and assert exactly
one `run_loop` was invoked for that definition, that Trigger State records one fire with the clock's
time, and that the returned outcome is the loop's terminal outcome.

**Acceptance Scenarios**:

1. **Given** a Scheduler with a registered manual trigger over a scripted loop, **When** the user starts
   that trigger by id, **Then** the Scheduler starts exactly one Loop Run through `run_loop` and returns
   its terminal outcome.
2. **Given** the same Scheduler, **When** the trigger fires, **Then** its Trigger State records the fire
   count, the last-fired time from the injected Clock, and a reference to the started Loop Run.
3. **Given** an unregistered trigger id, **When** the user starts it, **Then** the Scheduler raises a
   clear, public-safe error and starts no Loop Run.
4. **Given** a registered trigger, **When** a boundary audit inspects how the Loop Run was started,
   **Then** it confirms the run was started only through `run_loop` and no Phase-1/2 internal was called.

---

### User Story 2 - Drive an interval trigger on a virtual clock (Priority: P2)

A scheduler user registers an **interval trigger** ("start this loop every N time units"). The
**Interval trigger driver** computes each next-due time from the **Clock** and, as the Scheduler's clock
advances, fires the loop at each due tick by calling `run_loop`. In tests a **virtual clock** advances
deterministically, so the firing order and count are exact with no real sleeping or wall-clock
dependency.

**Why this priority**: Interval scheduling is the first executable trigger contract and the most common
recurring-loop need. It builds on the registry in User Story 1 and is the proof that the Phase-3 interval
*contract* is now executable.

**Independent Test**: Register an interval trigger, advance a virtual clock across several intervals, and
assert the loop fired exactly once per elapsed interval, that next-due times advance by the interval, and
that two identical runs over the same clock script produce identical firing sequences.

**Acceptance Scenarios**:

1. **Given** an interval trigger of period P over a scripted loop, **When** the virtual clock advances by
   3P, **Then** the loop fires exactly three times through `run_loop`, at the three due ticks.
2. **Given** the same interval trigger, **When** it fires, **Then** Trigger State's next-due time
   advances by exactly one period and the fire count increments by one.
3. **Given** two schedulers driven by identical virtual-clock scripts, **When** each runs, **Then** both
   produce identical firing sequences and identical Loop outcomes (determinism).
4. **Given** an interval trigger configured to start immediately, **When** the scheduler starts, **Then**
   the loop fires once at time zero and then every period thereafter.

---

### User Story 3 - Drive a condition trigger from a host predicate (Priority: P3)

A scheduler user registers a **condition trigger** with a host-supplied predicate. The **Condition
trigger driver** evaluates the predicate on demand or on each polling tick; when the predicate becomes
satisfied, it starts one Loop Run through `run_loop`. The predicate is host logic; the driver only
decides *that it is time* and delegates the run to the loop layer.

**Why this priority**: Condition-based starts are the second executable trigger contract and cover
event/state-driven loops. It builds on the registry and the polling/clock machinery and keeps predicate
logic on the host side (no in-runtime watcher).

**Independent Test**: Register a condition trigger whose scripted predicate flips from false to true at a
known tick; poll across ticks and assert the loop fires only on the satisfied ticks and not before, with
the firing order deterministic.

**Acceptance Scenarios**:

1. **Given** a condition trigger whose predicate is false, **When** the driver evaluates it, **Then** no
   Loop Run starts.
2. **Given** a condition trigger whose predicate becomes true at a tick, **When** the driver evaluates it
   at that tick, **Then** exactly one Loop Run starts through `run_loop`.
3. **Given** a condition trigger configured to fire once per satisfied edge, **When** the predicate stays
   true across several ticks, **Then** the loop fires only on the rising edge, not on every tick.
4. **Given** a predicate that raises, **When** the driver evaluates it, **Then** the error is surfaced as
   a diagnostic and the Scheduler continues; it never crashes the scheduler or starts a spurious run.

---

### User Story 4 - Track Trigger State and apply a missed-run policy (Priority: P4)

A scheduler user relies on **Trigger State** to know each trigger's last-fired time, next-due time, fire
count, and enabled/disabled status, and configures a **missed-run policy** that governs what happens when
the clock jumps past one or more due ticks: **skip** (run only the next due tick), **catch-up-once** (run
a single make-up Loop Run), or **coalesce** (collapse all missed ticks into one run). Trigger State is
reconstructable from the Scheduler Event stream, like Loop State.

**Why this priority**: Trigger State and the missed-run policy make scheduling observable and correct
under clock jumps. They build on the interval driver and are where recurring-schedule correctness is
enforced concretely.

**Independent Test**: Advance a virtual clock past several due ticks in one jump and assert the number of
Loop Runs started matches the configured missed-run policy (skip → 1, catch-up-once → 1 make-up, coalesce
→ 1), and that Trigger State's counters reflect the policy.

**Acceptance Scenarios**:

1. **Given** an interval trigger with the **skip** policy and a clock that jumps past 3 due ticks, **When**
   the scheduler processes the jump, **Then** it starts exactly one Loop Run (the next due) and advances
   next-due past the jump.
2. **Given** the **catch-up-once** policy and the same jump, **When** the scheduler processes it, **Then**
   it starts exactly one make-up Loop Run and records the missed-tick count in Trigger State.
3. **Given** the **coalesce** policy and the same jump, **When** the scheduler processes it, **Then** it
   collapses the missed ticks into a single Loop Run and resets next-due relative to the current time.
4. **Given** any policy, **When** ticks are missed, **Then** Trigger State remains reconstructable from
   the Scheduler Event stream alone and never loses the fire count.

---

### User Story 5 - Control the scheduler lifecycle and keep its edges honest (Priority: P5)

A scheduler user **starts** and **stops** the Scheduler, **pauses** and **resumes** individual triggers,
and **drains** the Scheduler so an in-flight Loop Run completes before shutdown. A paused trigger fires no
Loop Runs until resumed; a stopped Scheduler starts nothing; and the Scheduler serializes the Loop Runs
it starts (one at a time) so it never starts a second Loop Run while one is in flight, consistent with
the Phase-3 single-in-process-Loop-Run constraint. The interval and condition *execution*, durable
Trigger State, cron parsing, multi-process scheduling, and a distributed queue remain named, unbuilt
extension points.

**Why this priority**: Lifecycle control and the serialization/extension-point edges define what the
phase commits to versus what it reserves. They depend on the trigger machinery in Stories 1–4 and keep
the phase's scope honest.

**Independent Test**: Pause a trigger and assert it fires nothing while paused and resumes firing after
resume; drain the Scheduler mid-schedule and assert the in-flight Loop Run completes and no new run
starts; and assert that two due triggers never run concurrently.

**Acceptance Scenarios**:

1. **Given** a registered trigger, **When** it is paused and the clock advances past due ticks, **Then**
   no Loop Run starts until the trigger is resumed.
2. **Given** a running Scheduler with an in-flight Loop Run, **When** another trigger becomes due, **Then**
   its Loop Run is serialized after the in-flight one — never started concurrently.
3. **Given** a Scheduler asked to **drain**, **When** drain is requested, **Then** the in-flight Loop Run
   completes, no further Loop Runs start, and the Scheduler reports a clean stop.
4. **Given** a stopped Scheduler, **When** a trigger would be due, **Then** no Loop Run starts and the
   trigger's next-due is unchanged.

---

### Edge Cases

- The clock jumps backward (non-monotonic source): the Scheduler ignores the regression for due
  calculations and never fires a negative number of runs or double-fires a tick.
- Two triggers are due at the same tick: the Scheduler fires them in a deterministic, documented order
  (for example, by registration order) and serializes their Loop Runs.
- A registered loop's `run_loop` pauses for human review: the Scheduler records the paused outcome in
  Trigger State and does not treat the pause as a completed fire for catch-up purposes.
- An interval period of zero or negative is rejected at registration with a clear error.
- A condition predicate that is always true with an edge-only policy fires once; with an every-tick
  policy it fires every poll — both are explicit choices, not accidents.
- The Scheduler is stopped while a trigger is mid-evaluation: no Loop Run is started and no Trigger State
  is corrupted.
- A trigger is unregistered while due: it is removed cleanly and starts no further Loop Runs.

## Requirements *(mandatory)*

### Functional Requirements

#### Scheduler & Registry

- **FR-001**: The layer MUST provide a local, in-process **Scheduler** that owns a registry of triggers,
  each registered under a stable **trigger id** with a Loop Definition and a trigger configuration
  (manual, interval, or condition).
- **FR-002**: The Scheduler MUST start every Loop Run **only** by calling the Phase-3 manual entry point
  `run_loop`; it MUST NOT bypass the loop layer, drive sessions directly, or call any Phase-1/2 internal.
- **FR-003**: The Scheduler MUST return or surface the loop outcome of each Scheduled Loop Run and record
  it against the firing trigger's Trigger State.
- **FR-004**: Registering, looking up, enabling, disabling, and unregistering a trigger by id MUST be
  supported and MUST validate inputs (unknown id, duplicate id, invalid configuration) with clear,
  public-safe errors.

#### Clock

- **FR-010**: The Scheduler MUST depend on an injectable **Clock** abstraction (a monotonic time source)
  rather than the wall clock directly, so a **virtual clock** can drive deterministic tests with no real
  sleeping.
- **FR-011**: All due-time and next-due calculations MUST derive from the injected Clock; given identical
  clock advancement, scheduler decisions MUST be identical (determinism).
- **FR-012**: The layer MUST NOT require a real sleeping loop or wall-clock dependency in tests; advancing
  the virtual clock MUST be sufficient to drive every trigger.

#### Manual Trigger Registry

- **FR-020**: The layer MUST implement a **manual trigger registry**: a host registers a Loop Definition
  under a trigger id and starts it on demand by id, producing exactly one Scheduled Loop Run.
- **FR-021**: Starting a manual trigger MUST be synchronous from the host's perspective (it returns the
  loop outcome) and MUST update Trigger State (fire count, last-fired time).

#### Interval Trigger Driver

- **FR-030**: The layer MUST implement an executable **interval trigger driver** that starts a Loop Run
  every configured period, computing each next-due time from the Clock.
- **FR-031**: As the Clock advances, the driver MUST fire the loop once per elapsed due tick (subject to
  the missed-run policy, FR-050) and advance next-due by exactly one period per fire.
- **FR-032**: An interval trigger MAY be configured to **start immediately** (fire once at registration/
  start time) or to wait one full period before the first fire.
- **FR-033**: A non-positive interval period MUST be rejected at registration with a clear error.

#### Condition Trigger Driver

- **FR-040**: The layer MUST implement an executable **condition trigger driver** that evaluates a
  host-supplied predicate on demand or on each polling tick and starts a Loop Run when the predicate is
  satisfied.
- **FR-041**: The condition trigger MUST support an **edge** mode (fire only on the false→true rising
  edge) and a **level** mode (fire on every satisfied poll), as an explicit configuration.
- **FR-042**: A predicate that raises MUST be surfaced as a diagnostic and MUST NOT crash the Scheduler or
  start a spurious Loop Run; evaluation continues on the next tick.
- **FR-043**: The predicate is host logic; the layer MUST NOT implement an in-runtime event watcher or
  background condition daemon (FR-091).

#### Trigger State

- **FR-050**: The layer MUST maintain in-process **Trigger State** per registered trigger carrying: the
  trigger id, last-fired time, next-due time (where applicable), fire count, missed-tick count,
  enabled/disabled status, and a reference to the most recent Scheduled Loop Run.
- **FR-051**: Trigger State MUST reference Loop Runs by identifier/reference only and MUST NOT copy or own
  Loop State or run history.
- **FR-052**: Trigger State MUST be reconstructable from the ordered **Scheduler Event** stream together
  with the referenced loop outcomes; durable cross-restart persistence is reserved, not built (FR-091).

#### Missed-Run Policy

- **FR-060**: The layer MUST support a per-trigger **missed-run policy** with at least three modes:
  **skip** (run only the next due tick), **catch-up-once** (run a single make-up Loop Run), and
  **coalesce** (collapse all missed ticks into one Loop Run).
- **FR-061**: When the Clock advances past multiple due ticks at once, the Scheduler MUST start the number
  of Loop Runs dictated by the policy and update next-due and the missed-tick count accordingly.
- **FR-062**: The missed-run policy MUST never cause unbounded catch-up firing; the number of make-up runs
  per clock advance MUST be bounded by the policy (at most one for skip / catch-up-once / coalesce).

#### Scheduler Lifecycle & Serialization

- **FR-070**: The Scheduler MUST support **start**, **stop**, **pause** (a single trigger), **resume** (a
  single trigger), and **drain** (let the in-flight Loop Run finish, start no new runs, then stop cleanly).
- **FR-071**: A **paused** trigger MUST start no Loop Runs until resumed; a **stopped** Scheduler MUST
  start nothing and MUST leave next-due times unchanged.
- **FR-072**: The Scheduler MUST **serialize** the Loop Runs it starts — at most one Scheduled Loop Run in
  flight at a time — consistent with the Phase-3 single-in-process-Loop-Run constraint, unless a host
  explicitly opts into its own concurrency.
- **FR-073**: When multiple triggers are due at the same tick, the Scheduler MUST fire them in a
  deterministic, documented order and serialize their Loop Runs.

#### Scheduler Events

- **FR-080**: The layer MUST emit a **Scheduler Event** stream (distinct from Loop Events and Runtime
  Events) recording trigger registration, fire, skip/catch-up/coalesce, pause/resume, and stop, each
  carrying the trigger id and the Clock time.
- **FR-081**: Scheduler Events MUST be emitted in deterministic order and MUST be sufficient to
  reconstruct Trigger State (FR-052). Observation of Scheduler Events MUST default off and add zero
  behavior change when disabled.

#### Boundary, Non-Duplication & Extension Points

- **FR-090**: The layer MUST NOT implement or duplicate any Phase-1 runtime internal, any Phase-2
  host-assembly internal, or any Phase-3 loop-control internal; it MUST start Loop Runs only through the
  Phase-3 `run_loop` entry point and MUST NOT re-implement validation, retry, repair, evaluation, or the
  loop lifecycle.
- **FR-091**: The layer MUST name, without implementing, the reserved extension points: a distributed or
  durable queue, multi-process or cross-host scheduling, persistent Trigger State across restarts,
  cron-expression parsing, and a background OS daemon.
- **FR-092**: The layer MUST NOT implement any out-of-scope product or platform layer — distributed queue
  or worker system, cloud deployment, web/UI, multi-user tenancy, cron syntax, or any real-time/wall-clock
  guarantee. Any such need discovered during implementation MUST be deferred to a future-phase
  specification.

### Non-Functional Requirements

- **NFR-001 (Phase dependency)**: This phase MUST build strictly on the completed Phase-1 runtime, the
  Phase-2 host interface, and the Phase-3 loop layer, and inherit their guarantees rather than re-deriving
  them; it consumes the loop layer only through the public `run_loop` entry point.
- **NFR-002 (Determinism)**: Given an injected virtual clock and scripted loops/predicates, the Scheduler
  MUST produce the same trigger-firing order, the same number of Loop Runs, and the same outcomes on every
  run.
- **NFR-003 (Boundary integrity)**: It MUST be auditable that the Scheduler starts Loop Runs only through
  `run_loop` and invokes no Phase-1/2/3 internal directly (operationalized by FR-002, FR-090, SC-002).
- **NFR-004 (Public-safety)**: All committed Phase-4 artifacts MUST remain public-safe — no secrets,
  credentials, private paths, private project or repository names, or internal network addresses — and no
  raw private-reference excerpts.
- **NFR-005 (Observability parity)**: Scheduler observation MUST default off and add zero behavior change
  when disabled; enabling it MUST NOT alter scheduling decisions or outcomes.
- **NFR-006 (Minimalism & reversibility)**: The layer MUST stay minimal and independently reversible, with
  no speculative product surface, consistent with the constitution's harness-before-automation principle
  and surgical-scope discipline.

### Key Entities

- **Scheduler**: The in-process owner of the trigger registry and the Clock; it decides which trigger
  fires next and starts each Loop Run through `run_loop`. Owns no runtime, host, or loop internals.
- **Trigger Registration**: A stable trigger id bound to a Loop Definition and a trigger configuration
  (manual, interval, or condition) plus a missed-run policy.
- **Trigger Driver**: The executable that enacts a trigger — manual (start on demand), interval (fire per
  period), or condition (fire on a satisfied predicate).
- **Clock**: The injectable monotonic time source; a virtual clock for deterministic tests, a real clock
  in production, with identical decisions.
- **Trigger State**: The per-trigger in-process record — last-fired, next-due, fire count, missed-tick
  count, enabled status, and the most recent Scheduled Loop Run reference.
- **Missed-Run Policy**: The per-trigger rule (skip / catch-up-once / coalesce) governing behavior when
  due ticks are missed.
- **Scheduled Loop Run**: A Loop Run started by the Scheduler from a registered trigger, recorded against
  that trigger's Trigger State.
- **Scheduler Event**: A scheduler-level lifecycle record (register / fire / skip / catch-up / coalesce /
  pause / resume / stop), distinct from Loop Events and Runtime Events.

These scheduler-layer entities reference Phase-3 entities — Loop Definition, `run_loop`, Loop Outcome,
Loop State — without redefining them.

## Scheduler Boundaries

Component ownership for this phase (constitution Principle IV). The Scheduler & Trigger Engine interacts
with the loop layer only through the Phase-3 `run_loop` entry point — never through reach-through internal
access to Phase-1, Phase-2, or Phase-3 internals.

| Component | Owns | Must not |
|---|---|---|
| Scheduler | The trigger registry, the Clock dependency, the firing decision, lifecycle, and serialization | Start a Loop Run by any path other than `run_loop`; call a Phase-1/2/3 internal; run two Scheduled Loop Runs concurrently (default) |
| Clock | The injectable monotonic time source | Force a real sleep or wall-clock dependency in tests |
| Interval Driver | Per-period due calculation and firing | Depend on real time; fire unbounded catch-up runs |
| Condition Driver | Predicate evaluation timing and edge/level firing | Implement an in-runtime watcher/daemon; crash on a raising predicate |
| Trigger State | The per-trigger reference record | Copy or own Loop State or run history; require durable persistence this phase |
| Missed-Run Policy | The skip / catch-up-once / coalesce rule | Cause unbounded firing |
| Scheduler Events | The versioned scheduler-level event stream | Wrap, replace, or re-emit Loop Events or Runtime Events |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A scheduler user can register a Loop Definition under a trigger id and start it, producing
  exactly one Scheduled Loop Run through `run_loop` and a Trigger State that records the fire — with a
  boundary audit confirming no Phase-1/2/3 internal was called directly.
- **SC-002**: 100% of Loop Runs started by the Scheduler in the test suite go through `run_loop`; no test
  or audit can demonstrate the Scheduler starting a Loop Run by any other path.
- **SC-003**: An interval trigger of period P fires exactly N times when a virtual clock advances by N·P
  under the default policy, with next-due advancing by exactly one period per fire.
- **SC-004**: A condition trigger fires exactly on the satisfied ticks dictated by its edge/level mode and
  never on unsatisfied ticks; a raising predicate yields a diagnostic and no spurious run.
- **SC-005**: For a clock jump past K due ticks, the number of Loop Runs started equals the configured
  missed-run policy (skip → 1, catch-up-once → 1 make-up, coalesce → 1), verified across all three modes.
- **SC-006**: Trigger State is reconstructable from the ordered Scheduler Event stream alone, verified by
  inspection or replay comparison.
- **SC-007**: The Scheduler never starts two Scheduled Loop Runs concurrently by default; a paused trigger
  starts nothing and a drained Scheduler lets the in-flight run finish and then starts nothing.
- **SC-008**: Two schedulers driven by identical virtual-clock scripts produce identical firing sequences
  and identical Loop outcomes (determinism), with no real sleeping in the suite.
- **SC-009**: With Scheduler observation disabled, scheduling decisions and outcomes are identical to an
  observed run — proving scheduler observation adds zero behavior change.
- **SC-010**: Automated public-safety scans of all committed Phase-4 artifacts find zero private
  references, and a review confirms no Phase-1/2/3 internal is re-implemented (constitution Principles
  IV–VI and VIII upheld).

## In Scope *(this phase)*

- A local, in-process Scheduler owning a trigger registry and an injectable Clock.
- An executable interval trigger driver (virtual-clock-driven, deterministic, no real sleeping).
- An executable condition trigger driver (host predicate; edge and level modes).
- A manual trigger registry (register / lookup / start named loops by id).
- In-process Trigger State (last-fired, next-due, fire count, missed-tick count, enabled), reconstructable
  from the Scheduler Event stream.
- A missed-run policy (skip / catch-up-once / coalesce).
- Scheduler lifecycle (start / stop / pause / resume / drain) and serialized single-in-flight Loop Runs.
- A versioned Scheduler Event stream and `run_loop`-only invocation.

## Out of Scope *(this phase)*

- A distributed or durable queue, a queue-worker system, and any background OS daemon.
- Multi-process or cross-host scheduling.
- Persistent Trigger State across process restarts.
- Cron-expression parsing and any cron syntax.
- Real-time or wall-clock guarantees.
- Cloud deployment, a web/UI, and multi-user tenancy.
- Re-implementing any Phase-1/2/3 internal (validation, retry, repair, evaluation, the loop lifecycle).

## Assumptions

- This phase depends on the completed Phase-1 runtime
  ([`001-loopplane-runtime-foundation`](../001-loopplane-runtime-foundation/spec.md)), the Phase-2 host
  interface ([`002-loopplane-host-interface`](../002-loopplane-host-interface/spec.md)), and the Phase-3
  loop layer ([`003-loopplane-loop-engineering-layer`](../003-loopplane-loop-engineering-layer/spec.md)),
  and consumes the loop layer only through the public `run_loop` entry point.
- Phase-4 consumers are platform developers composing local recurring or condition-driven loops; no
  end-user product host ships in this phase.
- The Clock is injectable; tests use a virtual clock and never sleep on the wall clock. A real clock is a
  thin adapter with identical scheduling decisions.
- The Scheduler is single-process and serializes the Loop Runs it starts (one at a time) unless a host
  opts into its own concurrency; multiple concurrent Scheduled Loop Runs are deferred.
- Trigger State is held in process and reconstructable from the Scheduler Event stream; durable
  cross-restart persistence is reserved, not built.
- Condition predicates are host logic; the layer adds no in-runtime watcher or background daemon.
- Specification and documentation artifacts are written in English, consistent with prior phases, and all
  Phase-4 artifacts contain only public-safe content (constitution Principles II and VII).
