# Feature Specification: Resumable SSE (Reconnect)

**Feature Branch**: `058-sse-reconnect`

**Created**: 2026-06-20

**Status**: Draft — **plan authors a small ADR (0006); no maintainer consult**

**Input**: User description: "Resumable server-side SSE for the session event stream (gap G23): add an in-memory bounded per-session ring buffer + an SSE `id:` line carrying the existing event `sequence`, and replay missed frames on reconnect via the standard `Last-Event-ID` request header. Unit 058, Tier-4. Additive + default-off (byte-identical when the buffer is disabled). Durable cross-process resume is DEFERRED. A small ADR records the webapi streaming pass-through → retained-buffer contract (Const VI)."

## ⚠️ Boundary note (read first)

The webapi SSE layer is today a **pure pass-through consumer** of the recorded normalized event
stream (`streaming.py`: each frame is `serialize_event(event)`; never a re-emitter — Const VI). This
unit adds a **server-side retained per-session buffer + replay** — a change to that pass-through
contract, so the plan authors a **small ADR (0006)** (no maintainer consult; pre-approved as a small
ADR). Everything is **additive + default-off**: with the buffer disabled (default) the SSE frames +
behavior are byte-identical to today. Reuses the existing monotonic event `sequence`
(`envelope.py:46`) as the SSE event id. **Durable cross-process resume is out of scope (deferred).**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reconnect resumes without losing events (Priority: P1)

A client streaming a session's events (`GET /sessions/{id}/events`) drops its connection mid-run and
reconnects with the standard `Last-Event-ID` header; it receives the events it missed (those with a
sequence after its last-seen id) and then continues live — no gap, no full replay from the start.

**Why this priority**: This is gap G23 — today a dropped SSE connection loses any events emitted
while disconnected (the stream is live-only); resumable SSE is the resilience win.

**Independent Test** (offline, in-process): subscribe to a session stream, capture some frames with
their `id:`, drop the connection, emit more events, reconnect with `Last-Event-ID = <last id>`, and
assert the missed frames (and only those) are replayed, then the live stream continues.

**Acceptance Scenarios**:

1. **Given** the buffer enabled + a session stream, **When** a client reconnects with
   `Last-Event-ID`, **Then** it receives the buffered frames with a sequence greater than that id (in
   order), then continues live.
2. **Given** each streamed frame, **When** it is sent, **Then** it carries an `id:` line equal to the
   event's monotonic `sequence`.

---

### User Story 2 - Bounded buffer + default-off byte-identity (Priority: P1)

The per-session buffer is bounded (a ring buffer of the most recent N frames); when disabled (the
default) there is no buffer, no `id:` line, and the stream is byte-identical to today.

**Why this priority**: The retained buffer must be bounded (no unbounded memory growth) and must
impose nothing when not enabled (preserve the pass-through default).

**Independent Test**: with the buffer disabled, the SSE frames + behavior match pre-058 exactly;
with it enabled at size N, only the last N frames are retained (older frames are dropped — a
reconnect past the retained window gets what remains + continues live).

**Acceptance Scenarios**:

1. **Given** the buffer disabled (default), **When** a client streams, **Then** frames have no `id:`
   line and behavior is byte-identical to today (no buffer retained).
2. **Given** the buffer at size N, **When** more than N events are emitted, **Then** only the last N
   are retained (bounded memory); a reconnect replays what remains.

---

### User Story 3 - Resilient + contained (Priority: P2)

A reconnect with a missing/garbage/too-old `Last-Event-ID` degrades gracefully (replays what's
retained or nothing, then continues live — never a crash, never a duplicate of already-seen events
beyond the buffer window). The buffer is per-session + in-memory; it does not survive a process
restart (durable resume deferred).

**Why this priority**: The reconnect path must be fail-safe (the existing SSE fail-safe posture) and
honest about its in-memory scope.

**Independent Test**: a reconnect with no/garbage `Last-Event-ID` → starts the live stream (no
crash); a too-old id (beyond the retained window) → replays the retained window, then live.

**Acceptance Scenarios**:

1. **Given** a missing/garbage `Last-Event-ID`, **When** a client connects, **Then** it streams live
   (no crash, no error).
2. **Given** an id older than the retained window, **When** a client reconnects, **Then** it gets the
   retained frames (a best-effort resume), then live.

---

### Edge Cases

- **buffer disabled (default)**: no `id:` line, no buffer → byte-identical.
- **`Last-Event-ID` missing/garbage**: live stream from now (no crash).
- **id beyond the retained window**: replay the retained window, then live (best-effort).
- **slow/gone client on reconnect**: the existing SSE fail-safe (a gone client never crashes/hangs
  the run) is preserved.
- **process restart**: the in-memory buffer is lost (durable cross-process resume deferred).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each streamed SSE frame (when the buffer is enabled) MUST carry an `id:` line equal to
  the event's monotonic `sequence` (`envelope.py:46`).
- **FR-002**: The session event stream MUST retain a **bounded, in-memory, per-session ring buffer**
  of the most recent N frames (N configurable; older frames dropped when full).
- **FR-003**: On a `GET /sessions/{id}/events` request carrying a `Last-Event-ID` header, the stream
  MUST first replay the buffered frames with a `sequence` greater than that id (in order), then
  continue live.
- **FR-004**: The feature MUST be **default-off / byte-identical**: when the buffer is disabled (the
  default) there is no `id:` line, no retained buffer, and the SSE frames + behavior match today.
- **FR-005**: The reconnect path MUST be **fail-safe**: a missing/garbage/too-old `Last-Event-ID`
  degrades gracefully (replay what's retained or nothing, then live) — never a crash; the existing
  gone/slow-client safety (a dropped client never crashes/hangs the run) is preserved.
- **FR-006**: The capability MUST be **additive**, confined to `loopplane.webapi` (streaming + the
  session entry + the endpoint + a config knob); no runtime/loop/gateway/event-schema/content change.
  The plan authors a **small ADR (0006)** recording the pass-through → retained-buffer contract (VI).
- **FR-007**: The buffer is **in-memory + per-session**; durable cross-process resume is **DEFERRED**
  (documented; a later unit).

### Key Entities *(include if feature involves data)*

- **Per-session SSE ring buffer**: a bounded deque of recent `(sequence, frame)` on the session
  entry; size N configurable (0/None = disabled = byte-identical).
- **SSE `id:` line**: the event's monotonic `sequence` surfaced as the SSE event id.
- **`Last-Event-ID`**: the standard SSE reconnect header the client echoes; drives replay.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the buffer enabled, a reconnect with `Last-Event-ID` replays exactly the missed
  frames (sequence > id) in order, then continues live — in 100% of covered scenarios.
- **SC-002**: With the buffer disabled (default), SSE frames + behavior are byte-identical to today
  (no `id:` line, no buffer); the existing webapi/streaming tests pass unchanged.
- **SC-003**: The buffer is bounded (only the last N frames retained); a missing/garbage/too-old
  `Last-Event-ID` never crashes (graceful degrade). No runtime/event-schema/content change.

## Assumptions

- Reuses the existing monotonic event `sequence` (`envelope.py:46`) as the SSE id; reuses the
  existing `GET /sessions/{id}/events` stream (`app.py:275`) + `streaming.py` frame format + the
  fail-safe gone-client handling; the buffer lives on the session entry (`sessions.py`).
- The config knob (buffer size; 0/None = off) is supplied where the webapi app is created (the
  existing webapi config surface); default off → byte-identical.
- **Out of scope / DEFERRED**: durable cross-process / multi-worker resume (the in-memory buffer is
  lost on restart — a later unit, sequenced with G19/G20); resuming the one-shot `POST /runs/events`
  stream (it drives a fresh run; reconnect targets the long-lived session stream).
- Default-off; fail-safe; offline-testable (in-process); public-safe (frames are the existing
  `serialize_event`, no new content). The plan authors ADR 0006. Per Constitution IX the concept is
  borrowed but re-derived against this stream.
