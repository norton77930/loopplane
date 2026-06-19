# Feature Specification: Agent Scheduling Tools

**Feature Branch**: `049-agent-scheduling`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Agent-facing scheduling / recurring-run tools wrapping the unit-004 in-process scheduler so the model can schedule, list, and cancel triggers (host-governed). Unit 049, Tier-2 (autonomy & workflow); closes gap G6. Reuses the 004 scheduler; no new scheduling engine."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent schedules deferred / recurring work (Priority: P1)

While working, the agent schedules a focused task to run **after a delay** or **on a
recurring interval** (rather than only right now), and gets a schedule handle (id) back — so
follow-up or periodic work happens without the agent having to drive each occurrence itself.

**Why this priority**: This is the gap (G6) and the unit's core value — the reference agent
harnesses let an agent schedule recurring/delayed runs; LoopPlane only has immediate and
(via 048) background launch. Time-based scheduling unlocks "do X every N / after N".

**Independent Test**: With scheduling enabled (a deterministic injected clock in tests), the
agent creates an interval schedule; advancing the clock fires the scheduled task the expected
number of times; the schedule's occurrences are observable by id.

**Acceptance Scenarios**:

1. **Given** scheduling is enabled, **When** the agent creates a schedule (a delay or an
   interval) with an instruction, **Then** it receives a schedule id without blocking.
2. **Given** an interval schedule and time advancing (the injected clock in tests), **When**
   the interval elapses, **Then** the scheduled task fires (each occurrence runs as a bounded
   child run), the expected number of times.

---

### User Story 2 - Inspect and cancel schedules (Priority: P2)

The agent can list the run's schedules (with their cadence + status), inspect a schedule, and
cancel one it no longer needs.

**Why this priority**: A schedule is only safe/useful if the agent can enumerate and cancel it.

**Independent Test**: Create a schedule; `list` includes it with its cadence/status; `cancel`
stops further firings and reflects the cancellation; an unknown id yields a clear error.

**Acceptance Scenarios**:

1. **Given** schedules exist, **When** the agent lists them, **Then** it sees each schedule's
   id, cadence, and status (metadata only).
2. **Given** a recurring schedule, **When** the agent cancels it, **Then** no further
   occurrences fire and the schedule reports cancelled.

---

### User Story 3 - Bounded, contained, governed, lifecycle-bound (Priority: P3)

Schedules are bounded (a per-run cap + the 043 recursion-depth cap), contained (a failing
occurrence is reported, never crashing the parent), governed (Gateway tools), deterministic in
tests (an injectable clock — no real sleeping), and tied to the run/session lifecycle (no
schedule fires past its run; pending occurrences are cancelled at scope exit).

**Why this priority**: Autonomy must stay safe and testable — unbounded or leaking schedules,
real-clock flakiness, or a firing that takes down the parent are unacceptable (the 043/048
posture).

**Independent Test**: Exceeding the schedule cap is denied; a failing occurrence is reported
without crashing the parent; with the feature disabled no scheduling tools are offered;
advancing a virtual clock (not real time) drives firings deterministically.

**Acceptance Scenarios**:

1. **Given** the per-run schedule cap is reached, **When** the agent creates another, **Then**
   it is denied with a normalized error and nothing is scheduled.
2. **Given** the run ends with active schedules, **When** the scope exits, **Then** they are
   cancelled (no leak), and the parent's turn cycle is unaffected throughout.

---

### Edge Cases

- **cancel/inspect an unknown schedule id**: a clear normalized error (no crash).
- **interval of zero / negative delay**: rejected with a normalized error.
- **feature disabled / cap 0**: no scheduling tools registered (byte-identical), mirroring
  `max_background_tasks = 0` / `max_subagent_depth = 0`.
- **a firing whose child run raises**: reported on that occurrence's status; the schedule and
  the parent continue.
- **depth cap**: a scheduled child cannot itself schedule without bound (the 043 cap applies).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide agent-facing tools, reachable only through the Tool
  Gateway (V), to **create** a schedule (a one-shot delay or a recurring interval that runs a
  bounded child agent run from an instruction), **list** the run's schedules, **get** a
  schedule's status, and **cancel** a schedule.
- **FR-002**: `create` MUST return a schedule handle (id) without blocking the turn; firings
  occur asynchronously when the cadence elapses.
- **FR-003**: Scheduling MUST reuse the unit-004 scheduler concepts (interval / delay triggers
  on an **injectable clock**) — no new scheduling engine; tests drive a **virtual clock** (no
  real sleeping), so firings are deterministic.
- **FR-004**: `list`/`get` MUST report each schedule's id, cadence, and status as metadata
  only; `cancel` MUST stop further firings and reflect the cancellation; an unknown id MUST be
  a clear normalized error.
- **FR-005**: Schedules MUST be bounded — a configurable per-run maximum, and the existing 043
  recursion-depth cap MUST apply to scheduled child runs; exceeding a cap MUST be denied with a
  normalized error and nothing scheduled.
- **FR-006**: A failing/over-running occurrence MUST be contained — reported on that
  occurrence's status with a public-safe message; it MUST NOT raise across the Gateway or crash
  the parent run.
- **FR-007**: Schedules MUST be tied to the run/session lifecycle — when the run/session ends,
  active schedules are cancelled with no leak; the parent's turn cycle is preserved.
- **FR-008**: The feature MUST be opt-in and default-off (byte-identical when disabled), with
  no scheduling tools registered and no event-schema / content-model change when off.
- **FR-009**: The **concurrency / clock / lifecycle mechanism** MUST be settled in planning
  with a boundary review: prefer reusing the approved unit-048 background-task supervisor
  pattern (ADR 0002) + the unit-004 scheduler, additively (a neutral interface in
  `loopplane.context` so the controller/loop never import the tools layer); if it instead
  requires a breaking 001/002 contract change or a new boundary-crossing ADR, raise it for
  maintainer approval rather than introducing it silently.

### Key Entities *(include if feature involves data)*

- **Schedule**: a registered intent to run a bounded child agent run after a delay or on a
  recurring interval, identified by a schedule id, with a cadence and a status (active /
  cancelled / completed), and a record of its occurrences.
- **Schedule registry**: the per-run collection of schedules + their statuses, surfaced by
  `list`/`get`.
- **Clock**: the injectable time source (a virtual clock in tests; real time in production),
  reused from unit 004 — never real sleeping in tests.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With scheduling enabled and a virtual clock, an interval schedule fires its
  bounded child run the expected number of times as the clock advances (deterministic).
- **SC-002**: list/get/cancel reflect a schedule's real lifecycle (active → cancelled /
  completed) in 100% of covered scenarios; an unknown id errors cleanly.
- **SC-003**: Caps (count + depth) deny excess schedules; a failing occurrence never crashes
  the parent; no schedule fires past run/session end.
- **SC-004**: With the feature disabled, behavior is byte-identical to today — the existing
  test suite passes unchanged and no event-schema / content-model change is introduced.

## Assumptions

- A scheduled occurrence reuses the same bounded child-run machinery as units 043/048 (a
  one-shot `run_loop` child); 049 adds the **time-based trigger + a schedule registry +
  lifecycle binding**, reusing the unit-004 scheduler + clock — not a new engine.
- The concurrency/lifecycle is expected to reuse the unit-048 supervisor pattern (ADR 0002)
  additively; planning's boundary review confirms whether a new ADR is needed (likely not, as
  ADR 0002 already covers in-run concurrent child runs).
- Time is driven by an **injectable clock** (unit 004): tests advance a virtual clock; there
  is no real sleeping in tests.
- Out of scope: cron-expression parsing, durable/cross-session/persistent schedules, and
  distributed scheduling (consistent with unit 004's in-process, non-persistent scope).
- Per Constitution IX, the concept is borrowed from the reference harnesses but re-derived;
  III keeps this a bounded, opt-in autonomy primitive (not the reserved loop-automation layer).
