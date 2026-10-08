# Feature Specification: Subagent Fan-out Cap

**Feature Branch**: `090-subagent-fanout-cap`
**Created**: 2026-10-08
**Status**: Draft
**Input**: Maintainer chose a default-off cap on how many subagent children one root run may start. The next root run starts a new count. Unset behavior stays unchanged. No event, checkpoint, HTTP route, or new dependency.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Leave an unset count unchanged (Priority: P1)

An operator who sets only how deep subagents may nest does not also get a
count limit. Existing runs start the same children they start today.

**Why this priority**: The cap is opt-in. Selecting nothing must stay unchanged.
**Independent Test**: Run a parent that spawns a child that spawns a grandchild,
with no count configured. The grandchild starts.

**Acceptance Scenarios**:

1. **Given** the count is omitted, **when** a child spawns its own child within
   the depth cap, **then** that grandchild starts.
2. **Given** a mapping does not name the count, **when** the host is built,
   **then** the count stays unset.

### User Story 2 - Stop the tree at a chosen count (Priority: P1)

An operator sets how many `spawn_subagent` children one root run may start,
including descendants. The next spawn after that number is refused before a
child host exists. The refusal does not repeat the task. The next root run
on the same host starts a new count.

**Why this priority**: Depth alone does not bound how many children a tree starts.
**Independent Test**: Set the count to one. The parent spawn succeeds. The
child's spawn is refused, and the parent still receives the child's answer.

**Acceptance Scenarios**:

1. **Given** the count is one, **when** a second spawn is requested anywhere in
   the same root run, **then** it is refused and no child host is built for it.
2. **Given** the count is one and one root run has already used it, **when**
   the same host starts another root run that spawns once, **then** that
   spawn succeeds.
3. **Given** the count is zero and the depth cap still registers the tool,
   **when** any spawn is requested, **then** it is refused.
4. **Given** a spawn is refused by the count, **when** the caller reads the
   error, **then** the message is exactly
   `subagent fan-out cap reached (N); refusing to spawn a subagent`
   and does not contain the task text.
5. **Given** a spawn is refused because the depth cap is already reached,
   **when** a later spawn is still inside the depth cap, **then** the depth
   refusal did not use up a count slot.

### User Story 3 - Keep other autonomy caps separate (Priority: P2)

Background tasks, schedules, and swarm members keep their own limits. Those
limits are not added into the spawn count. A child host one of those features
starts uses the same spawn count when it later calls `spawn_subagent`.

**Why this priority**: A second counter would let one root run exceed the number
the operator set.
**Independent Test**: A child admitted during a run, including one whose host
is built after that run returns, is denied by that run's counter even when its
own config allows more.

**Acceptance Scenarios**:

1. **Given** a root run's counter is active, **when** a swarm member, background
   child, or scheduled child is admitted, **then** it uses that run's counter,
   including when its host is built after the run returns.
2. **Given** those other caps are set, **when** they admit their own work,
   **then** that work is not itself a spawn-count increment.

### Edge Cases

- A negative number, a boolean, or a non-integer is rejected when the host is
  built, with `max_subagent_fanout must be a non-negative integer`.
- A child that starts still counts if it later fails. The count does not go
  back down.
- The count lives only in memory for that root run. The next root run starts
  another. It is not a checkpoint field and it is not an event.
- The depth check happens first. A depth refusal does not consume a slot.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Omitting `max_subagent_fanout`, or leaving it unset, MUST NOT
  count `spawn_subagent` children. A host that only sets `max_subagent_depth`
  stays unchanged.
- **FR-002**: A non-negative integer N MUST be the most `spawn_subagent`
  children one root run may start, including descendants. The next root run
  on the same host MUST start a new count.
- **FR-003**: `0` MUST refuse every spawn. The tool MUST stay registered when
  `max_subagent_depth` is at least 1.
- **FR-004**: A boolean, a non-integer, or a negative value MUST be rejected
  with `max_subagent_fanout must be a non-negative integer`.
- **FR-005**: A count refusal MUST be a policy denial whose message is exactly
  `subagent fan-out cap reached (N); refusing to spawn a subagent`. The task
  text MUST NOT appear in that message.
- **FR-006**: The depth check MUST run first and MUST NOT consume a count slot.
- **FR-007**: A refused spawn MUST NOT build a child host. A child that starts
  MUST count even if it later fails. The count MUST NOT decrease.
- **FR-008**: The count MUST be in memory for one root run. Descendants of
  that run MUST share it. The next root run MUST start another count. It
  MUST NOT be a checkpoint field or an event. The check-and-increment MUST
  NOT await.
- **FR-009**: Background, schedule, and swarm caps MUST stay their own limits
  and MUST NOT be added into this count. Child hosts those features start MUST
  share the same counter when they can call `spawn_subagent`.
- **FR-010**: This unit MUST NOT change an event, a checkpoint, an HTTP route,
  a dependency, or an existing default.

### Key Entities

- **Spawn count**: The operator's unset-or-non-negative limit, and how many
  `spawn_subagent` children the current root run has already started.
- **Tree**: The parent host plus every child host that can call
  `spawn_subagent`, including children started by background, schedule, or swarm.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the count unset, a depth-2 spawn still starts the grandchild.
- **SC-002**: With the count at 1, the second spawn is refused, no second child
  host is built, and the task text is absent from the refusal.
- **SC-003**: With the count at 0, every spawn is refused and no child host is
  built.
- **SC-004**: A depth refusal followed by an in-depth spawn still starts that
  one child when the count is 1.
- **SC-005**: A child host built while a run's counter is active uses that
  counter. It does not start another from its own config.
- **SC-006**: The same host, with the count at 1, can spawn once on each of
  two root runs.

## Assumptions

- The maintainer approved this knob on 2026-10-08. It is default-off.
- "Unchanged" means a host that does not set the new field keeps today's spawn
  behavior, including nested spawns that the depth cap already allows.
- No token budget is part of this count. Live-turn migration and the Windows
  local jail stay out of this unit.
