# Feature Specification: Event Replay Store

**Feature Branch**: `071-event-replay-store`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Durable cross-process / multi-worker SSE reconnect (gap G23):
introduce a host-selectable Event Replay Store keyed by session and event sequence, with local and
network-capable backends, so session event-stream reconnect can replay missed events after
Last-Event-ID even when the in-process ring buffer is insufficient. Keep the default 058 behavior
unchanged, preserve normalized runtime event contracts, and keep replay scoped to the requesting
session/principal."

## Boundary Note

Unit 058 made session SSE reconnect resumable with a bounded in-memory per-session ring buffer and
explicitly deferred durable cross-process resume. This unit closes that durable half of gap G23. The
store records already-normalized session event frames for replay; it does not create new runtime
events, reinterpret event payloads, or replace the Runtime Event Bus. The roadmap board records ADR
0012 as the settled boundary direction for this unit; if the ADR artifact is still absent at plan
time, the plan must materialize or reconcile that decision before implementation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume After Process Loss Or Worker Change (Priority: P1)

A web client streaming a long-lived session loses its connection while events continue to be
produced. When the client reconnects with the standard `Last-Event-ID` value, it receives the
missed events from durable replay storage before continuing with live events.

**Why this priority**: This is the primary user value of the durable G23 follow-up. Unit 058 can only
replay what the current process retained; production deployments need reconnect behavior that is not
limited to one worker's memory.

**Independent Test**: Can be tested by recording session events into a replay store, creating a fresh
stream consumer that represents a reconnect from another process, and asserting that only events
with sequence greater than the supplied last-seen id are replayed in order before live delivery.

**Acceptance Scenarios**:

1. **Given** a session has stored events with sequences 1 through 5, **When** a client reconnects
   with `Last-Event-ID` 2, **Then** the stream first replays events 3 through 5 in sequence order.
2. **Given** replay has delivered stored events through sequence 5, **When** live events are still
   pending or arrive concurrently, **Then** the client does not receive duplicate events with
   sequence 5 or lower and then continues with later live events.

---

### User Story 2 - Preserve Default And In-Memory Behavior (Priority: P1)

Existing hosts that do not configure durable replay keep the unit 058 behavior exactly: the
in-memory ring buffer remains the default reconnect mechanism, and disabled replay remains
byte-identical where configured off.

**Why this priority**: Durable replay is operationally useful but must not impose new storage,
dependency, latency, or behavior on existing deployments.

**Independent Test**: Can be tested with existing session SSE tests and a default web host
configuration, proving that frame shape, `id:` behavior, in-memory replay, and disabled-buffer cases
remain unchanged unless a durable store is explicitly configured.

**Acceptance Scenarios**:

1. **Given** no durable replay store is configured, **When** a session event stream is used, **Then**
   current unit 058 in-memory behavior remains unchanged.
2. **Given** replay buffering is disabled, **When** a client streams events, **Then** frame output
   remains byte-identical to the disabled behavior from unit 058.

---

### User Story 3 - Operate Safely Across Backends And Tenants (Priority: P2)

An embedder can choose a local or shared durable replay backend, enforce bounded retention, and rely
on session/principal scoping so reconnect never leaks another caller's events.

**Why this priority**: Durable replay stores event payloads. The store must be interchangeable,
bounded, public-safe, and scoped to the session owner before it is suitable for multi-worker hosts.

**Independent Test**: Can be tested with a shared contract suite over the available replay-store
backends, plus web/API authorization tests proving that a non-owner cannot replay another
principal's session events.

**Acceptance Scenarios**:

1. **Given** two sessions owned by different principals, **When** one principal reconnects, **Then**
   only that principal's authorized session events can be replayed.
2. **Given** a configured retention limit, **When** more events are stored than the limit permits,
   **Then** older events are pruned or skipped according to the retention policy and reconnect
   continues safely with the retained window.
3. **Given** a replay backend is unavailable or contains corrupt stored entries, **When** a client
   reconnects, **Then** the server emits no private details, avoids crashing the run, and continues
   live when safe.

### Edge Cases

- Missing or malformed `Last-Event-ID`: starts live or replays the retained window using the
  existing fail-safe posture, never crashing.
- Last-seen id older than retention: replays the retained durable window and then live, without
  claiming full recovery.
- Last-seen id newer than stored events: replays nothing and continues live.
- Store unavailable during append: live event delivery remains best-effort and emits only
  public-safe diagnostics.
- Store unavailable during reconnect: durable replay is skipped or degraded safely, then live
  streaming continues when possible.
- Corrupt stored entry: skipped and reported through public-safe diagnostics, without breaking later
  valid entries.
- Multi-worker duplicate risk: replay and live delivery deduplicate by event sequence.
- Unauthorized session access: follows existing session-owner scoping and does not reveal whether
  another principal's replay data exists.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a host-selectable durable event replay store for session event
  frames keyed by session id and event sequence.
- **FR-002**: The replay store MUST record the same serialized normalized event frame that the
  session stream would send, without adding or changing runtime event payloads.
- **FR-003**: Reconnect handling MUST replay stored frames with sequence greater than the provided
  `Last-Event-ID` in ascending sequence order before continuing live.
- **FR-004**: Replay plus live delivery MUST deduplicate by sequence so a client does not receive
  the same event twice across the replay/live boundary.
- **FR-005**: Existing unit 058 behavior MUST remain the default when no durable replay store is
  configured, including in-memory ring replay and disabled-buffer byte identity.
- **FR-006**: The feature MUST include interchangeable replay-store backends for local durable use
  and shared multi-worker use, with optional networked storage import-guarded so base installs are
  unaffected.
- **FR-007**: Replay storage MUST support bounded retention or pruning so replay data does not grow
  without an operator-selected limit.
- **FR-008**: Replay MUST respect existing session ownership and principal scoping; a caller MUST
  NOT replay or infer another principal's session events.
- **FR-009**: Store append, load, corruption, and unavailable-store failures MUST be fail-safe and
  public-safe; failures MUST NOT expose credentials, private paths, or raw backend errors.
- **FR-010**: The feature MUST NOT add a runtime event type, termination reason, content block, or
  runtime event schema-version bump.
- **FR-011**: The feature MUST include offline deterministic tests for replay ordering,
  replay/live deduplication, default-unchanged behavior, retention boundaries, backend contract
  behavior, and authorization scoping.

### Key Entities

- **Event Replay Entry**: One stored session event frame, identified by session id and event
  sequence, with public serialized event data and recording metadata.
- **Event Replay Store**: Host-selected storage boundary that appends replay entries and returns a
  bounded ordered range after a last-seen sequence.
- **Replay Cursor**: The client's last observed sequence, normally supplied through the SSE
  `Last-Event-ID` header.
- **Retention Policy**: Operator-selected bounds that determine how much replay history is retained
  per session or store.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of covered reconnect scenarios replay only events with sequence greater than the
  supplied last-seen id, in ascending order, before live delivery.
- **SC-002**: 100% of covered replay/live boundary scenarios deliver no duplicate event sequence to
  the same reconnecting stream.
- **SC-003**: Existing unit 058 default and disabled behavior tests pass without expected-output
  changes when no durable replay store is configured.
- **SC-004**: Every available replay-store backend passes the same contract tests for append, range
  replay, ordering, retention, corruption tolerance, and unavailable-store behavior.
- **SC-005**: Authorization tests prove a principal cannot replay another principal's session events
  in 100% of covered scenarios.
- **SC-006**: Public-safety scans over changed files find no credentials, private paths, raw backend
  connection data, or private provider payload dumps.

## Assumptions

- Unit 058 remains the default reconnect behavior unless a host explicitly configures durable
  replay storage.
- The replay store records serialized normalized event frames; it does not own event vocabulary,
  event semantics, or frontend-specific formatting.
- The existing session/principal ownership checks from the web/API host apply before replay data is
  read.
- The roadmap board settles the ADR 0012 direction; plan time will create or reconcile the ADR
  artifact if it is still missing.
- The network-capable backend can reuse the repository's existing optional storage dependency
  posture; base installs must continue to import without that optional dependency.
