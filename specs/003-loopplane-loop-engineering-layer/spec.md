# Feature Specification: Loop Engineering Layer

**Feature Branch**: `003-loopplane-loop-engineering-layer`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Define the Loop Engineering Layer on top of the completed Runtime
Foundation (`001-loopplane-runtime-foundation`) and Host Interface (`002-loopplane-host-interface`).
This phase introduces outer-loop execution: loop definitions, a loop controller, validation,
evaluation, retry, repair, stop conditions, loop state, and loop-level events. The Loop Engineering
Layer must invoke agent runs through the Phase-2 Host Application Interface and consume runtime events
from it — never bypassing the Host Interface or calling Phase-1 runtime internals directly. Manual
triggers are implemented this phase; interval and condition triggers are contracts only, with no
production distributed scheduler. Out of scope: web UI, desktop app, browser frontend, production
scheduler, queue worker system, cloud deployment, multi-user tenancy, plugin marketplace, full
multi-agent orchestration, sandbox execution, cost governance, and external database persistence."

## Feature Overview

LoopPlane's first phase delivered an embeddable Agent Harness Runtime — thirteen bounded components
that drive a governed model-and-tools loop and make every step observable, controllable, and durable
(see [`../001-loopplane-runtime-foundation/spec.md`](../001-loopplane-runtime-foundation/spec.md)).
Its second phase added a thin host-integration layer — the **Host Application Interface**, a declarative
**Runtime Configuration**, and a **Reference Runner** — so an external application can assemble and run
that runtime from one place (see
[`../002-loopplane-host-interface/spec.md`](../002-loopplane-host-interface/spec.md)). Both phases
deliberately stopped short of automating *repeated* runs: the project constitution (Principle III,
"Agent Harness Before Loop Automation") deferred scheduler, validator, evaluator, and loop automation
to a future layer and left explicit extension points for it.

Phase 3 builds that layer. The **Loop Engineering Layer** wraps agent runs in an outer control loop:
it defines a loop, triggers it, runs an agent run **through the Host Application Interface**, validates
the outcome, optionally evaluates it, decides whether to stop, retry, repair, or request human review,
and repeats until a stop condition is met. It adds **no runtime internals of its own** — every agent
run is started and observed through the Phase-2 Host Interface, and the layer never reaches into
Phase-1 components. The deliverable is the outer loop's vocabulary and control: **Loop Definition**,
**Loop Controller**, **Trigger** boundary, **Validator**, optional **Evaluator**, **retry** and
**repair**, **stop conditions**, **Loop State**, and a **Loop Event** stream.

This phase implements manual triggering and a single, in-process Loop Run at a time. Interval and
condition triggers are defined as contracts a host may drive, with no production scheduler. Loop State
is held in process and reconstructable from the loop's own event stream; durable loop persistence and
loop resume are reserved extension points, not built here.

### Core Distinctions

This phase introduces an outer layer that sits beside, not inside, the runtime. The following
distinctions are normative — every requirement below preserves them.

| # | Phase-1/2 concept (inner) | Phase-3 concept (outer) |
|---|---|---|
| 1 | **Agent Run** — one governed run of a session driven through the Host Application Interface, ending in exactly one terminal Runtime Event. | **Loop Run** — one execution of a Loop Definition: an ordered sequence of one or more **Loop Iterations**, each of which starts exactly one Agent Run. |
| 2 | **Runtime Controller** — owns a single session's lifecycle (create, attach, drive, resume, terminate). | **Loop Controller** — owns a Loop Run's lifecycle; it starts each Agent Run by calling the Host Application Interface (which internally uses the Runtime Controller) and never drives sessions directly. |
| 3 | **Runtime Event** — a normalized within-run step on the Runtime Event Bus (reasoning, tool call, terminal). | **Loop Event** — a loop-level lifecycle record emitted by the Loop Controller on a separate stream; it references runs by `session_id` but never wraps or replaces Runtime Events. |
| 4 | — | **Validator** — produces a gating decision (`pass` / `fail` / `needs_repair` / `needs_human_review`) that drives loop control flow. |
| 5 | — | **Evaluator** — produces optional, non-gating measurement (`score` / `label` / `reason` / `metadata`); it informs but does not by itself decide control flow. |
| 6 | **Retry** — re-runs an iteration after a failed or transient outcome **without changing the instruction** (governed by retry count and backoff). | **Repair** — re-runs after `needs_repair` with an **intentionally changed input** that injects a repair instruction and previous-run context. |
| 7 | **Run State** — a session's per-run history and durable records, owned by the runtime. | **Loop State** — the outer record of iterations and decisions; it references Run State by id and never copies or owns it. |

**What Loop State references (distinction 7, expanded)**: Loop State points at Phase-1/2 state only by
identifier or reference — the `session_id` of each Agent Run, Checkpoint records, Memory entries, and
Artifact references — all obtained and reused through the Host Application Interface. The loop never
reads or mutates Phase-1 internals to assemble its state.

**Implemented this phase vs reserved extension points (distinction 8)**:

- **Implemented**: Loop Definition, Loop Controller, manual trigger, Validator contract and outcome
  handling, optional Evaluator, retry and repair, stop conditions, in-process Loop State, the Loop
  Event stream, and host-interface-only run invocation.
- **Reserved (named, not built)**: interval and condition trigger *execution* (a production
  scheduler/watcher), durable loop-state persistence and loop resume, multiple concurrent Loop Runs,
  and full multi-agent orchestration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define and manually run a single-iteration loop (Priority: P1)

A loop engineer describes an outer loop in a **Loop Definition** — a loop id, a manual trigger, an
input source, a host runtime profile (a Phase-2 Runtime Configuration), and a stop condition of "one
passing iteration" — and triggers it manually. The **Loop Controller** starts one **Loop Iteration**,
invokes the Host Application Interface to run exactly one **Agent Run**, consumes that run's normalized
Runtime Event stream through the interface, records a **Loop State** that references the run and its
artifacts, and emits the loop-level event sequence. The engineer receives the loop outcome and the Loop
State without the loop touching any Phase-1 internal.

**Why this priority**: This is the minimum viable outer loop and the point of the phase. Without a Loop
Definition that can be triggered to drive one governed Agent Run through the Host Interface and produce
observable Loop State, there is no loop engineering layer. It is independently demonstrable with nothing
but a scripted model and a one-line "always pass" validator.

**Independent Test**: Can be fully tested by defining a loop over a scripted-model Runtime
Configuration, triggering it manually, and asserting that exactly one Agent Run is started through the
Host Application Interface, that Loop State references the run's `session_id` and artifacts, and that
the Loop Events `loop_started` → `loop_iteration_started` → `loop_iteration_completed` →
`loop_completed` are emitted in order.

**Acceptance Scenarios**:

1. **Given** a Loop Definition with a manual trigger, a scripted-model host runtime profile, an
   always-pass validator, and a single-iteration stop condition, **When** the engineer triggers the
   loop, **Then** the Loop Controller starts exactly one Agent Run through the Host Application
   Interface and the Loop Run ends with `loop_completed`.
2. **Given** the same loop, **When** it runs, **Then** Loop State records `loop_id`,
   `loop_definition_id`, an iteration index of one, a run reference (`session_id`), the validation
   result, and any artifact references — all by reference, with no copied run history.
3. **Given** the same loop, **When** it runs twice, **Then** both Loop Runs produce identical ordered
   Loop Event streams and identical outcomes (determinism).
4. **Given** the running loop, **When** a boundary audit inspects how the Agent Run was started,
   **Then** it confirms the run was started only through the Host Application Interface and no Phase-1
   component was called directly.

---

### User Story 2 - Gate a loop on validation outcomes (Priority: P2)

A loop engineer attaches a **validation policy** to the Loop Definition. After each iteration's Agent
Run, the **Validator** returns exactly one of `pass`, `fail`, `needs_repair`, or `needs_human_review`.
The Loop Controller emits `validation_completed` and takes the matching action: stop on `pass`, retry
or stop on `fail`, repair on `needs_repair`, and pause for human review on `needs_human_review`.

**Why this priority**: Validation is what turns a single run into a *controlled* loop. It builds on
User Story 1 and is the decision spine every later capability (retry, repair, human review) depends on.

**Independent Test**: Can be fully tested by scripting each validator status in turn and asserting that
the Loop Controller emits `validation_completed` and selects the correct next action and Loop Event for
each — without exercising retry/repair internals beyond the decision.

**Acceptance Scenarios**:

1. **Given** a validator scripted to return `pass`, **When** the iteration completes, **Then** the loop
   emits `validation_completed` and stops with `loop_completed` (success).
2. **Given** a validator scripted to return `needs_repair`, **When** the iteration completes, **Then**
   the loop emits `validation_completed` followed by `repair_requested` and starts a repair iteration.
3. **Given** a validator scripted to return `needs_human_review`, **When** the iteration completes,
   **Then** the loop emits `human_review_requested` and pauses without starting another Agent Run.
4. **Given** a validator that raises or returns an unrecognized status, **When** the iteration
   completes, **Then** the loop fails safe — routing to human review or terminating with `loop_failed`
   and a diagnostic — and never treats the outcome as a silent `pass`.

---

### User Story 3 - Retry transient failures and repair bad output (Priority: P3)

A loop engineer configures a **retry policy** (a maximum retry count and a backoff contract) and a
**repair policy** (a repair instruction source). On `fail`, the Loop Controller schedules a retry —
re-running the same input — until the retry count is exhausted, then stops with failure. On
`needs_repair`, it constructs the next iteration's input by injecting the repair instruction and
previous-run context (prior input, prior outcome reference, validation reason), optionally reusing
prior artifacts, and makes an explicit checkpoint reuse-or-reset decision.

**Why this priority**: Retry and repair are the corrective machinery that makes outer loops useful for
self-improving runs. They build on User Story 2's decisions and are where the retry-vs-repair
distinction must be enforced concretely.

**Independent Test**: Can be fully tested by scripting `fail` outcomes and asserting the retry count is
honored exactly with `retry_scheduled` events, and by scripting a `needs_repair` outcome and asserting
the next Agent Run's input — submitted through the Host Application Interface — contains the repair
instruction and prior-run context while the original Loop Definition is unchanged.

**Acceptance Scenarios**:

1. **Given** a retry policy with a maximum of two retries and a validator scripted to always `fail`,
   **When** the loop runs, **Then** it starts at most three Agent Runs total, emits `retry_scheduled`
   for each retry with the contracted backoff delay, and ends with `loop_failed`.
2. **Given** a validator scripted to return `needs_repair` once then `pass`, **When** the loop runs,
   **Then** the second Agent Run's input — passed through the Host Application Interface — contains the
   repair instruction and the prior run's context, and the loop ends with `loop_completed`.
3. **Given** an artifact policy permitting reuse and a prior iteration that produced an artifact,
   **When** a repair iteration runs, **Then** it references the prior artifact by its Phase-1 reference
   through the Host Interface rather than regenerating or copying it.
4. **Given** a repair iteration, **When** it starts, **Then** the checkpoint reuse-or-reset decision is
   explicit and, by default, the iteration starts a fresh Agent Run (reset) unless reuse is configured,
   and reuse is expressed only by reference to Phase-1 records.

---

### User Story 4 - Score or label iterations with an optional evaluator (Priority: P4)

A loop engineer adds an optional **evaluation policy**. After validation, the **Evaluator** produces a
`score`, `label`, `reason`, and/or `metadata`. The Loop Controller emits `evaluation_completed` and
records the result in Loop State. A stop condition may read the score or label (for example, "stop when
score ≥ threshold"), but evaluation never by itself decides retry or repair. When no evaluation policy
is configured, the loop runs unchanged with no evaluation step.

**Why this priority**: Evaluation adds measurement and quality-driven stopping on top of pass/fail
gating. It is genuinely optional, so it sits below the validation, retry, and repair machinery that the
loop needs to function at all.

**Independent Test**: Can be fully tested by scripting evaluator scores and asserting they are recorded
in Loop State and surfaced via `evaluation_completed`, that a score-threshold stop condition halts the
loop at the right iteration, and that removing the evaluation policy leaves the loop fully functional.

**Acceptance Scenarios**:

1. **Given** an evaluation policy and a stop condition "stop when score ≥ 0.9", **When** an iteration's
   evaluator returns 0.95, **Then** the loop records the evaluation result, emits `evaluation_completed`,
   and stops with `loop_completed`.
2. **Given** an evaluation policy whose evaluator returns a low score below threshold, **When** the
   iteration completes and the validation result is `pass`, **Then** the loop's control flow follows the
   stop condition and validator — evaluation alone does not force a retry or repair.
3. **Given** no evaluation policy, **When** the loop runs, **Then** no evaluation step executes and no
   `evaluation_completed` event is emitted, and the loop completes on validation alone.
4. **Given** an evaluator that raises, **When** the iteration completes, **Then** the error is surfaced
   as a diagnostic, the Loop Run is not aborted, and the iteration proceeds on the validation result.

---

### User Story 5 - Bound triggers and route human review through extension points (Priority: P5)

A loop engineer relies on the **manual trigger** to start Loop Runs and reads the **interval** and
**condition** trigger *contracts* to drive scheduled or condition-based starts from their own host,
since this phase ships no production scheduler. When a validator returns `needs_human_review` or the
approval policy requires it, the loop emits `human_review_requested`, pauses, and resumes on an external
decision — leaving in-run tool approval to the Phase-1 Human Approval boundary.

**Why this priority**: Trigger contracts and the human-review boundary define the layer's edges — what
it commits to versus what it reserves. They depend on the loop machinery in Stories 1–4 existing and
are the last mile that keeps the phase's scope honest.

**Independent Test**: Can be fully tested by asserting the manual trigger starts a Loop Run, that the
interval and condition trigger contracts are documented and a host-supplied driver can invoke each, and
that a `needs_human_review` outcome pauses the loop and a supplied decision resumes or terminates it.

**Acceptance Scenarios**:

1. **Given** a Loop Definition, **When** a host invokes the manual trigger, **Then** exactly one Loop
   Run starts; no background scheduler or daemon is involved.
2. **Given** the interval and condition trigger contracts, **When** a host-supplied driver enacts an
   interval tick or a satisfied condition, **Then** it starts a Loop Run through the same manual entry
   point, and no in-runtime scheduler is required.
3. **Given** a validator that returns `needs_human_review`, **When** the iteration completes, **Then**
   the loop emits `human_review_requested`, records an approval status in Loop State, and starts no
   further Agent Run until a decision is supplied.
4. **Given** a paused loop awaiting human review that never receives a decision, **When** the loop is
   inspected, **Then** it remains cleanly paused with a terminal-pending status and never hangs the
   runtime or leaves a stranded Agent Run.

---

### Edge Cases

- An Agent Run terminates with a non-natural reason (turn budget exhausted, cancelled, or unrecoverable
  error): the Loop Controller maps it to a failed iteration subject to the retry policy, not a loop
  crash.
- The validator raises or returns an unrecognized status: the loop fails safe to human review (or to
  `loop_failed` when review is unavailable) with a diagnostic, never a silent pass.
- The retry count is zero: a single `fail` immediately ends the Loop Run with `loop_failed`, with no
  `retry_scheduled` emitted.
- The stop condition can never be satisfied: the iteration upper bound still terminates the Loop Run
  with `loop_failed`, so no loop runs unbounded.
- A repair is requested but no prior artifacts exist: the repair iteration proceeds with the repair
  instruction and prior-run context alone, with no artifact reuse.
- The evaluator errors: the error is a non-fatal diagnostic; the iteration proceeds on the validation
  result and the Loop Run continues.
- A loop awaiting human review never receives a decision: it stays cleanly paused without consuming a
  running Agent Run and without hanging the runtime.
- The same Loop Definition is triggered to run twice in sequence: each Loop Run is independent with no
  Loop State leaking between runs.
- Observation is disabled: the Loop Run's decisions and outcome are identical to an observed run; only
  the Loop Event emission differs.

## Requirements *(mandatory)*

### Functional Requirements

#### Loop Definition

- **FR-001**: The layer MUST define a declarative, public-safe **Loop Definition** that describes an
  outer loop without embedding runtime internals or secrets. A Loop Definition MUST carry: a stable
  **loop id**, a **trigger**, an **input source**, a **host runtime profile**, a **validation policy**,
  an optional **evaluation policy**, a **retry policy**, a **repair policy**, a **stop condition**, an
  **artifact policy**, an **approval policy**, and an **observation policy**.
- **FR-002**: The **host runtime profile** MUST reference a Phase-2 Runtime Configuration (or a
  host-resolvable selector for one) that composes each Agent Run; the Loop Definition MUST NOT wire
  Phase-1 collaborators directly.
- **FR-003**: The **input source** MUST supply the user request for the first iteration's Agent Run and
  MUST be augmentable by repair context on later iterations (FR-052) without mutating the original
  Loop Definition.
- **FR-004**: The **validation policy** MUST identify the Validator the Loop Controller applies to each
  iteration's outcome; the Validator contract is defined in FR-030–FR-034.
- **FR-005**: The **evaluation policy** MUST be optional; when it is absent, the loop MUST run without
  scoring or labeling and MUST perform no evaluation step (FR-040, FR-042).
- **FR-006**: The **retry policy** and **repair policy** MUST be expressible independently — retry as a
  count plus a backoff contract, repair as enablement plus an instruction source — preserving the
  retry-vs-repair distinction (FR-050–FR-056).
- **FR-007**: The **stop condition** MUST be a testable predicate over Loop State (for example: a
  passing validation, a maximum iteration count, or an evaluation-score threshold) and MUST always
  include a bound that guarantees termination (FR-013).
- **FR-008**: The **artifact policy** MUST declare whether artifacts produced by prior iterations may
  be reused by later iterations and how (by reference), delegating storage to Phase-1 Artifact Storage
  through the Host Interface.
- **FR-009**: The **approval policy** MUST declare when human review is required at the loop level (for
  example, on a validator `needs_human_review`), while delegating enforcement of any in-run tool
  approval to the Phase-1 Human Approval boundary (FR-082). The **observation policy** MUST declare
  whether loop-level observation (Loop Events and any metrics) is emitted, defaulting off in line with
  Phase-1 Observability.

#### Loop Controller

- **FR-010**: The layer MUST provide a **Loop Controller** that owns the lifecycle of a **Loop Run** —
  one execution of a Loop Definition — from trigger to a single terminal loop outcome.
- **FR-011**: For each **Loop Iteration**, the Loop Controller MUST start exactly one Agent Run by
  invoking the Phase-2 Host Application Interface, passing the iteration's input and, on repair or retry
  iterations, the injected context (FR-052).
- **FR-012**: The Loop Controller MUST consume each Agent Run's normalized Runtime Event stream through
  the Host Application Interface and MUST treat the run's single terminal Runtime Event as the
  iteration's runtime outcome; it MUST NOT subscribe to or call any Phase-1 internal directly.
- **FR-013**: The Loop Controller MUST evaluate the stop condition every iteration and MUST enforce a
  hard upper bound on iterations so that every Loop Run reaches a terminal loop outcome (no unbounded
  looping).
- **FR-014**: After each Agent Run, the Loop Controller MUST apply the Validator (FR-030) and, if
  configured, the Evaluator (FR-040), then select exactly one next action: **stop** (success or
  failure), **retry**, **repair**, or **request human review**.
- **FR-015**: The Loop Controller MUST record the result of every iteration into Loop State (FR-060) and
  MUST emit the corresponding Loop Events (FR-070) in deterministic per-loop order.
- **FR-016**: The Loop Controller MUST map an Agent Run terminal reason that is not natural completion
  (turn budget exhausted, cancelled, or unrecoverable error) to a loop-level outcome — by default a
  failed iteration subject to the retry policy — rather than crashing the loop.
- **FR-017**: The Loop Controller MUST be free of any web, browser, desktop, or CLI host dependency and
  MUST be drivable from a plain host process, consistent with Phase-1/2 portability.

#### Trigger Boundary

- **FR-020**: The layer MUST implement a **manual trigger**: a host explicitly starts a Loop Run for a
  given Loop Definition.
- **FR-021**: The layer MUST define an **interval trigger contract** — the inputs and semantics of
  "start a Loop Run every interval" — without providing a production scheduler; a host MAY enact the
  interval externally this phase.
- **FR-022**: The layer MUST define a **condition trigger contract** — a host-supplied predicate whose
  satisfaction starts a Loop Run — without providing a production event or condition watcher this phase.
- **FR-023**: The layer MUST NOT include a production distributed scheduler, queue worker, or background
  daemon; the interval and condition triggers are contracts and extension points only (FR-091).

#### Validator

- **FR-030**: The layer MUST define a **Validator** contract that, given an iteration's Agent Run
  outcome and Loop State, returns exactly one **validation result** whose status is one of: `pass`,
  `fail`, `needs_repair`, or `needs_human_review`.
- **FR-031**: A validation result MUST be able to carry a human-readable **reason** and structured
  **metadata** usable by repair (FR-052) and by the stop condition (FR-007).
- **FR-032**: The Loop Controller MUST map each validation status to a defined decision: `pass` →
  stop-success (unless the stop condition requires further iterations), `fail` → retry (or stop-failure
  when retries are exhausted), `needs_repair` → repair, `needs_human_review` → request human review.
- **FR-033**: The Validator MUST be supplied by the host through the validation policy; the layer MUST
  treat validation as a policy boundary and MUST NOT hardcode domain-specific validation logic.
- **FR-034**: If the Validator raises or returns an unrecognized status, the Loop Controller MUST fail
  safe — by default routing the iteration to human review, or to `loop_failed` when human review is
  unavailable, and emitting a diagnostic — rather than treating the outcome as a silent `pass`.

#### Evaluator

- **FR-040**: The layer MUST define an optional **Evaluator** contract that, when an evaluation policy
  is present, produces an **evaluation result** carrying any of: a numeric **score**, a **label**, a
  **reason**, and structured **metadata**.
- **FR-041**: Evaluation MUST be non-gating: an evaluation result MUST NOT by itself decide stop, retry,
  or repair. Only the stop condition (FR-007) or a Validator MAY consume evaluation output to influence
  control flow.
- **FR-042**: The Loop Controller MUST record each evaluation result in Loop State and emit
  `evaluation_completed`; when no evaluation policy is configured, no evaluation step MUST run and no
  `evaluation_completed` event MUST be emitted.
- **FR-043**: An Evaluator error MUST be non-fatal: it MUST be surfaced as a diagnostic and MUST NOT
  abort the Loop Run; the iteration proceeds using the validation result alone.

#### Retry & Repair

- **FR-050**: The layer MUST treat **retry** and **repair** as distinct operations. **Retry** re-runs an
  iteration after a failed or transient outcome without changing the instruction. **Repair** re-runs
  after `needs_repair` with an intentionally changed input that incorporates corrective context.
- **FR-051**: The **retry policy** MUST express a maximum **retry count** and a **backoff contract** (the
  delay schedule between attempts). The Loop Controller MUST honor the retry count exactly and MUST
  surface the scheduled delay via `retry_scheduled`; the backoff is a contract a host MAY enact, and no
  in-runtime sleeping scheduler is required this phase.
- **FR-052**: On `needs_repair`, the Loop Controller MUST construct the next iteration's input by
  injecting a **repair instruction** and **previous-run context** — at minimum the prior input, the
  prior Agent Run's outcome reference, and the validation reason and metadata — through the Host
  Application Interface, without mutating the original Loop Definition.
- **FR-053**: The repair path MUST support **artifact reuse**: artifacts produced by a prior iteration
  MAY be referenced by a repair iteration (by artifact reference through the Host Interface), governed
  by the artifact policy (FR-008).
- **FR-054**: The retry and repair paths MUST make an explicit **checkpoint reuse-or-reset decision**:
  by default a new iteration starts a fresh Agent Run (reset), and reuse of a prior run's
  checkpoint or context is opt-in and expressed by reference to Phase-1 records, never by copying them.
- **FR-055**: When the retry count is exhausted for a failing iteration, the Loop Controller MUST stop
  the Loop Run with a failure outcome and emit `loop_failed`.
- **FR-056**: Retry and repair MUST both respect the iteration upper bound (FR-013); neither may cause
  unbounded looping.

#### Loop State

- **FR-060**: The layer MUST maintain **Loop State** for each Loop Run carrying: `loop_id`,
  `loop_definition_id`, the current **iteration index**, **run references** (the `session_id` of each
  Agent Run started), the latest **validation result**, the latest **evaluation result** (if any),
  **artifacts** (references), the **approval status**, and the terminal **stop reason** (once set).
- **FR-061**: Loop State MUST reference Phase-1 state — runs, Checkpoint records, Memory entries, and
  Artifacts — only by identifier or reference; it MUST NOT copy or own Run State, conversation history,
  or artifact bytes.
- **FR-062**: Loop State MUST be held in process by the Loop Controller and MUST be reconstructable from
  the ordered Loop Event stream together with the referenced Agent Run records; durable loop-state
  persistence is not required this phase.
- **FR-063**: Loop State MUST remain distinct from Run State: Run State (Phase-1 per-session history and
  durable records) is owned by the runtime, while Loop State is the outer record of iterations and
  decisions that points at runs.
- **FR-064**: Durable loop-state persistence and **loop resume** (reconstructing a Loop Run after a
  process restart) MUST be reserved as named extension points (FR-091) and MUST NOT be implemented this
  phase.

#### Loop Events

- **FR-070**: The layer MUST emit a **Loop Event** stream distinct from the Phase-1 Runtime Event
  stream. Loop Events describe loop-level lifecycle; they reference Agent Runs by `session_id` but MUST
  NOT wrap, replace, or re-emit Runtime Events.
- **FR-071**: The layer MUST emit, at the appropriate points: `loop_started`, `loop_iteration_started`,
  `loop_iteration_completed`, `validation_completed`, `evaluation_completed`, `repair_requested`,
  `retry_scheduled`, `human_review_requested`, `loop_completed`, and `loop_failed`.
- **FR-072**: Every Loop Event MUST carry at least the `loop_id`, the `loop_definition_id`, the
  iteration index it pertains to (where applicable), and a correlation to the relevant Agent Run
  (`session_id`) when one exists.
- **FR-073**: Loop Events MUST be emitted in deterministic per-loop order, and the ordered Loop Event
  stream MUST be sufficient to reconstruct the loop's decisions and Loop State (FR-062), mirroring the
  Phase-1 event-sufficiency guarantee.
- **FR-074**: Every Loop Run MUST end by emitting exactly one terminal Loop Event — `loop_completed`
  (success) or `loop_failed` (failure) — so no Loop Run is left without a terminal outcome.
- **FR-075**: The Loop Event vocabulary MUST be versioned and evolve additively, consistent with the
  Phase-1 Runtime Event Bus discipline; consumers MUST be able to tolerate unknown future loop-event
  types.

#### Host Interface Integration

- **FR-080**: Every Agent Run started by the layer MUST be started through the Phase-2 Host Application
  Interface; no Loop component may start, drive, or terminate a run by any other path.
- **FR-081**: The layer MUST consume runtime events for each Agent Run from the Host Application
  Interface event stream; it MUST NOT subscribe to the Phase-1 Runtime Event Bus, Dispatcher, or Agent
  Loop directly.
- **FR-082**: The layer MUST pass per-iteration input, memory selection, and repair context to each
  Agent Run through the Host Application Interface and Runtime Configuration surface; any tool approval
  encountered during a run MUST be resolved through the Phase-1 Human Approval boundary as surfaced by
  the Host Interface, not re-implemented by the loop.
- **FR-083**: The layer MUST obtain run outcomes, Checkpoint references, and Artifact references only
  through the Host Application Interface, and MUST treat them as opaque references for Loop State
  (FR-061).

#### Boundary, Non-Duplication & Extension Points

- **FR-090**: The layer MUST NOT implement or duplicate any Phase-1 runtime internal — Agent Loop,
  Runtime Controller session mechanics, Dispatcher, Tool Gateway, Runtime Event Bus, Memory, Checkpoint,
  Artifact Storage, Observability, or Human Approval — nor any Phase-2 host-assembly internal; it MUST
  compose them only through the Phase-2 Host Application Interface.
- **FR-091**: The layer MUST name, without implementing, the reserved extension points: interval and
  condition trigger execution (a production scheduler or watcher), durable loop-state persistence and
  loop resume, multiple concurrent Loop Runs, and full multi-agent orchestration.
- **FR-092**: The layer MUST NOT implement any out-of-scope product or platform layer — web UI, desktop
  app, browser frontend, distributed scheduler, queue worker system, cloud deployment, multi-user
  tenancy, plugin marketplace, sandboxed execution, cost governance, or external database persistence.
  Any such need discovered during implementation MUST be deferred to a future-phase specification.

### Non-Functional Requirements

- **NFR-001 (Phase dependency)**: This phase MUST build strictly on the completed Phase-1 runtime
  foundation and the Phase-2 Host Interface and inherit their guarantees — deterministic event
  ordering, privacy, portability, and lossless serialization — rather than re-stating or re-deriving
  them.
- **NFR-002 (Determinism)**: Given a scripted model, a scripted validator, and a scripted evaluator, a
  Loop Run MUST produce the same ordered Loop Event stream, the same iteration decisions, and the same
  terminal outcome on every run.
- **NFR-003 (Boundary integrity)**: It MUST be auditable that no Loop component invokes a Phase-1 or
  Phase-2 internal directly; all run orchestration goes through the Host Application Interface
  (operationalized by FR-080–FR-083 and SC-002).
- **NFR-004 (Public-safety)**: All committed Phase-3 artifacts MUST remain public-safe — no secrets,
  credentials, private paths, private project or repository names, or internal network addresses — and
  no raw private-reference excerpts.
- **NFR-005 (Observability parity)**: Loop-level observation MUST default off and add zero behavior
  change when disabled, consistent with the Phase-1 Observability principle; enabling it MUST NOT alter
  loop decisions or outcomes.
- **NFR-006 (Minimalism & reversibility)**: The layer MUST stay minimal and independently reversible,
  with no speculative product surface, consistent with the constitution's "harness before loop
  automation" principle and surgical-scope discipline.

### Key Entities

- **Loop Definition**: The declarative, public-safe description of an outer loop — loop id, trigger,
  input source, host runtime profile, validation/evaluation/retry/repair policies, stop condition, and
  artifact/approval/observation policies. Carries no secrets and wires no runtime internals.
- **Loop Run**: One execution of a Loop Definition — an ordered sequence of Loop Iterations ending in a
  single terminal loop outcome.
- **Loop Iteration**: One pass of the loop — a single Agent Run started through the Host Interface, plus
  its validation, optional evaluation, and the resulting control decision.
- **Loop Controller**: The owner of a Loop Run's lifecycle; it starts iterations through the Host
  Application Interface, tracks Loop State, decides stop/retry/repair/human-review, and emits Loop
  Events.
- **Trigger**: What starts a Loop Run — a manual trigger (implemented) or an interval or condition
  trigger contract (host-driven this phase).
- **Validation Result**: The Validator's gating output — a status of `pass` / `fail` / `needs_repair` /
  `needs_human_review` plus optional reason and metadata.
- **Evaluation Result**: The optional Evaluator's non-gating output — score, label, reason, and/or
  metadata.
- **Retry Policy**: The maximum retry count and the backoff contract governing retries.
- **Repair Instruction**: The corrective guidance injected, with previous-run context, into a repair
  iteration's input.
- **Stop Condition**: The testable predicate over Loop State that, together with the iteration bound,
  determines when a Loop Run ends.
- **Loop State**: The outer per-run record — loop id, definition id, iteration index, run references,
  validation and evaluation results, artifact references, approval status, and stop reason — held in
  process and reconstructable from the Loop Event stream.
- **Loop Event**: A loop-level lifecycle record on the Loop Event stream, distinct from Runtime Events.

These outer-layer entities reference Phase-1/2 entities — Agent Run (Session), Runtime Event, Checkpoint
record, Artifact, Approval Request, the Host Application Interface, and the Runtime Configuration —
without redefining them.

## Loop Engineering Boundaries

Component ownership for this phase (constitution Principle IV). The Loop Engineering Layer interacts
with the runtime only through the Phase-2 Host Application Interface and its normalized event stream —
never through reach-through internal access to Phase-1 or Phase-2.

| Component | Owns | Must not |
|---|---|---|
| Loop Definition | The declarative outer-loop contract (trigger, input source, host runtime profile, and the validation/evaluation/retry/repair/stop/artifact/approval/observation policies) and its validation | Carry secrets or private paths; wire Phase-1 collaborators directly; encode runtime internals |
| Loop Controller | The Loop Run lifecycle: starting iterations through the Host Interface, tracking Loop State, deciding stop/retry/repair/human-review, and emitting Loop Events | Call any Phase-1/Phase-2 internal directly; start a run by any path other than the Host Application Interface |
| Trigger Boundary | The manual trigger and the interval/condition trigger contracts | Include a production scheduler, queue worker, or background daemon |
| Validator | The gating contract (`pass` / `fail` / `needs_repair` / `needs_human_review`) and fail-safe handling | Hardcode domain-specific validation; perform non-gating scoring (that is the Evaluator) |
| Evaluator | The optional non-gating measurement (score/label/reason/metadata) | Decide control flow on its own; abort the loop on error |
| Retry & Repair | Retry count and backoff contract; repair instruction and previous-run context injection; artifact reuse and checkpoint reuse-or-reset decisions | Mutate the original Loop Definition; copy Run State or artifact bytes; loop unbounded |
| Loop State | The outer per-run record that references runs, checkpoints, memory, and artifacts by id | Copy or own Run State; require durable persistence this phase |
| Loop Events | The versioned loop-level event stream and its terminal-event guarantee | Wrap, replace, or re-emit Runtime Events |
| Host Interface Integration | Starting runs and consuming runtime events exclusively through the Host Application Interface | Bypass the Host Interface or reach into runtime-foundation internals |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A loop engineer can define a loop and run it end-to-end from a single manual trigger,
  producing a Loop State that references the Agent Run's `session_id`, the validation result, and any
  artifacts, and emitting the ordered Loop Event sequence — with a boundary audit confirming no Phase-1
  internal was called directly.
- **SC-002**: 100% of Agent Runs started by loops in the test suite go through the Host Application
  Interface; no test or audit can demonstrate a loop starting, driving, or observing a run by any other
  path.
- **SC-003**: Each of the four validation statuses (`pass`, `fail`, `needs_repair`,
  `needs_human_review`) maps to a defined, observable loop decision and Loop Event in 100% of suite
  cases, including the fail-safe path for an unrecognized or raised validator outcome.
- **SC-004**: The retry policy is honored exactly — a loop with retry count N starts at most N+1 Agent
  Runs for a persistently failing iteration and ends with `loop_failed` on exhaustion.
- **SC-005**: A repair iteration's Agent Run input, captured as it is submitted through the Host
  Application Interface, demonstrably contains the repair instruction and prior-run context, while the
  original Loop Definition is unchanged.
- **SC-006**: The ordered Loop Event stream for a Loop Run is alone sufficient to reconstruct the loop's
  decisions and Loop State, verified by inspection or replay comparison.
- **SC-007**: Every started Loop Run reaches exactly one terminal Loop Event within its iteration and
  retry bounds — no Loop Run hangs, loops unbounded, or ends without a terminal outcome, including loops
  paused for human review that receive no decision.
- **SC-008**: The interval and condition triggers are specified as host-drivable contracts with no
  scheduler dependency; a host-supplied test driver can enact each and start a Loop Run through the
  manual entry point.
- **SC-009**: With observation disabled, a Loop Run's decisions and terminal outcome are identical to the
  same run with observation enabled — proving loop observation adds zero behavior change.
- **SC-010**: Automated public-safety scans of all committed Phase-3 artifacts find zero private
  references — internal paths, private project or repository names, network addresses, credentials — and
  a review confirms no Phase-1 or Phase-2 internal is re-implemented (constitution Principles IV–VI and
  VIII upheld).

## In Scope *(this phase)*

- A declarative Loop Definition contract covering loop id, trigger, input source, host runtime profile,
  and the validation, evaluation, retry, repair, stop, artifact, approval, and observation policies.
- A Loop Controller that owns the Loop Run lifecycle, starts each Agent Run through the Host Application
  Interface, tracks Loop State, and decides stop/retry/repair/human-review.
- A manual trigger, plus interval and condition trigger contracts (no production scheduler).
- A Validator contract with the four gating outcomes and fail-safe handling.
- An optional Evaluator contract producing non-gating score/label/reason/metadata.
- Retry (count + backoff contract) and repair (instruction + previous-run context injection, artifact
  reuse, checkpoint reuse-or-reset decision), kept distinct.
- In-process Loop State that references runs, checkpoints, memory, and artifacts by id and is
  reconstructable from the Loop Event stream.
- A versioned Loop Event stream with the ten named events and a single terminal event per Loop Run.
- Host-interface-only run invocation and runtime-event consumption.

## Out of Scope *(this phase)*

- A web UI, a desktop app, and a browser frontend.
- A production distributed scheduler, a queue worker system, and any background trigger daemon —
  interval and condition triggers are contracts only this phase.
- Cloud deployment, multi-user tenancy, a plugin marketplace, full multi-agent orchestration, sandboxed
  execution, and cost governance.
- External database persistence and durable loop-state persistence or loop resume (reserved extension
  points).
- Multiple concurrent Loop Runs (single in-process Loop Run at a time this phase).
- Raw private-reference migration details — the loop concepts are rewritten public-safe here, and no
  raw reference material is reproduced.

## Assumptions

- This phase depends on the completed Phase-1 runtime foundation
  ([`001-loopplane-runtime-foundation`](../001-loopplane-runtime-foundation/spec.md)) and the Phase-2
  host interface ([`002-loopplane-host-interface`](../002-loopplane-host-interface/spec.md)), and
  consumes the runtime only through the Phase-2 Host Application Interface and its normalized event
  stream.
- Phase-3 consumers are loop engineers and platform developers composing outer loops programmatically;
  no end-user product host ships in this phase.
- The Validator and Evaluator are supplied by the host as policies referenced by the Loop Definition;
  the layer defines their contracts and handles their outcomes but hardcodes no domain-specific logic.
- The retry backoff, interval trigger, and condition trigger are contracts a host driver enacts; no
  in-runtime scheduler, watcher, or sleeping loop is introduced this phase.
- Loop State is held in process and is reconstructable from the Loop Event stream and the referenced
  Agent Run records; durable loop persistence and loop resume are reserved, not built.
- A single Loop Run executes at a time; multiple concurrent Loop Runs are deferred.
- The local filesystem durability from Phase 1 remains sufficient for the Checkpoint and Artifact
  references a loop reuses; no external database is introduced.
- Specification and documentation artifacts are written in English, consistent with the Phase-1 and
  Phase-2 specs.
- The local private reference directory remains untracked; it is not read, modified, or committed by
  this phase, and all Phase-3 artifacts contain only public-safe content (constitution Principles II
  and VII).
