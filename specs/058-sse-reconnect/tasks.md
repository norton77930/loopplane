# Tasks: Resumable SSE (Reconnect)

**Feature**: 058-sse-reconnect | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0006](../../docs/adr/0006-resumable-sse.md)

**Scope**: additive, a small ADR (0006) — a bounded per-session SSE replay buffer + an `id:` line +
`Last-Event-ID` replay on `GET /sessions/{id}/events`; default-off byte-identical; confined to
`loopplane.webapi`. In-memory + per-session; durable cross-process resume deferred.

**Tests**: requested.

## Phase 1: Config knob (Foundational)

- [ ] T001 Add a per-session SSE replay-buffer-size knob to the webapi app factory (where
  `create_app` / the app is built — e.g. `create_app(..., sse_replay_buffer=0)`), default `0`/`None`
  = off. Thread it to `run_session` / `SessionEntry`. Default-off → byte-identical.

## Phase 2: Buffer + id: line on the session sink (P1) 🎯

- [ ] T002 In `src/loopplane/webapi/sessions.py`: add `replay_buffer: deque[tuple[int, str]] | None`
  to `SessionEntry` (a `deque(maxlen=N)` when enabled, else `None`). In `run_session`'s sink: when
  the buffer is enabled, build the frame as `id: {event.sequence}\ndata: {serialize_event(event)}\n\n`,
  append `(event.sequence, frame)` to the buffer, and send it live; when disabled, the existing
  `data: {serialize_event(event)}\n\n` only (no `id:`, no buffer) — byte-identical. (`event.sequence`
  is on every `_Envelope` event.)

## Phase 3: Reconnect replay on the endpoint (P1)

- [ ] T003 In `src/loopplane/webapi/app.py` `GET /sessions/{id}/events`: accept the `Last-Event-ID`
  request header (FastAPI `Header(None, alias="Last-Event-ID")`). When present + the buffer is
  enabled: first yield the buffered frames with `sequence > last_id` (in order), tracking the max
  replayed sequence; then drain the live `entry.events`, **skipping frames whose `sequence ≤ the max
  replayed`** (dedup — parse the `id:` from the frame, or track via the buffer). When absent / buffer
  disabled: the existing live drain (byte-identical). A garbage `Last-Event-ID` → treat as absent
  (live; no crash). Preserve the existing gone-client fail-safe.

## Phase 4: Tests (P1/P2)

- [ ] T004 Add webapi SSE reconnect tests (offline/in-process, mirroring the existing webapi/session
  test harness): (a) buffer enabled — each frame carries `id: <sequence>`; (b) reconnect with
  `Last-Event-ID` replays the missed frames (seq > id) in order with no duplicate, then live; (c)
  default-off (buffer disabled) — no `id:` line, no buffer, byte-identical (the existing
  webapi/streaming tests still pass); (d) bounded — more than N events → only the last N retained;
  (e) fail-safe — a missing/garbage/too-old `Last-Event-ID` → live, no crash.

## Phase 5: Gates

- [ ] T005 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-off byte-identity). Confirm the structural audits
  (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the events
  serialize/`SCHEMA_VERSION` tests (unchanged — no event-schema change) + the existing webapi/session
  suite pass. No new public name expected (api-reference unchanged unless a name is exported).

## Dependencies

- T001 → T002 → T003 → T004 → T005 (gates last).

## Implementation strategy

- Confined to `loopplane.webapi` (config knob + sessions.py + app.py + tests). May be done inline or
  via a fork; then the four gates + the structural audits + an adversarial verify (default-off
  byte-identity, the dedup-by-sequence correctness [no loss / no dup], the bounded buffer, fail-safe
  reconnect, no event-schema change) before commit — Workflow if available, else MANUAL. Commit only
  on a clean review / GO.
- Additive; ADR 0006; in-memory + per-session; durable resume deferred.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 1 low (informational). 100% requirement
coverage (FR-001..FR-007 and SC-001..003 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ **ADR 0006** ↔ data-model ↔ contract ↔ tasks agree (the
`id:`=sequence line; a bounded `deque(maxlen=N)` per-session buffer on `SessionEntry`; the
`Last-Event-ID` replay [seq > id] then live with dedup-by-sequence; default-off byte-identity;
fail-safe; in-memory + per-session). **Additive — a small ADR (0006)**: confined to
`loopplane.webapi`; no runtime/loop/gateway change; no event-schema/SCHEMA_VERSION/content change
(the frame payload is the existing `serialize_event`; the pass-through → retained-buffer contract is
recorded in ADR 0006, Const VI). No Constitution violation (I/IV/V/VI/X). Low note (informational):
the dedup-by-sequence (T003) is the load-bearing correctness point — replay then live must deliver
each frame exactly once (track the max replayed sequence; skip live frames at/below it); verify
no-loss + no-dup at implement, incl. the too-old-id and bounded-eviction cases. **Cleared for
`/speckit-implement`.**
