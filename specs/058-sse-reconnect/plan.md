# Implementation Plan: Resumable SSE (Reconnect)

**Branch**: `058-sse-reconnect` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/058-sse-reconnect/spec.md`

**Boundary**: settled by **[ADR 0006](../../docs/adr/0006-resumable-sse.md)** (a small, maintainer-
pre-approved ADR; authored at this plan step, no consult). The webapi SSE layer goes from a pure
pass-through consumer to one that retains a bounded per-session buffer + replays it (Const VI).
Additive + default-off (byte-identical when disabled).

## Summary

Make the session SSE stream resumable. When a per-session reconnect buffer is enabled: (1) the
session sink prefixes each frame with `id: <event.sequence>` (the monotonic per-session sequence,
`envelope.py:46`) and appends `(sequence, frame)` to a bounded `deque(maxlen=N)` on `SessionEntry`;
(2) `GET /sessions/{id}/events` reads the `Last-Event-ID` header and, if present, replays the
buffered frames with `sequence` greater than that id (in order, deduped by sequence) before
continuing the live drain of `entry.events`. With the buffer disabled (the default, size `0`/`None`)
there is no `id:` line, no buffer, and the stream is byte-identical to today. Confined to
`loopplane.webapi`; no runtime/loop/gateway/event-schema/content change. In-memory + per-session;
durable cross-process resume deferred.

## Technical Context

**Language/Version**: Python 3.11+; `collections.deque(maxlen=N)`.

**Primary Dependencies**: none new — reuses `anyio` streams, the existing `serialize_event`, and the
event `sequence`.

**Storage**: in-memory bounded ring buffer on `SessionEntry` (no persistence).

**Testing**: pytest, offline/in-process (the existing webapi/SSE test harness): a session stream
emits frames with `id:`; a reconnect with `Last-Event-ID` replays the missed frames (seq > id), no
dup; default-off → no `id:` line + byte-identical; bounded (only the last N retained); a
missing/garbage/too-old id degrades gracefully.

**Target Platform**: the web/API host (`loopplane.webapi`).

**Constraints**: additive; default-off byte-identical; bounded buffer; fail-safe reconnect; reuse
the existing sequence + stream + frame format; no new dependency; no runtime/event change. ADR 0006.
Durable cross-process resume deferred.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007 + ADR 0006. ✅
- **IV. Boundary**: Confined to `loopplane.webapi`; the runtime/event core is untouched (recorded in
  ADR 0006). ✅
- **V. Tool Gateway**: N/A — no tool/execution path. ✅
- **VI. Event Bus**: No event-schema/SCHEMA_VERSION/content change; the frame payload is still the
  existing `serialize_event`. The webapi pass-through → retained-buffer contract change is recorded
  in ADR 0006 (the only VI-relevant surface; the normalized stream itself is unchanged). ✅
- **X. Testable Evolution**: Additive; default-off byte-identical; reversible; offline-tested. ✅

**Result**: PASS — additive, a small maintainer-pre-approved ADR (0006); no breaking 011/001
contract change, no event-schema change. Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/058-sse-reconnect/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/sse-reconnect.md
└── checklists/requirements.md
docs/adr/0006-resumable-sse.md   # the small boundary decision
```

### Source Code (repository root)

```text
src/loopplane/webapi/sessions.py    # MODIFIED: SessionEntry gains a bounded ring buffer (deque
                                    #   maxlen=N); the sink prefixes id:<seq> + appends (seq, frame)
                                    #   when the buffer is enabled (default-off: no buffer, no id:)
src/loopplane/webapi/app.py         # MODIFIED: GET /sessions/{id}/events reads Last-Event-ID and
                                    #   replays buffered frames (seq > id, deduped) then streams live
src/loopplane/webapi/<config>       # MODIFIED: a buffer-size knob on the webapi app factory
                                    #   (default 0/None = off = byte-identical)
tests/<webapi sse tests>            # NEW/MODIFIED: reconnect replay + id: line + default-off + bounds
```

**Structure Decision**: The buffer lives on `SessionEntry` (per-session, bounded). The session sink
(in `run_session`) is the single append point — it already serializes each event; it gains the
`id:` prefix + the buffer append, both gated on the buffer being enabled (so default-off is
byte-identical). The events endpoint gains the `Last-Event-ID` read + replay-then-live, **deduping by
sequence** (track the max replayed sequence; skip live frames at/below it) — the key correctness
point, since the live channel may still hold frames also present in the replay buffer. The buffer
size is a webapi-app-factory knob (default off). No change outside `loopplane.webapi`.

## Complexity Tracking

> A bounded in-memory buffer + an `id:`/`Last-Event-ID` replay on an existing stream — the standard
> resumable-SSE pattern. Additive, default-off, a small ADR (0006). The one subtlety (dedup by
> sequence across replay + live) is a local correctness concern, not new architecture. Not a
> Constitution violation.
