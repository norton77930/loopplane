# Implementation Plan: Observability & Debug-Console Layer

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-loopplane-observability-debug-console/spec.md`

## Summary

Build the **Observability & Debug-Console** layer (Phase-10) that makes a run or loop **inspectable after
the fact** — deterministically, public-safe, metadata-only, and offline. A new additive sub-package,
`loopplane.inspect`, ships read-only transforms over recorded event streams: **loop diagnostics** and **run
diagnostics** (metadata summaries), a **trace data model** (loop → iteration → run → tool/turn spans), a
**debug timeline** (sequence-ordered, start/complete pairing), and deterministic **event replay**. It
consumes the recorded Phase-3 **Loop Event** stream (correlated to Agent Runs by `session_id`, reusing
`reconstruct_state`) and the recorded Phase-1 **Runtime Event** stream — exactly as Constitution VI
prescribes for trace/observability consumers. It **never** drives, starts, or mutates a run or loop, never
re-emits or wraps the live buses, reads only metadata (counts, ids, types, sequences, public-safe reasons),
and ships **no** frontend. Design detail lives in [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–9).

**Primary Dependencies**: the public Phase-3 Loop Event / Loop State surface (`loopplane.engineering`:
`LoopEvent`, `LoopEventType`, `reconstruct_state`, `LoopState`, `LoopOutcome`) and the public Phase-1 Runtime
Event surface (`loopplane.events`: `RuntimeEvent` and its typed events, `TerminationReason`). Plus the
stdlib. **No new third-party dependency.**

**Storage**: None. The layer owns no store; it transforms recorded streams supplied by the caller into
in-memory value structures.

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted `LoopEvent` / `RuntimeEvent` streams + a recording replay sink are the
deterministic instruments (NFR-001, SC-002) — no run, no live bus.

**Target Platform**: Cross-platform library embedded in a host process; a pure-transform layer with no host,
transport, or UI dependency.

**Performance Goals**: Negligible — each transform is a linear pass over a recorded stream. Determinism
preserved (NFR-001).

**Constraints**: metadata-only (FR-001, NFR-002); read-only — drives no run, re-emits no live-bus event
(FR-002, NFR-006); sequence-ordered, never wall-clock (FR-003, SC-007); deterministic (NFR-001, SC-002);
tolerant of empty/malformed/unknown-type streams (FR-062, NFR-005, SC-004); reuses `reconstruct_state`
(FR-062, SC-008).

**Scale/Scope**: One new package (~5 modules), one example, one doc, unit/integration/contract suites.
**No Phase-1/2/3 source is modified.**

## Dependency on Phases 1 & 3

This phase is **strictly additive** and consumes only public event/state value types — it composes them and
re-derives none of them (NFR-003, FR-062):

- **Phase-3 (`loopplane.engineering`)**: `LoopEvent` (`type` / `sequence` / `loop_id` / `loop_definition_id`
  / `iteration_index` / `session_id` / `payload`), the `LoopEventType` vocabulary, and `reconstruct_state` /
  `LoopState` / `LoopOutcome` (loop diagnostics reuse reconstruction).
- **Phase-1 (`loopplane.events`)**: `RuntimeEvent` (a discriminated union; each event carries a `type`
  literal and a monotonic `sequence`) and `TerminationReason` — read for counts + the termination reason.

The layer reads only the public **metadata** fields (`type`, `sequence`, ids, the termination reason); it
never reads a content-bearing payload value, so it cannot leak content (FR-001, FR-060).

**Non-duplication guarantee (FR-062, SC-008)**: the layer contains no run/loop driving, no event
serialization, and no state-reconstruction logic. It reuses `reconstruct_state`; the live buses stay the
Phase-1/Phase-3 surfaces'; it only consumes recorded streams.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.inspect` depends on the public `loopplane.engineering`
(Loop Events / Loop State) and `loopplane.events` (Runtime Events); the runtime, loop, host, and every
loop-layer sibling have **zero** knowledge of the inspect layer.

```text
recorded streams (captured by the host)
     │ LoopEvent[]  +  {session_id: RuntimeEvent[]}
     ▼
loopplane.inspect.loop_diagnostics / run_diagnostics / build_trace / build_timeline / replay
     │ pure, deterministic, sequence-ordered, metadata-only transforms
     ▼
in-memory value structures (a future, separate viewer renders them) — NO live bus, NO run driven
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/inspect-boundary.md](./contracts/inspect-boundary.md)):

- The layer **drives no run** and **re-emits no live-bus event**: it transforms recorded streams into value
  structures (FR-002, FR-061, NFR-006).
- It reads **only metadata** fields and never a content-bearing payload value (FR-001, FR-060).
- It imports only `loopplane.engineering`, `loopplane.events`, and stdlib; it does **not** import
  `run_loop` / the controller / the host / the gateway, or a sibling layer (FR-061, NFR-003).

## Project Structure

### Documentation (this feature)

```text
specs/010-loopplane-observability-debug-console/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── observability.md       # diagnostics, trace, timeline, replay value contracts
│   └── inspect-boundary.md    # the read-only / metadata-only boundary + audit
├── checklists/requirements.md
└── tasks.md                   # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/inspect/
├── __init__.py        # public exports
├── base.py            # SequencedEvent protocol + count_by_type helper (FR-003)
├── diagnostics.py     # LoopDiagnostics + loop_diagnostics; RunDiagnostics + run_diagnostics (FR-010-FR-021)
├── trace.py           # TraceSpan + Trace + build_trace (FR-030-FR-032)
├── timeline.py        # TimelineEntry + Timeline + build_timeline (FR-040-FR-041)
└── replay.py          # replay over a recorded stream + start/complete markers (FR-050-FR-051)

examples/
└── inspect_quickstart.py  # runnable: diagnose + trace + timeline + replay a scripted stream (public-safe)

docs/
└── observability-debug.md # public-safe guide: loop/run diagnostics -> trace -> timeline -> replay

tests/
├── unit/
│   └── test_inspect_core.py        # diagnostics counters, empty/unknown-type tolerance, timeline ordering
├── integration/
│   ├── test_inspect_us1.py         # US1: loop diagnostics from a Loop Event stream (SC-001/002/008)
│   ├── test_inspect_us2.py         # US2: run diagnostics from a Runtime Event stream (SC-003/004)
│   ├── test_inspect_us3.py         # US3: trace tree loop->iteration->run->tool/turn, metadata-only (SC-003)
│   ├── test_inspect_us4.py         # US4: debug timeline sequence-ordered + span pairing (SC-007)
│   └── test_inspect_us5.py         # US5: replay in recorded order + start/complete markers (SC-009)
└── contract/
    └── test_inspect_boundary.py    # import-boundary + no-run/no-reemit audit + determinism (SC-002/005)
```

**Structure Decision**: one new sub-package `loopplane.inspect`, mirroring the Phase-1..9
one-package-per-boundary convention so the layer is a single, clearly-bounded, independently revertible
addition. It depends inward on the public Phase-3 Loop Event/State and Phase-1 Runtime Event value types
only. No Phase-1/2/3 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| IA — Foundational + loop diagnostics (US1) | `base.py` (`SequencedEvent`, `count_by_type`), `diagnostics.py` (`LoopDiagnostics`, `loop_diagnostics`) + package skeleton + `__init__` + scripted helpers — **blocks all stories** | `test_inspect_core.py` + `test_inspect_us1.py` green (SC-001/002/008) | Revert package; nothing depends on it |
| IB — Run diagnostics (US2) | `diagnostics.py` (`RunDiagnostics`, `run_diagnostics`) | `test_inspect_us2.py` green; metadata-only, unknown-type skipped (SC-003/004) | Revert IB |
| IC — Trace data model (US3) | `trace.py` (`TraceSpan`, `Trace`, `build_trace`) | `test_inspect_us3.py` green; nested, metadata-only (SC-003) | Revert IC |
| ID — Debug timeline (US4) | `timeline.py` (`TimelineEntry`, `Timeline`, `build_timeline`) | `test_inspect_us4.py` green; sequence-ordered + span pairing (SC-007) | Revert ID |
| IE — Event replay (US5) | `replay.py` (`replay` + start/complete markers) | `test_inspect_us5.py` green; recorded order, no run driven (SC-009) | Revert IE |
| IF — Example, docs, boundary | `examples/inspect_quickstart.py`, `docs/observability-debug.md`, `test_inspect_boundary.py` + public-safety `PHASE10_TARGETS` | boundary + no-run + determinism green; example runs; scan clean (SC-002/005/006) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Leaking conversation content / tool arguments (metadata breach) | The layer reads only declared metadata fields (`type`, `sequence`, ids, the termination reason) and never a content-bearing payload value; a metadata-only test asserts no content/argument is surfaced (FR-001, FR-060, NFR-002, SC-003) |
| Driving a run or re-emitting the live bus (Constitution VI breach) | The layer holds no run/bus path; a contract test asserts no `run_loop`/host import and no live-bus emission; the import audit forbids those surfaces (FR-002, FR-061, NFR-006, SC-005) |
| Non-deterministic ordering (wall-clock) | All ordering is by the events' monotonic `sequence`, never wall-clock; a determinism test runs each transform twice over a stream (NFR-001, SC-002/007) |
| A crash on an empty / malformed / unknown-type / unpaired stream | Every transform tolerates these: empty ⇒ empty result, unknown type ⇒ skipped, unpaired start ⇒ open span recorded; fail-safe tests assert no crash (FR-011, FR-021, FR-041, FR-062, NFR-005, SC-004) |
| Re-implementing state reconstruction | Loop diagnostics reuse the Phase-3 `reconstruct_state`; a test asserts the latest-state fields match it (FR-010, FR-062, SC-008) |
| Reaching a runtime control internal | Import-boundary audit: `loopplane.inspect` imports only `engineering` / `events` + stdlib; references no `run_loop` / `LoopController` / host / gateway token (FR-061, NFR-003) |
| Scope creep into a live UI / remote export | Out-of-scope list + reserved extension points (FR-090–FR-094); Constitution III gate; only deterministic, offline, value-only transforms ship |

**Rollback posture**: `loopplane.inspect` is purely **additive** over Phases 1 & 3 — small, task-scoped
commits, each phase (IA–IF) independently revertible. The layer owns no state and drives nothing, so
reverting any or all leaves the runtime, loop, and every sibling untouched.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.inspect` written fresh; composes the public event/state surfaces; no legacy code copied (FR-062) |
| III | Agent Harness Before Loop Automation | PASS | A deterministic, offline inspection layer over recorded streams; ships **no** live UI/remote export and names every reserved extension point (FR-090–FR-094) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (transform recorded streams into inspection value structures); depends inward on public event/state types; no run/bus logic (FR-002, FR-061) |
| V | Tool Gateway Ownership | PASS | The layer resolves/authorizes/executes no tools; it only reads recorded tool-call **metadata** (counts), never invoking |
| VI | Runtime Event Bus Ownership | PASS | **Central**: the layer is a trace/observability **consumer** of recorded normalized events; it never formats frontend events on the bus, never re-emits or wraps the live buses, and treats event schemas as read-only contracts (FR-002, FR-061) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; produced artifacts are metadata-only; scan extended with PHASE10 targets (NFR-002, SC-006) |
| VIII | No SDK Replacement | PASS | No tracing/observability framework introduced; pure stdlib transforms over LoopPlane's own event surfaces |
| IX | Reference, Not Clone | PASS | Trace/timeline/diagnostics concepts re-derived public-safe from the spec and the public surfaces; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (IA–IF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; determinism + metadata-only + read-only first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and no
Phase-1/2/3 modification. The layer owns no mutable runtime state, drives nothing, and reads only metadata.
Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
