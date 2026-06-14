# Feature Specification: LoopPlane Multi-Agent Orchestration

**Feature Branch**: `013-loopplane-multi-agent-orchestration`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Subagents, coordinator, and delegation on top of the Phase-3 Loop
Engineering Layer (003), composing ONLY its public surface (run_loop / LoopDefinition / LoopOutcome /
LoopEvent / LoopEventSink / LoopState / RunReference / ArtifactRef / reconstruct_state). It ships an
agent registry, subagent execution, a coordinator, a delegation policy, child run references,
aggregated events, and aggregated artifacts. A subagent is a named loop definition; the coordinator
runs selected subagents and aggregates their results DETERMINISTICALLY by registration order. It is an
additive ORCHESTRATION layer — it drives subagent loop runs only through the public Phase-3 entry
point, executes no tool itself, and consumes each subagent's loop-event stream as a consumer (it never
re-emits a live bus). Aggregation is metadata-safe (ids, types, sequences, references, counts), never
conversation content. Deterministic, public-safe, offline, in-process testable, English. Distributed /
remote orchestration, dynamic subagent spawning beyond the registry, and cross-host coordination are
reserved extension points."

## User Scenarios & Testing *(mandatory)*

Multi-agent orchestration turns the single-loop Phase-3 layer into a way to run **several agent loops
as subagents** and combine their results: register named subagents, run a selected set under a
coordinator, reference each child run, and aggregate their events and artifacts — deterministically and
metadata-safe. Every story is a thin, public-safe seam over the **public** Phase-3 loop surface; it
adds no runtime behavior of its own.

### User Story 1 - Register and run a subagent (Priority: P1)

An operator registers a named subagent (a loop definition) and runs it; the orchestrator drives the
subagent's loop run through the public Phase-3 entry point and returns a **child run reference** plus
its outcome. This is the minimum viable product: a named, runnable subagent.

**Why this priority**: A runnable subagent is the unit everything else composes; the coordinator,
delegation, and aggregation all build on it.

**Independent Test**: Register a subagent over a scripted loop definition, run it, and assert the
returned child run reference identifies the run and the outcome reports its terminal status.

**Acceptance Scenarios**:

1. **Given** a registry, **When** an operator registers a named subagent, **Then** it is addressable by
   its public name; a duplicate name is rejected with an explicit error.
2. **Given** a registered subagent, **When** it is run, **Then** exactly one loop run is driven through
   the public Phase-3 entry point and a child run reference + terminal outcome is returned.
3. **Given** an unregistered name, **When** it is run, **Then** an explicit not-found result is
   returned, never a crash.

### User Story 2 - Coordinate a set of subagents (Priority: P2)

An operator runs a **coordinator** over a selected set of subagents; the coordinator runs them in a
deterministic order and returns each child run reference and outcome.

**Why this priority**: Coordinating multiple subagents is the core multi-agent capability; it builds
directly on US1.

**Independent Test**: Register several subagents, coordinate a selected set, and assert each is run
once and the returned references/outcomes are in the registration order, identically on every run.

**Acceptance Scenarios**:

1. **Given** several registered subagents, **When** the coordinator runs a selected set, **Then** each
   selected subagent is run exactly once and its child reference + outcome is returned.
2. **Given** the same selection, **When** the coordinator runs twice, **Then** the references and
   outcomes are in the same deterministic order both times (registration order).
3. **Given** a selection naming an unknown subagent, **When** the coordinator runs, **Then** the
   unknown entry yields an explicit not-found result and the known subagents still run.

### User Story 3 - Aggregate child events (Priority: P3)

An operator obtains an **aggregated event view** over the coordinated subagents: each subagent's loop
events, grouped by subagent in registration order, ordered within a subagent by the events' monotonic
sequence — metadata-safe.

**Why this priority**: Aggregated observability across subagents is what makes a multi-agent run
inspectable; it rounds out US2.

**Independent Test**: Coordinate subagents that emit scripted loop events and assert the aggregated
view groups events by subagent (registration order) and orders them by sequence, with metadata only.

**Acceptance Scenarios**:

1. **Given** coordinated subagents, **When** the aggregated event view is built, **Then** events are
   grouped by subagent in registration order and ordered by sequence within each subagent.
2. **Given** the same run, **When** the view is built twice, **Then** it is identical (deterministic,
   not wall-clock dependent) even if subagents ran concurrently.
3. **Given** any event, **When** it is aggregated, **Then** only metadata (subagent name, type,
   sequence, references) is surfaced — never conversation content.

### User Story 4 - Aggregate child artifacts (Priority: P4)

An operator obtains an **aggregated artifact view** over the coordinated subagents: each subagent's
artifact references, grouped by subagent in registration order — metadata-safe.

**Why this priority**: Aggregated artifacts complete the cross-subagent result picture; strictly
additive to US3.

**Independent Test**: Coordinate subagents that produce artifact references and assert the aggregated
view groups the references by subagent (registration order), with reference metadata only.

**Acceptance Scenarios**:

1. **Given** coordinated subagents with artifacts, **When** the aggregated artifact view is built,
   **Then** the artifact references are grouped by subagent in registration order.
2. **Given** a subagent with no artifacts, **When** the view is built, **Then** it contributes an empty
   group, never a crash.
3. **Given** any artifact, **When** it is aggregated, **Then** only the public-safe reference metadata
   is surfaced — never the artifact content.

### User Story 5 - Delegate and fail safe (Priority: P5)

A **delegation policy** selects which registered subagents the coordinator runs; a failing subagent is
contained, an unknown selection is explicit, and an empty selection is safe.

**Why this priority**: Delegation and fail-safe behavior make the coordinator usable under real,
partial-failure conditions; it guards the other stories.

**Independent Test**: Run a coordinator under a delegation policy where one subagent's loop fails and
one name is unknown, and assert the coordinator completes, the failure is captured per subagent, and
the healthy subagents still produce results.

**Acceptance Scenarios**:

1. **Given** a delegation policy, **When** the coordinator runs, **Then** exactly the policy-selected
   subagents are run, in registration order.
2. **Given** a subagent whose loop run fails (or a raising delegation policy), **When** the coordinator
   runs, **Then** the failure is captured for that subagent and the coordinator still completes with
   the other subagents' results.
3. **Given** an empty selection, **When** the coordinator runs, **Then** it returns an empty,
   well-formed result, never an error.

### Edge Cases

- **Duplicate / unknown subagent**: registering a duplicate name → an explicit error; running or
  selecting an unknown name → an explicit not-found result, never a crash.
- **Failing subagent**: a subagent whose loop run raises or fails is captured per subagent; the
  coordinator still completes with the others' results.
- **Raising delegation policy**: a raising policy is contained (fail-safe), not a crash.
- **Empty selection / no artifacts / no events**: an empty selection → an empty result; a subagent with
  no events/artifacts → an empty group.
- **Concurrent subagents**: even if subagents run concurrently, the aggregated views are ordered
  deterministically by registration order (not completion time).

## Requirements *(mandatory)*

### Functional Requirements

**Agent registry & subagent execution (US1)**

- **FR-001**: The layer MUST provide an agent registry that registers a named subagent (a loop
  definition) addressable by its public name; a duplicate name MUST be rejected with an explicit error.
- **FR-002**: The layer MUST run a registered subagent by driving exactly one loop run through the
  public Phase-3 entry point, returning a child run reference plus its terminal outcome; it MUST NOT
  reach Phase-1/2 internals, execute a tool itself, or re-implement the loop.
- **FR-003**: Running or selecting an unregistered subagent name MUST return an explicit not-found
  result, never a crash.

**Coordinator (US2)**

- **FR-010**: The coordinator MUST run a selected set of subagents, each exactly once, returning each
  child run reference and outcome.
- **FR-011**: The coordinator's returned references/outcomes MUST be in a deterministic order
  (registration order) — identical on every run with the same selection.

**Aggregated events (US3)**

- **FR-020**: The layer MUST build an aggregated event view that groups each subagent's loop events by
  subagent in registration order and orders them within a subagent by the events' monotonic sequence.
- **FR-021**: The aggregated event view MUST be deterministic (never wall-clock dependent, even if
  subagents ran concurrently) and MUST surface only metadata (subagent name, event type, sequence,
  references) — never conversation content.

**Aggregated artifacts (US4)**

- **FR-030**: The layer MUST build an aggregated artifact view that groups each subagent's artifact
  references by subagent in registration order; a subagent with no artifacts contributes an empty
  group.
- **FR-031**: The aggregated artifact view MUST surface only public-safe reference metadata — never the
  artifact content.

**Delegation & fail-safe (US5)**

- **FR-040**: A delegation policy MUST select which registered subagents the coordinator runs; the
  coordinator MUST run exactly the selected subagents in registration order.
- **FR-041**: A subagent whose loop run fails, or a raising delegation policy, MUST be contained — the
  failure is captured per subagent and the coordinator still completes with the other subagents'
  results; an empty selection MUST return an empty, well-formed result.

### Non-Functional Requirements

- **NFR-001 (Boundary)**: The layer MUST compose only the public Phase-3 loop surface
  (`loopplane.engineering`); it MUST NOT import Phase-1/2 runtime internals or a sibling layer. An
  import-boundary audit MUST enforce this (0 violations).
- **NFR-002 (Constitution V — Tool Gateway Ownership)**: The layer MUST execute no tool itself; tool
  execution remains the gateway's, reached only through the subagents' loop runs.
- **NFR-003 (Constitution VI — Runtime Event Bus Ownership)**: The layer MUST consume each subagent's
  loop-event stream as a consumer and MUST NOT re-emit, wrap, or compete with the live event bus.
- **NFR-004 (Determinism)**: Subagent ordering, the coordinator's results, and the aggregated views
  MUST be a pure function of the registry and selection — the same inputs yield the same results on
  every run, ordered by registration (never by wall-clock / completion time).
- **NFR-005 (Fail-safe)**: A failing subagent, a raising policy, an unknown name, or an empty selection
  MUST map to an explicit, safe result — never a crash or hang.
- **NFR-006 (Metadata-only / public-safe / offline)**: All aggregated artifacts MUST be English and
  public-safe (no secrets, private paths, internal names, or IPs), metadata-only (ids / types /
  sequences / references / counts), and produced offline; tests run in-process.
- **NFR-007 (Testability)**: The registry, coordinator, and aggregation MUST be exercised by in-process
  tests over scripted loop definitions — no real model, no network.

### Key Entities *(include if data involved)*

- **Subagent**: a named loop definition registered in the agent registry; addressed by its public name.
- **Child run reference**: a public-safe reference to a subagent's loop run (the subagent name + the
  loop run's reference); metadata only.
- **Subagent result**: a child run reference + the subagent's terminal outcome (or a captured failure).
- **Aggregated event view**: subagents' loop events grouped by subagent (registration order), ordered
  by sequence within — metadata only.
- **Aggregated artifact view**: subagents' artifact references grouped by subagent (registration
  order) — metadata only.
- **Delegation policy**: the selection of which registered subagents the coordinator runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can register and run a subagent and receive a child run reference + outcome
  entirely in-process, with zero direct references to runtime internals.
- **SC-002**: Given the same registry and selection, the coordinator's results and the aggregated views
  are identical on every run (deterministic, registration-ordered, not wall-clock dependent).
- **SC-003**: Across the full test corpus, 0 aggregated views leak a secret, private path, internal
  name, IP, or conversation content; views carry references / metadata only.
- **SC-004**: 100% of failing-subagent / raising-policy / unknown-name / empty-selection cases return
  an explicit, safe result — never a crash or hang.
- **SC-005**: An import-boundary audit confirms the layer composes only the public Phase-3 loop surface
  with 0 violations, executes no tool, and re-emits no live bus event.
- **SC-006**: A coordinator over N subagents runs each exactly once and aggregates all N in
  registration order (no dropped or duplicated subagent).

## Assumptions

- A **subagent is a named loop definition**; running it drives exactly one loop run through the public
  Phase-3 entry point (`run_loop`). The orchestration adds no new public contract to Phase-3.
- Subagents may run **sequentially or concurrently**; the aggregation is deterministic by **registration
  order** regardless, so concurrency never changes the result. Each subagent runs its own independent
  loop run.
- Aggregation is **metadata-only**: it surfaces subagent names, event types/sequences, run references,
  and artifact references — never conversation content, tool arguments, or outputs.
- The layer depends on unit 003 (the loop-engineering layer) for the loop run entry point and the loop
  event/state/reference surface; it adds no dependency to it.
- This unit ships the registry, the coordinator, the aggregation, in-process tests, a public-safe
  example, and a docs guide only.

### Reserved extension points (named, not built)

- Distributed / remote orchestration and cross-host coordination (subagents on other processes/hosts).
- Dynamic subagent spawning beyond the static registry (subagents that create subagents at run time).
- A negotiation / message-passing protocol between subagents (subagents that talk to each other).
- Real parallelism beyond in-process concurrency, and load-balanced subagent pools.
- Persistent orchestration state, replay, or a distributed coordinator.
