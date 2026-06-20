# Data Model: Resumable SSE (Reconnect)

Additive; inside `loopplane.webapi`. No event-schema/content/runtime change. Per
[ADR 0006](../../docs/adr/0006-resumable-sse.md).

## SessionEntry (modified — additive)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `events` | `MemoryObjectReceiveStream[str]` | existing — the live SSE channel (unchanged). |
| `replay_buffer` | `deque[tuple[int, str]] \| None` | NEW — bounded `(sequence, frame)` ring buffer (`maxlen=N`); `None` when disabled (default) → byte-identical. |

The session sink (in `run_session`): when the buffer is enabled, builds the frame as
`id: <event.sequence>\ndata: <serialize_event>\n\n`, appends `(event.sequence, frame)` to
`replay_buffer`, and sends it live. When disabled: the existing `data: <serialize_event>\n\n` only
(no `id:`, no buffer).

## SSE frame (modified — additive, only when enabled)

| Line | Value | Notes |
| ---- | ----- | ----- |
| `id:` | `event.sequence` | NEW — the monotonic per-session sequence (only when the buffer is enabled). |
| `data:` | `serialize_event(event)` | existing — unchanged payload. |

## Reconnect (the events endpoint)

| Input | Behavior |
| ----- | -------- |
| `Last-Event-ID` header (int) + buffer enabled | Replay `replay_buffer` entries with `sequence > last_id` (in order), then drain live, skipping frames with `sequence ≤ max-replayed` (dedup). |
| no/garbage `Last-Event-ID`, or buffer disabled | Stream live from now (the existing behavior). |

## Rules (from FRs + ADR 0006)

| Rule | Source |
| ---- | ------ |
| `id:` line = event sequence (when enabled) | FR-001, D1 |
| bounded per-session ring buffer on SessionEntry | FR-002, D2 |
| Last-Event-ID → replay seq > id, then live, deduped | FR-003, D3 |
| default-off byte-identical (no id:, no buffer) | FR-004, D4 |
| fail-safe (missing/garbage/too-old id; gone-client safety) | FR-005, D5 |
| additive, confined to webapi; ADR 0006 | FR-006 |
| in-memory + per-session; durable resume DEFERRED | FR-007, D6 |
