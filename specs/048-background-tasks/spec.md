# Feature Specification: Background Task Tools

**Feature Branch**: `048-background-tasks`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Agent-facing background / long-running task tools (create / get / list / stop / output) so the model can launch and manage work that outlives a single turn. Unit 048, Tier-2 (autonomy & workflow); closes gap G5. Builds on the existing run/loop seams; a plan-stage boundary review decides additive-vs-ADR."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch work without blocking the turn (Priority: P1)

While working, the agent launches a bounded sub-task (a focused agent run) and immediately
gets a task handle (id) back instead of waiting for it to finish — so it can start several
pieces of work and continue, rather than blocking on each one as it must with the
synchronous `spawn_subagent` (043).

**Why this priority**: This is the core value and the gap (G5) — the reference harnesses let
an agent start background/long-running tasks and keep going; LoopPlane today only has the
blocking one-shot subagent. Non-blocking launch is what unlocks parallel/long work.

**Independent Test**: With background tasks enabled, the agent creates a task; the create
call returns a task id promptly (it does not wait for the task to complete); the task then
runs to completion and its result becomes retrievable.

**Acceptance Scenarios**:

1. **Given** background tasks are enabled, **When** the agent creates a task with an
   instruction, **Then** it receives a task id without waiting for the task to finish.
2. **Given** a created task, **When** it completes, **Then** its final result/output is
   retrievable by id.

---

### User Story 2 - Inspect and control running tasks (Priority: P2)

The agent can query a task's status, retrieve its output, list the run's tasks, and stop a
task it no longer needs.

**Why this priority**: Launching is only useful if the agent can observe and control the work
— get status/output, enumerate tasks, and cancel.

**Independent Test**: Create a task; `get` reports its status; `output` returns its result
once done; `list` includes it; `stop` cancels a still-running task and its status reflects
cancellation.

**Acceptance Scenarios**:

1. **Given** a task id, **When** the agent calls get/output, **Then** it sees the task's
   status and (when finished) its result.
2. **Given** a running task, **When** the agent stops it, **Then** the task is cancelled and
   reported as stopped; **and** `list` reflects the run's tasks and their statuses.

---

### User Story 3 - Bounded, contained, and governed (Priority: P3)

Background tasks are bounded (a cap on how many a run may start, and the same recursion-depth
cap as `spawn_subagent`), failure-contained (a failing task is reported via its status, never
crashing the parent), governed (the tools flow through the Tool Gateway), and tied to the
run's lifecycle (no task outlives or leaks past its run).

**Why this priority**: Autonomy must stay safe — unbounded or leaking background work, or a
task that takes down the parent, is unacceptable (mirrors the 043 fail-safe posture).

**Independent Test**: Exceeding the task cap is denied with a normalized error; a task that
errors is reported as failed (parent continues); when the run ends, no task is left running.

**Acceptance Scenarios**:

1. **Given** the per-run task cap is reached, **When** the agent creates another task, **Then**
   it is denied with a clear normalized error and no task is started.
2. **Given** a task whose work raises, **When** the agent retrieves it, **Then** its status is
   "failed" with a public-safe message and the parent run is unaffected.
3. **Given** pending tasks, **When** the run ends, **Then** they are cancelled/cleaned up (no
   leak).

---

### Edge Cases

- **get/output/stop on an unknown task id**: a clear normalized error (no crash).
- **output before completion**: returns the current status (e.g., "running"), not a block.
- **stop on an already-finished task**: a no-op with a clear status.
- **feature disabled / cap is 0**: no background-task tools are offered (byte-identical to
  today), mirroring `max_subagent_depth = 0`.
- **depth cap**: a background task cannot itself spawn unbounded background tasks (the 043
  recursion-depth cap applies).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide agent-facing tools, reachable only through the Tool
  Gateway (V), to **create** a background task (a bounded agent sub-run from an instruction),
  **get** its status, retrieve its **output**, **list** the run's tasks, and **stop** a task.
- **FR-002**: `create` MUST return a task handle (id) without blocking the turn on the task's
  completion; the task runs concurrently with / deferred from the parent.
- **FR-003**: A completed task's final result MUST be retrievable by id (`get`/`output`),
  and `list` MUST enumerate the run's tasks with their statuses (metadata-only — no secrets,
  no conversation content beyond the task result the agent itself requested).
- **FR-004**: `stop` MUST cancel a still-running task and reflect the cancellation in its
  status; `stop` on a finished/unknown task MUST be a clear, normalized no-op/error (no crash).
- **FR-005**: Background tasks MUST be bounded — a configurable per-run maximum task count,
  and the existing `spawn_subagent` recursion-depth cap (043) MUST apply so tasks cannot nest
  without bound; exceeding a cap MUST be denied with a normalized error and no task started.
- **FR-006**: A failing/over-running task MUST be contained — reported via its status with a
  public-safe message; it MUST NOT raise across the Gateway or crash the parent run.
- **FR-007**: Tasks MUST be tied to the run lifecycle — when the run ends, pending tasks are
  cancelled/cleaned up with no leak; the agent loop's turn cycle for the parent is preserved.
- **FR-008**: The feature MUST be opt-in and default-off (byte-identical to today when
  disabled), mirroring `max_subagent_depth = 0`; when off, no background-task tools are
  registered and no event-schema/content-model change occurs.
- **FR-009**: The **concurrency and lifecycle mechanism** (how a task runs without blocking,
  and how it is bound to the run's structured-concurrency scope) MUST be settled in planning
  with a boundary review; if it cannot be done without a breaking change to a 001/002 public
  contract, or it warrants a new ADR for a boundary crossing, that MUST be raised for
  maintainer approval rather than introduced silently.

### Key Entities *(include if feature involves data)*

- **Background task**: a bounded agent sub-run launched from an instruction, identified by a
  task id, with a status (pending / running / completed / failed / stopped) and, when done, a
  result (the child's final text, as `spawn_subagent` returns).
- **Task registry**: the per-run collection of background tasks and their statuses/results,
  surfaced by `list`/`get`/`output`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `create` returns a handle without waiting for task completion (the parent is not
  blocked), and the task's result is later retrievable — proving non-blocking launch.
- **SC-002**: Status/output/list/stop reflect a task's real lifecycle (running → completed /
  failed / stopped) in 100% of the covered scenarios.
- **SC-003**: Caps (count + depth) deny excess tasks with the file/state unchanged; a failing
  task never crashes the parent; no task leaks past run end.
- **SC-004**: With the feature disabled, behavior is byte-identical to today — the existing
  test suite passes unchanged and no event-schema/content-model change is introduced.

## Assumptions

- A background task reuses the unit-043 one-shot child-run machinery (a bounded agent run via
  the existing Phase-3 `run_loop`); 048 adds **non-blocking launch + a task registry +
  lifecycle binding** on top, rather than a new execution engine.
- Concurrency is in-process (structured concurrency within the run's scope); distributed or
  cross-session/persistent background tasks are out of scope.
- The depth cap reuses the 043 `subagent_depth` / `max_subagent_depth`; an additional per-run
  task-count cap bounds breadth.
- "Output" is the task's final result text (as `spawn_subagent` returns); streaming a task's
  live events to the agent is out of scope for this unit.
- The exact concurrency/lifecycle wiring (and whether an ADR is needed) is a planning decision
  (FR-009); per Constitution IX the concept is borrowed from the reference harnesses but
  re-derived.
