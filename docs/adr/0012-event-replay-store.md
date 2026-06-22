# ADR 0012: Durable Event Replay Store

- **Status**: Accepted (2026-06-22)
- **Deciders**: LoopPlane maintainer (roadmap board pre-settled this boundary for unit 071);
  spec 071 (event-replay-store).
- **Related**: ADR 0006 (resumable SSE in-memory buffer), ADR 0008 (Postgres sync thread-bridge),
  Constitution **IV** (clear webapi replay-store boundary), **VI** (Runtime Event Bus unchanged),
  **VII** (public-safe stored frames and diagnostics), **X** (additive, reversible, tested).

## Context

Unit 058 added resumable session SSE through an in-memory per-session ring buffer. That solved
short disconnects when the client returns to the same process, but explicitly deferred durable
cross-process and multi-worker replay. Production hosts may route a reconnect to another worker or
restart the worker that held the ring buffer. The runtime already emits normalized events with
monotonic sequence numbers; the webapi already serializes them into public SSE frames.

The design question is how to persist enough transport replay data without moving event ownership
out of the Runtime Event Bus or adding a new distributed event system.

## Decision

- **D1 - New EventReplayStore boundary under webapi.** Add a small host-selected replay store for
  serialized session SSE frames. It is a transport replay boundary, not a runtime event source.
- **D2 - Key by session and sequence.** Each replay record is identified by `(session_id,
  sequence)` and stores the exact SSE frame, principal id, and recording timestamp.
- **D3 - Replay after Last-Event-ID.** Reconnect handling loads records with sequence greater than
  the supplied cursor, emits them in order, and deduplicates by sequence when merging with live
  delivery.
- **D4 - Store-polled tailing for cross-worker reconnect.** When no local live channel is available,
  a reconnecting stream may poll the shared replay store after the last emitted sequence. This gives
  durable catch-up and live tailing without adding backend-specific notifications or a distributed
  pub/sub layer.
- **D5 - Default unchanged.** With no durable store configured, unit 058's in-memory ring and
  disabled-buffer behavior remain unchanged. No base install gets a new dependency.
- **D6 - File, SQLite, and optional Postgres backends.** File and SQLite provide local durable
  options. Postgres uses the existing optional dependency posture and sync thread-bridge from ADR
  0008.
- **D7 - Retention is required.** Durable replay stores must enforce a configured maximum retained
  event count per session.
- **D8 - Ownership and public safety.** Existing web/API owner checks happen before replay reads;
  records also carry principal id for defense in depth. Store failures and corruption produce only
  public-safe diagnostics.

## Consequences

- Enables durable G23 reconnect for session event streams without changing runtime event
  vocabulary, content model, termination reasons, or `SCHEMA_VERSION`.
- Adds one optional webapi storage seam and three backend implementations.
- Keeps the existing in-memory replay path as the default and rollback path.
- Store polling is simpler and portable but not as efficient as backend-native notifications. Native
  notifications or a full distributed event bus are explicitly deferred.

## Deferred

- Distributed pub/sub, database notifications, and fan-out coordination.
- One-shot `POST /runs/events` reconnect.
- Migration tooling beyond table creation for the first Postgres replay backend.
- Authoritative retention by wall-clock duration; the first slice uses count-based retention.
