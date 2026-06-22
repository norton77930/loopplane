# Implementation Plan: Event Replay Store

**Branch**: `071-event-replay-store` | **Date**: 2026-06-22 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from `specs/071-event-replay-store/spec.md`

**Boundary**: settled by **[ADR 0012](../../docs/adr/0012-event-replay-store.md)**, authored in
this plan step to materialize the roadmap-board decision. This extends unit 058's resumable SSE
contract from an in-memory per-session ring to an optional durable replay-store boundary while
leaving the normalized Runtime Event Bus unchanged.

## Summary

Add a host-selectable `EventReplayStore` for serialized session SSE frames keyed by
`(session_id, sequence)`. The session event sink appends the exact frame it streams when a store is
configured; reconnect handling can replay durable frames after `Last-Event-ID`, deduplicate against
live delivery by sequence, and optionally keep a reconnecting stream alive by polling the store when
the live in-process channel is not available on that worker. Default behavior remains the unit 058
in-memory ring / disabled-buffer path unless a durable store is explicitly configured.

## Technical Context

**Language/Version**: Python 3.11+; pydantic-free dataclasses/Protocols for the replay-store
boundary.

**Primary Dependencies**: Standard library for file/SQLite storage; existing optional
`loopplane[postgres]` extra for the Postgres backend; FastAPI/AnyIO already used by `webapi`.

**Storage**: New event replay stores: file JSONL, SQLite, and optional Postgres. Each stores
serialized SSE frames plus session id, sequence, principal id, and recorded timestamp.

**Testing**: pytest, offline. Unit/contract tests for store backends and replay merge logic; webapi
integration tests for reconnect, default unchanged behavior, retention, corruption, and owner
scoping. Optional live Postgres remains skip-gated or stubbed.

**Target Platform**: LoopPlane web/API host; embedded host surfaces unaffected unless they opt into
the webapi durable replay store.

**Project Type**: Python runtime library and web/API host.

**Performance Goals**: Append is one small record per normalized event; reconnect loads only a
bounded ordered range. Default path has no additional work when no durable store is configured.

**Constraints**: Additive; default-off; no new runtime event type, termination reason, content
block, or `SCHEMA_VERSION` bump; no Tool Gateway change; no frontend API shape change beyond more
resilient `Last-Event-ID` behavior.

**Scale/Scope**: Session event streams only. Covers durable catch-up and store-poll tailing for
multi-worker reconnect; does not introduce distributed push notification, a global event bus, or
full replay of one-shot run streams.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md`, this plan, ADR 0012, and upcoming tasks. PASS.
- **IV. Runtime Boundary Clarity**: Adds a new replay-store boundary under the webapi event-stream
  surface. Runtime event production remains owned by the existing Event Bus. PASS.
- **V. Tool Gateway Ownership**: No tool resolution, authorization, or execution change. PASS.
- **VI. Runtime Event Bus Ownership**: Stores and replays already-serialized normalized events; no
  event vocabulary or schema change. The webapi retained-replay boundary is recorded in ADR 0012.
  PASS.
- **VII. Public-Safe Documentation**: Specs and design use synthetic sessions and never include
  credentials, private paths, or raw backend connection data. PASS.
- **VIII. No SDK Replacement**: No external agent framework or runtime replacement. PASS.
- **X. Testable Evolution**: Bounded, optional, reversible, and covered by store contract plus
  webapi reconnect tests. PASS.

**Post-design re-check**: PASS. Research/design keep the durable replay store additive and
host-selected. The only notable operational cost is polling for cross-worker tailing; it is opt-in
with a bounded interval and does not alter default behavior. Complexity Tracking is not required.

## Project Structure

### Documentation (this feature)

```text
specs/071-event-replay-store/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── event-replay-store.md
└── checklists/
    └── requirements.md

docs/adr/0012-event-replay-store.md
```

### Source Code (repository root)

```text
src/loopplane/webapi/replay.py       # NEW: EventReplayStore Protocol + File/SQLite/Postgres stores
src/loopplane/webapi/sessions.py     # MODIFIED: append streamed frames to optional store; merge
                                     #   durable replay, in-memory replay, and live frames
src/loopplane/webapi/app.py          # MODIFIED: create_app store/retention knobs; session events
                                     #   route can replay from durable store after ownership check
src/loopplane/webapi/__init__.py     # MODIFIED only if new public exports are required
docs/api-reference.md                # MODIFIED only if new public names are exported
tests/contract/test_event_replay_store.py
tests/integration/test_webapi_replay_store.py
tests/unit/test_sse_reconnect.py
```

**Structure Decision**: Keep the replay store in `loopplane.webapi` because it stores SSE frames for
the web/API session stream, not raw runtime events or checkpoint records. The Protocol mirrors the
checkpoint backend style where useful, but remains its own boundary: append frame records,
load/replay records after a sequence, prune/delete per session, and tolerate corrupt rows. The
session route performs existing ownership checks before any replay read, while the store record also
carries `principal_id` for defense in depth.

## Agent Context Update

The official agent-context extension was invoked with `specs/071-event-replay-store/plan.md`, but
the PowerShell script skipped the update because its YAML parser fallback raised a syntax error. Per
repo policy, the `AGENTS.md` managed block was not edited manually.

## Complexity Tracking

> No constitution violations require justification.
