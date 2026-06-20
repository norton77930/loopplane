# Contract: Resumable SSE (Reconnect)

Additive resumability for the session SSE stream (`GET /sessions/{id}/events`). Active only when the
per-session reconnect buffer is enabled (a webapi-app-factory knob); default-off is byte-identical.
Per [ADR 0006](../../docs/adr/0006-resumable-sse.md).

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| webapi buffer-size knob | `int` (default `0`/`None` = off) | per-session SSE replay ring-buffer size. |
| SSE frame `id:` line | `event.sequence` | added only when the buffer is enabled. |
| `Last-Event-ID` (request header) | `int` | the standard SSE reconnect header; drives replay. |

## Behavior

| Case | Result |
| ---- | ------ |
| Buffer disabled (default) | No `id:` line, no buffer; SSE frames + behavior byte-identical to today. |
| Buffer enabled, each frame | Carries `id: <sequence>`; `(sequence, frame)` appended to a bounded `deque(maxlen=N)` on the session entry. |
| Reconnect with `Last-Event-ID` | Replays buffered frames with `sequence > id` (in order), then continues live — deduped by sequence (no frame twice). |
| `Last-Event-ID` missing / garbage | Streams live from now (no crash). |
| `Last-Event-ID` older than the retained window | Replays the retained window (best-effort), then live. |
| More than N events emitted | Only the last N retained (bounded memory); older dropped. |
| Slow / gone client (incl. on reconnect) | The existing fail-safe — never crashes/hangs the session. |

## Invariants

- Default-off (`0`/`None`) is byte-identical to pre-058 (no `id:`, no buffer); the existing
  webapi/streaming tests pass unchanged.
- The buffer is **bounded** (`deque(maxlen=N)`) + **per-session** + **in-memory** (lost on restart).
- Replay is **deduped by sequence** (a frame is delivered at most once across replay + live).
- Reconnect is **fail-safe** (missing/garbage/too-old id degrades gracefully; gone-client safety kept).
- No event-schema/SCHEMA_VERSION/content change; the frame payload is the existing `serialize_event`;
  confined to `loopplane.webapi` (V/VI intact, the contract change recorded in ADR 0006).
- Durable cross-process / multi-worker resume is out of scope (deferred); reconnect targets the
  long-lived session stream, not the one-shot `POST /runs/events`.
