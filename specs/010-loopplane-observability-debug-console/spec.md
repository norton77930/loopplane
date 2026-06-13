# Feature Specification: LoopPlane Observability & Debug-Console Layer

**Feature Branch**: `main` (main-only autopilot)

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Define the LoopPlane Observability & Debug-Console layer (unit 010) on top of the Phase-1 runtime foundation and the Phase-3 Loop Engineering Layer, composing only their public event/state contracts (the Phase-3 Loop Event stream + reconstruct_state, and the Phase-1 Runtime Event stream): reusable, deterministic, public-safe, METADATA-ONLY data contracts and transforms that make runs and loops inspectable after the fact — a trace data model, event replay, a debug timeline, run diagnostics, and loop diagnostics. A read-only data layer; it never drives a run, never re-emits the live buses, and ships no frontend."

## Overview

The Observability & Debug-Console layer (Phase-10) makes a run or loop **inspectable after the fact**. It
ships reusable, deterministic, public-safe, **metadata-only** data contracts and transforms over recorded
event streams: **loop diagnostics**, **run diagnostics**, a **trace data model**, a **debug timeline**, and
deterministic **event replay**.

It is a **read-only data layer**. It consumes the recorded **Phase-3 Loop Event** stream (correlated to its
Agent Runs by `session_id`) and the recorded **Phase-1 Runtime Event** stream exactly as Constitution VI
(Runtime Event Bus Ownership) prescribes for trace/observability consumers — it never drives, starts, or
mutates a run or loop, never reaches Phase-1/Phase-2 internals beyond the public event/state surface, never
re-emits or wraps the live buses, and ships **no** frontend or live UI. Every artifact is deterministic
(ordered by the events' monotonic sequence, not wall-clock) and carries **only metadata** — never
conversation content, tool arguments, or secrets.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what happened in a loop (Priority: P1)

A developer has a recorded Loop Event stream from a finished loop and wants a concise, trustworthy summary:
how many iterations ran, what the validation/evaluation outcomes were, whether retries or repairs happened,
whether human review was requested, and how it ended. The **loop diagnostics** transform produces that
summary deterministically, reusing the Phase-3 state reconstruction where useful.

**Why this priority**: A loop summary is the most common debugging need and exercises the full
recorded-stream → metadata-summary path. This is the minimum slice that delivers value.

**Independent Test**: Given a scripted Loop Event stream, assert the diagnostics report the iteration count,
the validation/evaluation outcomes, retry/repair/human-review counts, and the terminal status; an empty
stream yields an empty report; the report is identical on every run.

**Acceptance Scenarios**:

1. **Given** a recorded Loop Event stream, **When** loop diagnostics run, **Then** the report carries the
   iteration count, the latest validation/evaluation outcomes, retry/repair/human-review counts, and the
   terminal status (`loop_completed` / `loop_failed`).
2. **Given** the same stream, **When** diagnostics run twice, **Then** the two reports are identical.
3. **Given** an empty stream, **When** diagnostics run, **Then** the report is empty and no error is raised.

---

### User Story 2 - See what happened in an agent run (Priority: P2)

A developer wants the same for a single Agent Run from its recorded Runtime Event stream: how many tool calls
ran, how many errors/diagnostics occurred, how many turns, and why it terminated. The **run diagnostics**
transform produces that metadata summary deterministically.

**Why this priority**: Run-level diagnostics complement loop-level ones; independent of the trace/timeline.

**Independent Test**: Given a scripted Runtime Event stream, assert the diagnostics report the tool-call
count, error/diagnostic count, turn count, and termination reason; an unknown future event type is skipped.

**Acceptance Scenarios**:

1. **Given** a recorded Runtime Event stream, **When** run diagnostics run, **Then** the report carries the
   tool-call count, error/diagnostic count, turn count, and termination reason.
2. **Given** a stream containing an unknown future event type, **When** diagnostics run, **Then** the unknown
   event is skipped and the rest is summarized without error.

---

### User Story 3 - Build a trace of a loop and its runs (Priority: P2)

A developer wants a structured trace they could feed to a viewer: the loop, its iterations, the Agent Runs in
each iteration, and the tool calls / turns within each run — a tree of spans keyed by public ids and event
types, metadata only. The **trace data model** transform builds it from the recorded streams.

**Why this priority**: A normalized trace is the foundation a (future, separate) viewer renders; it
correlates loop and run events.

**Independent Test**: Given recorded Loop and Runtime Event streams correlated by `session_id`, assert the
trace nests loop → iteration → run → (tool call / turn) with public ids, types, and counts only — no content
or arguments.

**Acceptance Scenarios**:

1. **Given** correlated Loop and Runtime Event streams, **When** the trace is built, **Then** it nests
   loop → iteration → run → tool call / turn, each span keyed by public ids and event types.
2. **Given** any trace, **When** it is inspected, **Then** it contains no conversation content, tool
   arguments, tool outputs, or secrets.

---

### User Story 4 - Read a debug timeline (Priority: P2)

A developer wants an ordered timeline of events with start→complete spans and nesting, reproducible across
runs. The **debug timeline** transform orders events by their monotonic sequence (not wall-clock) and pairs
start/complete markers.

**Why this priority**: A linear, reproducible timeline is the quickest way to scan what happened; depends on
the same recorded streams.

**Independent Test**: Given a recorded stream with start/complete pairs, assert the timeline is ordered by
sequence, pairs each start with its completion, and is identical on every run.

**Acceptance Scenarios**:

1. **Given** a recorded stream, **When** the timeline is built, **Then** entries are ordered by monotonic
   sequence and a started event is paired with its completed event.
2. **Given** the same stream, **When** the timeline is built twice, **Then** the two timelines are identical.

---

### User Story 5 - Replay a recorded stream for re-inspection (Priority: P3)

A developer wants to re-feed a recorded event stream through a consumer in recorded order to re-inspect it.
The **event replay** transform feeds the recorded events to a supplied sink in order, with replay start/
complete markers, reading recorded events only and starting no run.

**Why this priority**: Replay enables re-running an analysis over a captured stream; lowest priority because
the diagnostics/trace deliver value directly.

**Independent Test**: Given a recorded stream and a recording sink, assert replay delivers every event in
recorded order, brackets them with start/complete markers, and starts no run.

**Acceptance Scenarios**:

1. **Given** a recorded stream, **When** it is replayed through a sink, **Then** the sink receives every
   event in recorded order, bracketed by replay start/complete markers.
2. **Given** replay, **When** it runs, **Then** no run or loop is started or mutated.

---

### Edge Cases

- **Empty stream** → an empty trace / timeline / diagnostics; replay delivers only the start/complete
  markers; never a crash.
- **Unknown future event type** → tolerated and skipped (forward-compatible), never an error.
- **Out-of-order or duplicate sequence** → the timeline orders by sequence deterministically; a missing
  completion leaves an open (unpaired) span recorded explicitly, never a crash.
- **A Loop Event referencing a `session_id` with no Runtime Event stream** → the trace records the run span
  by id with no children, never a crash.
- **A content-bearing payload field** → never surfaced; only declared metadata fields are read.

## Requirements *(mandatory)*

### Metadata-only, read-only foundation

- **FR-001**: Every artifact (trace, timeline, diagnostics, replay markers) MUST carry **only metadata** —
  ids, event types, sequences, counts, and public-safe reasons/statuses. It MUST NOT surface conversation
  content, tool arguments, tool outputs, secrets, or private references (FR-060).
- **FR-002**: The layer MUST be **read-only**: it consumes recorded event streams and MUST NOT drive, start,
  or mutate a run or loop, and MUST NOT re-emit or wrap the live event buses (FR-061, Constitution VI).
- **FR-003**: Every transform MUST be deterministic: the same recorded stream yields the same result on
  every run; ordering MUST be by the events' monotonic **sequence**, never wall-clock time.

### Loop diagnostics (US1)

- **FR-010**: The layer MUST provide **loop diagnostics** over a recorded Loop Event stream reporting the
  iteration count, the latest validation and evaluation outcomes, the retry / repair / human-review counts,
  and the terminal status. It MAY reuse the Phase-3 `reconstruct_state` for the latest-state fields (no
  re-implementation).
- **FR-011**: An empty Loop Event stream MUST yield an empty report; an unknown future loop event type MUST
  be skipped (FR-062).

### Run diagnostics (US2)

- **FR-020**: The layer MUST provide **run diagnostics** over a recorded Runtime Event stream reporting the
  tool-call count, the error/diagnostic count, the turn count, and the termination reason — metadata only.
- **FR-021**: An empty Runtime Event stream MUST yield an empty report; an unknown future runtime event type
  MUST be skipped (FR-062).

### Trace data contract (US3)

- **FR-030**: The layer MUST define a **trace data model** — a tree of spans of loop → iteration → run →
  (tool call / turn), each keyed by public ids and event types — built from a recorded Loop Event stream
  correlated to its Runtime Event streams by `session_id`.
- **FR-031**: A trace MUST carry only metadata (ids, types, sequences, counts); it MUST NOT carry content,
  arguments, or outputs (FR-001).
- **FR-032**: A Loop Event referencing a `session_id` with no Runtime Event stream MUST yield a run span with
  no children, never a crash (FR-062).

### Debug timeline (US4)

- **FR-040**: The layer MUST provide a **debug timeline** — entries ordered by monotonic sequence — that
  pairs a started event with its completed event and records nesting (loop / iteration / run / tool).
- **FR-041**: A started event with no matching completion MUST be recorded as an explicit open span, never a
  crash; a duplicate or out-of-order sequence MUST be ordered deterministically.

### Event replay (US5)

- **FR-050**: The layer MUST provide **event replay** that feeds a recorded event stream to a supplied
  consumer sink in recorded order, bracketed by replay start/complete markers, reading recorded events only.
- **FR-051**: Replay MUST start, drive, or mutate **no** run or loop (FR-061).

### Boundary, non-execution & non-duplication

- **FR-060**: Every artifact MUST be metadata-only and public-safe; the layer MUST NOT read or surface a
  content-bearing payload field.
- **FR-061**: The layer MUST read only the **public** Phase-3 Loop Event / Loop State contracts
  (`LoopEvent`, `LoopEventType`, `reconstruct_state`, `LoopState`, `LoopOutcome`) and the **public** Phase-1
  Runtime Event contracts (`RuntimeEvent` and its typed events). It MUST NOT import a Phase-1/Phase-3 runtime
  control internal (the controller, the host), and MUST NOT re-emit the live buses.
- **FR-062**: The layer MUST tolerate an empty, malformed, or forward-compatible (unknown-type) stream — an
  empty/safe result, never a crash; it MUST NOT re-implement event serialization or state reconstruction
  (those reuse the Phase-1/Phase-3 surfaces).

### Reserved extension points

- **FR-090** (reserved, named-not-built): a live/streaming debug console or web UI.
- **FR-091** (reserved): remote/distributed trace export beyond the existing Phase-1 OpenTelemetry overlay.
- **FR-092** (reserved): persistent trace storage.
- **FR-093** (reserved): cross-run/distributed trace correlation.
- **FR-094** (reserved): wall-clock performance timing or flame graphs.
  Each reserved point MUST be named in docs and MUST NOT be implemented this phase.

### Non-Functional Requirements

- **NFR-001 (Determinism)**: Given a recorded event stream, every trace, timeline, replay order, and
  diagnostics result MUST be identical on every run; ordering is by monotonic sequence, never wall-clock.
- **NFR-002 (Public-safety & metadata-only)**: No committed artifact, and no produced artifact, may contain
  secrets, conversation content, tool arguments/outputs, private paths, internal names, or internal network
  addresses.
- **NFR-003 (Boundary)**: The layer composes only the public Phase-1 Runtime Event and Phase-3 Loop
  Event/Loop State surfaces; it references no runtime control internal, Phase-2 host, or sibling layer —
  enforced by an import audit.
- **NFR-004 (Language & safety)**: All artifacts are English and public-safe.
- **NFR-005 (Fail-safe)**: Every failure mode — an empty stream, an unknown event type, an out-of-order
  sequence, an unpaired span, a missing correlated run — MUST map to an explicit, safe result (empty/skip/
  open-span), never a crash or hang.
- **NFR-006 (Read-only)**: The layer drives zero runs and re-emits zero live-bus events; it only consumes
  recorded streams.

### Key Entities

- **Loop Diagnostics / Run Diagnostics**: metadata summaries over the respective recorded streams.
- **Trace**: a tree of **Trace Spans** (loop / iteration / run / tool call / turn) keyed by public ids +
  types + counts.
- **Debug Timeline / Timeline Entry**: sequence-ordered entries with start/complete pairing and nesting.
- **Replay**: a recorded-stream feeder with start/complete markers and a consumer sink.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer gets a complete loop summary (iterations, outcomes, retries/repairs/review,
  terminal status) from a recorded Loop Event stream with a single transform.
- **SC-002**: Every transform is 100% reproducible — the same recorded stream yields an identical trace,
  timeline, replay order, and diagnostics on every run.
- **SC-003**: No produced artifact contains conversation content, tool arguments/outputs, or secrets
  (metadata-only verified across the suite).
- **SC-004**: An empty, malformed, or unknown-event-type stream always yields a safe result (0 crashes
  across the suite).
- **SC-005**: The layer drives 0 runs and re-emits 0 live-bus events; it only consumes recorded streams.
- **SC-006**: No committed artifact contains secrets, private paths, internal names, or internal network
  addresses (public-safety scan green).
- **SC-007**: The timeline and trace order strictly by monotonic sequence (0 wall-clock-dependent outputs).
- **SC-008**: Loop diagnostics reuse the Phase-3 state reconstruction and never re-implement it
  (import-boundary audit green; latest-state fields match `reconstruct_state`).
- **SC-009**: Replay delivers every recorded event in recorded order, bracketed by start/complete markers,
  starting no run.
- **SC-010**: The reserved extension points (live UI, remote export, persistent storage, cross-run
  correlation, wall-clock timing) are absent from the shipped surface.

## Assumptions

- The layer composes the existing public Phase-3 Loop Event contracts (`LoopEvent` with `type` / `sequence` /
  `loop_id` / `loop_definition_id` / `iteration_index` / `session_id` / `payload`, the `LoopEventType`
  vocabulary, and `reconstruct_state` / `LoopState` / `LoopOutcome`) and the public Phase-1 Runtime Event
  contracts (`RuntimeEvent` and its typed events). These exist and are stable (units 001 and 003 are
  Verified).
- **Streams are recorded** (already-captured sequences), not live. The layer reads them; capturing them is
  the host's concern. Determinism is defined relative to a recorded stream.
- **Ordering is by `sequence`** (monotonic within a run/loop), never wall-clock time; wall-clock performance
  timing is a reserved extension point.
- **Metadata-only**: the layer reads only declared id/type/sequence/count/status fields; it never reads a
  content-bearing payload value, so it cannot leak content even when a payload carries it.
- This layer is **read-only and offline**: it produces data structures for inspection (a future, separate
  viewer renders them); it ships no UI and no live console (reserved).

## Out of Scope

- Any frontend, web, or live UI / console.
- Driving, starting, or mutating a run or loop (owned by Phase-1 / Phase-3).
- Re-emitting or wrapping the live event buses (the layer consumes recorded streams).
- Re-implementing event serialization or loop-state reconstruction (reuse the Phase-1 / Phase-3 surfaces).
- Remote/cloud trace export; persistent trace storage; cross-run correlation; wall-clock timing / flame
  graphs; surfacing conversation content or tool arguments/outputs; any non-deterministic ordering.
