# Research: Event Replay Store

## Decision 1 - Store serialized SSE frames, not raw event objects

**Decision**: Persist the exact SSE frame string produced for the session stream, keyed by
`(session_id, sequence)`, together with principal id and recording metadata.

**Rationale**: Unit 058 already defines the client-visible frame contract: an `id:` line derived
from event sequence plus a `data:` line containing the public serialized runtime event. Storing the
same frame avoids reformatting drift and keeps the Runtime Event Bus vocabulary untouched.

**Alternatives considered**:

- Store raw `RuntimeEvent` JSON and rebuild SSE frames on replay. Rejected because it duplicates the
  frame-format responsibility and risks drift between live and replayed frames.
- Store provider or model payloads. Rejected as out of scope and unsafe; replay owns public runtime
  event frames only.

## Decision 2 - Webapi-owned replay boundary

**Decision**: Put `EventReplayStore` under `loopplane.webapi`, not under the runtime event package.

**Rationale**: The store is a retained SSE transport concern. It does not publish, transform, or
own normalized runtime events. Keeping it in webapi preserves Constitution VI: the Event Bus remains
the source of normalized events, while webapi adapts those events to transport frames.

**Alternatives considered**:

- Add a core `loopplane.events` store. Rejected because it would imply Event Bus ownership of
  transport replay and broaden the runtime contract.
- Reuse checkpoint records. Rejected because checkpoint history and SSE frame replay have different
  retention, corruption, and client-cursor semantics.

## Decision 3 - Protocol shape

**Decision**: Use a small Protocol:

- `append(record)` asynchronously stores one event replay record.
- `load_after(session_id, principal_id, sequence, limit)` returns ordered retained records after the
  cursor plus public-safe problems.
- `delete_session(session_id)` removes a session's replay data.
- Optional pruning is implementation-owned and happens during append based on retention config.

**Rationale**: This keeps writes non-blocking for async session sinks while preserving simple
read-side integration with SSE reconnect. Including `principal_id` in the query defends against
misuse even though the route performs ownership checks first.

**Alternatives considered**:

- A streaming subscription Protocol. Rejected for this unit because File/SQLite/Postgres cannot
  implement push notifications uniformly without a larger distributed event bus.
- A fully async read Protocol. Rejected for parity with existing sync storage patterns and because
  reconnect range reads are small and bounded.

## Decision 4 - Cross-worker tail by polling the store

**Decision**: After durable replay, a reconnecting stream may poll `load_after` at a bounded
interval when no in-process live channel is available. When the live channel is available, existing
live streaming remains the fast path and is merged/deduplicated by sequence.

**Rationale**: Multi-worker reconnect cannot rely on a process-local AnyIO memory channel. Polling
the shared replay store is simple, deterministic, and works consistently for File-on-shared-disk,
SQLite-on-shared-file, and Postgres. It avoids adding a new distributed event bus.

**Alternatives considered**:

- Database notifications or pub/sub. Rejected as backend-specific and larger than the P2 scope.
- Replay-only then close. Rejected because SSE reconnect should continue as a stream when possible.

## Decision 5 - Backends mirror checkpoint storage style

**Decision**: Provide File, SQLite, and optional Postgres replay-store backends. SQLite uses the
standard library. Postgres reuses the repository's existing optional extra and sync thread-bridge
posture from ADR 0008.

**Rationale**: This matches the storage progression already established by checkpoint units: a
local file default for deterministic tests, SQLite for local durable sharing, and Postgres for
networked deployments. Import-guarding keeps base installs unaffected.

**Alternatives considered**:

- Only Postgres. Rejected because local tests and small deployments need a dependency-free durable
  backend.
- Only file/SQLite. Rejected because the feature's multi-worker target needs a network-capable
  option.

## Decision 6 - Retention is mandatory and configurable

**Decision**: Every backend enforces an operator-selected maximum retained event count per session.
The default store configuration must be explicit; absence of a store keeps unit 058 behavior.

**Rationale**: Runtime event streams may be long-lived. Durable replay without pruning can grow
without bound and violates the bounded-resilience posture established in unit 058.

**Alternatives considered**:

- Time-based retention only. Rejected for the first slice because count-based retention is easier to
  test deterministically and maps directly to sequence cursors.
- Unlimited retention. Rejected as unsafe.

## Decision 7 - Fail-safe append/read behavior

**Decision**: Store failures are public-safe and fail soft: live streaming continues if appending
replay data fails; reconnect degrades to retained in-memory/live behavior or an empty replay when
the durable store is unavailable.

**Rationale**: Replay durability improves resilience but must not make the primary live event stream
less reliable or expose backend details.

**Alternatives considered**:

- Fail the run/session when replay persistence fails. Rejected because reconnect storage is an
  auxiliary transport resilience feature.
- Surface raw backend errors. Rejected by public-safety requirements.
