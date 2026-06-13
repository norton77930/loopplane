# Research: Observability & Debug-Console Layer (Phase-10)

Phase-0 decisions for `loopplane.inspect`. Every decision composes the public Phase-1/3 event/state
contracts; the live buses and run driving stay the runtime's, and reconstruction stays Phase-3's.

## Inherited context, no re-derivation (NFR-003, FR-062)

The layer consumes these **public** surfaces verbatim and adds only read-only transforms above them:

| Surface | Source (public) | Used by |
|---|---|---|
| `LoopEvent` (`type`, `sequence`, `loop_id`, `loop_definition_id`, `iteration_index`, `session_id`) | `loopplane.engineering` | loop diagnostics, trace, timeline |
| `LoopEventType` (10 lifecycle types) + `reconstruct_state` / `LoopState` / `LoopOutcome` | `loopplane.engineering` | loop diagnostics (latest-state fields) |
| `RuntimeEvent` (a discriminated union; each carries a `type` literal + a monotonic `sequence`) | `loopplane.events` | run diagnostics, trace, timeline |
| `TerminationReason` | `loopplane.events` | run diagnostics (the termination reason) |

The layer reads only these **metadata** fields; it never reads a content-bearing payload value.

## Decision 1 — Metadata-only by construction

- **Decision**: every transform reads only `type`, `sequence`, ids, and a small set of declared public-safe
  metadata fields (the loop terminal status, the run `TerminationReason`). It never reads a content-bearing
  payload value (assistant text, tool arguments/outputs).
- **Rationale**: FR-001/FR-060/NFR-002/SC-003 — the layer *cannot* leak content because it never reads it.
- **Alternatives rejected**: *Carrying the raw payload through the trace* — would surface content/arguments;
  rejected (metadata-only).

## Decision 2 — Loop diagnostics count events and reuse `reconstruct_state`

- **Decision**: `loop_diagnostics(events)` counts `LoopEventType`s (iterations from `loop_iteration_*`,
  retries from `retry_scheduled`, repairs from `repair_requested`, human-review from
  `human_review_requested`) and reuses the Phase-3 `reconstruct_state(events)` for the latest validation /
  evaluation outcomes and the terminal status. An empty stream yields an empty report; an unknown type is
  skipped.
- **Rationale**: FR-010/FR-011/SC-008 — reusing reconstruction guarantees the latest-state fields match
  Phase-3 and avoids re-implementation (FR-062).
- **Alternatives rejected**: *Re-deriving the latest state in this layer* — duplicates Phase-3; forbidden.

## Decision 3 — Run diagnostics count by the runtime event `type` discriminator

- **Decision**: `run_diagnostics(events)` counts by `event.type`: tool calls (`tool-call-started`), turns
  (`turn-completed`), errors (`diagnostic`), and reads the termination reason from the `run-terminated`
  event. Metadata only; an empty stream ⇒ empty; an unknown type ⇒ skipped.
- **Rationale**: FR-020/FR-021 — counts and the termination reason are public-safe metadata; the `type`
  discriminator is uniform across the `RuntimeEvent` union.
- **Alternatives rejected**: *Reading payload bodies for richer stats* — risks leaking content; rejected.

## Decision 4 — The trace is a nested span tree keyed by public ids

- **Decision**: `build_trace(loop_events, run_events_by_session)` builds a `Trace` of `TraceSpan`s nesting
  loop → iteration → run → (tool call / turn). Iterations group by `iteration_index`; a run span is keyed by
  `session_id` and its children come from the correlated `RuntimeEvent` stream (`run_events_by_session[sid]`);
  spans carry ids, types, `sequence`, and child counts only. A loop event whose `session_id` has no
  correlated stream yields a run span with no children.
- **Rationale**: FR-030/FR-031/FR-032 — a normalized, metadata-only trace a viewer could render; correlation
  is by the public `session_id`.
- **Alternatives rejected**: *Flattening to a list* — loses the loop/iteration/run structure a debugger needs.

## Decision 5 — The timeline orders by monotonic sequence and pairs start/complete

- **Decision**: `build_timeline(events)` produces `TimelineEntry`s ordered by `sequence` (stable sort), pairs
  a started event with its completing event (e.g., `tool-call-started` ↔ `tool-call-completed`,
  `loop_iteration_started` ↔ `loop_iteration_completed`), and records nesting depth. A started event with no
  completion is an explicit **open** span; a duplicate/out-of-order sequence is sorted deterministically.
- **Rationale**: FR-040/FR-041/SC-007 — sequence ordering is reproducible (unlike wall-clock); explicit open
  spans keep it fail-safe.
- **Alternatives rejected**: *Wall-clock ordering / durations* — non-deterministic and platform-dependent;
  reserved (FR-094).

## Decision 6 — Replay feeds a recorded stream to a sink, bracketed by markers

- **Decision**: `replay(events, sink)` awaits `sink(event)` for each recorded event in recorded order,
  bracketed by an internal replay start / complete signal; it reads recorded events only and starts no run.
- **Rationale**: FR-050/FR-051/SC-009 — re-feeding a captured stream for re-inspection; the markers mirror
  the Phase-1 `replay-started` / `replay-completed` semantics without re-emitting the live bus.
- **Alternatives rejected**: *Re-running the loop to regenerate events* — would drive a run; forbidden
  (read-only).

## Decision 7 — Determinism, fail-safe, read-only, non-duplication are first-class

- **Determinism (NFR-001/SC-002/SC-007)**: no I/O, network, clock, or randomness; ordering is by `sequence`.
- **Fail-safe (NFR-005/SC-004)**: an empty stream ⇒ empty result; an unknown event type ⇒ skipped; an
  unpaired start ⇒ an open span; a missing correlated run ⇒ a childless span — never a crash.
- **Read-only (NFR-006/SC-005)**: the layer drives zero runs and re-emits zero live-bus events; it only
  consumes recorded streams and returns value structures.
- **Non-duplication (FR-062/SC-008)**: reuses `reconstruct_state`; no event serialization or run driving is
  re-implemented.

## Decision 8 — Constitution VI alignment (consume, never compete)

- **Decision**: the layer is a pure **consumer** of recorded normalized events; it produces value structures
  for a future, separate viewer and never emits onto, wraps, or re-orders the live Runtime/Loop Event buses.
- **Rationale**: Constitution VI — streaming/history/trace/observability consume normalized events on the
  consumer's side of the bus; this layer is exactly that, offline.
