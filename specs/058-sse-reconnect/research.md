# Research: Resumable SSE (Reconnect)

Settled by **[ADR 0006](../../docs/adr/0006-resumable-sse.md)** (small, maintainer-pre-approved). No
open `NEEDS CLARIFICATION`.

## Decision 1 — SSE id from the event sequence (ADR 0006 D1)

**Decision**: When the buffer is enabled, prefix each session SSE frame with `id: <event.sequence>`
(every `_Envelope` event carries the monotonic, gap-free per-session `sequence`, `envelope.py:46`).

**Rationale**: The standard SSE reconnect protocol uses the `id:` line + the client's `Last-Event-ID`
header; the existing sequence is the perfect monotonic id. No new id scheme needed.

## Decision 2 — Bounded per-session ring buffer on SessionEntry (ADR 0006 D2)

**Decision**: `SessionEntry` retains a `deque(maxlen=N)` of `(sequence, frame)`; the session sink (in
`run_session`) appends to it as it forwards each frame.

**Rationale**: Bounded → no unbounded memory growth; per-session matches the stream's scope; the sink
is the single, natural append point.

**Alternatives considered**: an unbounded buffer (rejected — memory growth); a global buffer (rejected
— per-session is the right scope + isolation).

## Decision 3 — Replay on Last-Event-ID, dedup by sequence (ADR 0006 D3)

**Decision**: `GET /sessions/{id}/events` reads the `Last-Event-ID` header; if present + buffer
enabled, replay the buffered frames with `sequence` greater than that id (in order), then drain the
live `entry.events` — **skipping any live frame whose sequence ≤ the max replayed** (dedup), since the
live channel may still hold frames also in the replay buffer.

**Rationale**: Correct resume with no loss + no duplicate; the dedup-by-sequence is the load-bearing
correctness point. FastAPI exposes the request header.

## Decision 4 — Default-off byte-identity + fail-safe (ADR 0006 D4/D5)

**Decision**: A buffer-size knob on the webapi app factory; `0`/`None` (default) → no buffer, no
`id:` line → byte-identical. A missing/garbage/too-old `Last-Event-ID` degrades gracefully (replay
what's retained or nothing, then live; never crash). The existing gone/slow-client safety is kept.

**Rationale**: Impose nothing on existing embedders; preserve the fail-safe SSE posture.

## Decision 5 — In-memory + per-session; durable resume deferred (ADR 0006 D6)

**Decision**: The buffer is in-process + per-session (lost on restart, not cross-worker). Durable /
cross-process / multi-worker resume is a later unit (sequenced with G19/G20).

**Rationale**: The in-memory variant delivers the resilience win within a process now; durability is
a Postgres/multi-tenant-shaped problem.

## Out of scope

Durable cross-process / multi-worker resume; resuming the one-shot `POST /runs/events` stream (it
drives a fresh run — reconnect targets the long-lived session stream).
