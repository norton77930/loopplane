# Feature Specification: Worker Drain Handoff

**Feature Branch**: `088-worker-drain-handoff`
**Created**: 2026-10-08
**Status**: Draft
**Input**: Maintainer asked for the next Spec Kit stage after 087. Gap C4's first remaining P1 item is the G20 live-run tail. This unit takes the between-run handoff slice only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move later work off a worker that is leaving (Priority: P1)

An operator is replacing one web worker in a rolling update. That worker must stop
accepting new runs, finish the run it already holds, and then let another worker
serve the same person.

**Why this priority**: This is the remaining G20 slice that 085, 086, and 087 left open.
**Independent Test**: Mark one of two workers draining during an active run. The
active run finishes. The next run for that person is accepted only by the other worker.

**Acceptance Scenarios**:

1. **Given** a worker is draining and holds no run, **when** a new run is offered to it,
   **then** it refuses, and a worker that is not draining can accept that person.
2. **Given** a worker holds a run and then starts draining, **when** that run is still
   in progress, **then** the run is not cut off, and no second worker can hold the
   same person at the same time.
3. **Given** the draining worker's run has finished, **when** the person continues,
   **then** the other worker can accept the continuation.

### User Story 2 - Leave today's deployments unchanged (Priority: P1)

Drain is an explicit action. Workers that never drain keep today's admit, reject,
and in-flight behavior.

**Why this priority**: A rolling-update control must not change workers that are not leaving.
**Independent Test**: Repeat the existing admission conflicts with drain never started.

**Acceptance Scenarios**:

1. **Given** drain was never started, **when** runs are admitted, **then** results match
   the behavior from unit 085.
2. **Given** an operator cancels the drain, **when** a new run is offered to that worker,
   **then** the worker can accept it again.

### User Story 3 - Do not pretend a live turn moved (Priority: P2)

The person does not get a second run, a new public error, or a claim that an
in-progress turn jumped to another process.

**Why this priority**: Mid-turn migration would change run records and the public API.
**Independent Test**: The refusal uses an existing public capacity response. No new
termination reason appears. The in-flight run ends for its own reason.

**Acceptance Scenarios**:

1. **Given** a draining worker refuses a new run, **when** the caller sees the response,
   **then** the wording is the existing capacity response, not a new phrase.
2. **Given** drain starts during a run, **when** the run ends, **then** its completion
   reason is one this product already had.

### Edge Cases

- Drain on one worker does not drain its peers that share the same grant record.
- A second worker still loses while the draining worker's run is in progress.
- Starting drain twice, or ending it when it was not started, is harmless.
- Process death without an explicit drain stays on the existing lease expiry path.
- Representations of the worker do not gain person, grant, or holder identifiers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Drain MUST be opt-in and off until the operator starts it on that worker (US2).
- **FR-002**: A draining worker MUST refuse a new run before creating a grant (US1).
- **FR-003**: A run already held when drain starts MUST continue until it finishes,
  and MUST still release its grant afterwards (US1).
- **FR-004**: While that grant is held, another worker MUST NOT hold the same person (US1).
- **FR-005**: After the grant is released, another worker that is not draining MUST be
  able to accept that person (US1).
- **FR-006**: Ending drain MUST allow that same worker to accept new runs again (US2).
- **FR-007**: The refusal MUST reuse the existing capacity response. No new public
  phrase, status, route, or termination reason is permitted (US3).
- **FR-008**: No new dependency, extra, Gateway stage, event or checkpoint schema,
  default, or pricing rule is permitted.
- **FR-009**: Worker representations MUST stay free of person, grant, and holder identifiers.
- **FR-010**: Tests MUST cover refusal, in-flight completion, peer acceptance after
  release, drain cancellation, and the unchanged non-drain path.

### Key Entities

- **Worker drain**: a per-worker flag. It is not a grant, a session, or a shared record.
- **Grant**: the existing right for one worker to hold one person. Drain does not create a second kind of grant.
- **Peer worker**: another worker that shares the grant record and is not itself draining.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a two-worker check, the draining worker refuses the next run and the
  other worker accepts it only after the first run has released.
- **SC-002**: An in-flight run whose worker starts draining still finishes, and the
  overlap of the two workers' holds for that person is empty.
- **SC-003**: With drain never started, existing admission checks pass unchanged.
- **SC-004**: The public capacity wording stays the only wording for this refusal.

## Assumptions

- The maintainer authorized the next Spec Kit unit on 2026-10-08 while asking for
  the stage to be planned and implemented in this session.
- "Live run migration" in the gap list is sliced the same way 085 sliced G20.
  This unit is between-run handoff when a worker drains. Moving an in-progress
  turn, its tool calls, or its process memory to another worker stays deferred.
- Remote agent execution (G9), Docker sandbox (G11), billing, and a new public
  route that starts drain stay out of scope. The operator starts drain inside
  the worker they are retiring.
- Lease expiry after a crash remains the existing path. This unit does not shorten leases.

## Out of Scope

- Mid-turn or mid-tool migration, work stealing, and checkpoint schema changes.
- A new termination reason, event type, HTTP route, or public error phrase.
- Sticky routing, load-balancer configuration, and process signal handlers.
- Changing units 085, 086, or 087 after they were verified.
