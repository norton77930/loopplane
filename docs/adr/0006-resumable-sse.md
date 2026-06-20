# ADR 0006: Resumable SSE (server-side reconnect buffer)

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (pre-approved as a *small* ADR for unit 058 at the Tier-4 plan
  step); spec 058 (sse-reconnect).
- **Related**: Constitution **VI** (the webapi SSE streaming contract — today a *pure pass-through
  consumer* of the recorded normalized stream; this adds a server-side *retained* per-session buffer
  + replay), **IV** (webapi boundary), **X** (additive, default-off, byte-identical when disabled,
  reversible). Sixth ADR (after 0001–0005).

## Context

`loopplane.webapi`'s SSE layer (`streaming.py`, `sessions.py`) is a **pure pass-through consumer**:
each frame is the public `serialize_event(event)`, forwarded once over an unbounded in-process
channel; it never re-emits or retains (Const VI). Gap G23 wants **reconnect resilience**: a client
whose SSE connection drops should resume without losing events. The standard SSE mechanism is an
`id:` line per frame + the client's `Last-Event-ID` header on reconnect, with the server replaying
events after that id. The session event stream (`GET /sessions/{id}/events`, draining
`SessionEntry.events`) is the long-lived stream this targets; the one-shot `POST /runs/events` drives
a fresh run and is out of scope. The monotonic event `sequence` (`envelope.py:46`, on every
`_Envelope` event) is the natural SSE id.

## Decision

- **D1 — SSE `id:` line from the event sequence.** When the reconnect buffer is enabled, each
  session SSE frame carries `id: <event.sequence>` (the monotonic, gap-free per-session sequence).
- **D2 — Bounded in-memory per-session ring buffer.** `SessionEntry` retains a bounded ring buffer
  (a `deque(maxlen=N)`) of recent `(sequence, frame)`; the session sink appends to it as it forwards
  each frame. Bounded → no unbounded memory growth.
- **D3 — Replay on `Last-Event-ID`.** `GET /sessions/{id}/events` reads the `Last-Event-ID` request
  header; if present (and the buffer is enabled), it first replays the buffered frames with a
  `sequence` greater than that id (in order), then continues the live stream — **deduping by
  sequence** so a frame is never delivered twice (the live drain skips any frame whose sequence was
  already replayed).
- **D4 — Default-off, byte-identical.** The buffer size is configurable where the webapi app is
  created; `0`/`None` (the default) means **no buffer, no `id:` line** — the SSE frames + behavior
  are byte-identical to pre-058. The existing webapi/streaming tests pass unchanged.
- **D5 — Fail-safe.** A missing / malformed / too-old `Last-Event-ID` degrades gracefully (replay
  what's retained, or nothing, then live) — never a crash. The existing gone/slow-client safety (a
  dropped client never crashes or hangs the run/session) is preserved.
- **D6 — In-memory + per-session; durable resume DEFERRED.** The buffer lives in the process; it does
  not survive a restart and is not shared across workers. Durable / cross-process / multi-worker
  resume is **out of scope** — a later unit, sequenced with the G19 (Postgres) / G20 (multi-tenant)
  foundation.

## Consequences

- **Enables G23**: standard `Last-Event-ID` reconnect resilience for the session SSE stream,
  contained + default-off.
- **A webapi contract change (VI), recorded here**: the SSE layer goes from a pure pass-through to
  one that *retains* a bounded per-session buffer and *replays* it — additive (default-off) and
  reversible (remove the buffer + the `id:` line → today's surface). No event-schema / SCHEMA_VERSION
  / content change; the frame payload is still the existing `serialize_event`.
- **Reuse-first**: the existing monotonic event `sequence`, the `GET /sessions/{id}/events` stream,
  the `streaming.py` frame format, and the fail-safe gone-client handling are all reused.
- **Deferred (documented)**: durable cross-process / multi-worker resume; resuming the one-shot
  `POST /runs/events` stream. Out of scope unless a future unit + ADR revisits them.
