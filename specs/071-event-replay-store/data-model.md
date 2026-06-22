# Data Model: Event Replay Store

## EventReplayRecord

One replayable session event frame.

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `session_id` | string | yes | Existing session id. |
| `sequence` | integer | yes | Existing monotonic runtime event sequence; unique per session. |
| `principal_id` | string | yes | Owner at record time; used for defense-in-depth scoping. |
| `frame` | string | yes | Exact SSE frame sent or replayed for this event. |
| `recorded_at` | aware datetime | yes | Store-side append time. |

**Validation**:

- `session_id`, `principal_id`, and `frame` are non-empty.
- `sequence` is non-negative.
- `(session_id, sequence)` is unique.
- `frame` must start with `id: <sequence>` when durable replay is enabled.

## EventReplayStore

Host-selected replay storage boundary.

| Operation | Input | Output | Behavior |
| --------- | ----- | ------ | -------- |
| `append` | `EventReplayRecord` | none | Persists one record; per-session appends are serialized where needed. |
| `load_after` | `session_id`, `principal_id`, `after_sequence`, `limit` | records + problems | Returns ordered records with sequence greater than the cursor. |
| `delete_session` | `session_id` | none | Removes replay data for a session; idempotent. |

**Validation**:

- `load_after` must return records ordered by sequence.
- `load_after` must filter by principal id.
- Corrupt stored entries are skipped and reported as public-safe problems.
- Unknown session yields an empty result.

## Retention Policy

Operator-selected bound for replay storage.

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `max_events_per_session` | integer | yes | Positive integer for configured stores. |
| `poll_interval_seconds` | float | no | Bounded store-tail interval for cross-worker reconnect. |

**Validation**:

- `max_events_per_session` must be greater than zero when a durable store is configured.
- `poll_interval_seconds` must be positive when store polling is enabled.

## Backend Record Shapes

### File Backend

One JSONL file per session, storing serialized `EventReplayRecord` objects. Pruning rewrites or
compacts the session file to the retained window.

### SQLite Backend

One `event_replay` table with primary key `(session_id, sequence)` and columns for principal id,
recorded timestamp, and frame data. Pruning deletes older rows outside the retained window.

### Postgres Backend

Same logical shape as SQLite, using the optional Postgres dependency and the sync thread-bridge
posture. Credentials are host configuration and are never logged or serialized.

## State Transitions

```text
Runtime event emitted
  -> session sink serializes SSE frame
  -> optional durable replay append
  -> live frame delivery

Client reconnects with cursor
  -> route verifies session ownership
  -> durable replay loads records after cursor
  -> replay frames emitted in sequence order
  -> live channel and/or store polling continues after max emitted sequence
```
