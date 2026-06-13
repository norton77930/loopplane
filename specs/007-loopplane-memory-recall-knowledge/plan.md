# Implementation Plan: Memory Recall & Knowledge Layer

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-loopplane-memory-recall-knowledge/spec.md`

## Summary

Build the **Memory Recall & Knowledge** layer (Phase-7) that lets a host begin each Agent Run of a loop
with **relevant recalled context** assembled deterministically and injected through the loop's existing
input contract. The layer ships three **recall sources** — **conversation recall** (the loop's prior-run
trail from the public `LoopState.run_refs`), **artifact recall** (the artifacts the loop produced, via the
public Artifact Storage metadata), and **memory-entry recall** (durable entries selected through the
existing Phase-1 `select_entries`) — plus a named **Knowledge Index** contract with an in-memory reference,
a **Memory Injection Policy** that composes sources, de-duplicates and orders them, applies a
**Retrieval Budget**, and produces a Phase-3 `InputSource` that prepends a bounded recalled preamble to a
base input. The deliverable is one new additive sub-package, `loopplane.recall`, plus a public-safe
example, a doc, and unit/integration/contract suites. It composes **only** the public Phase-1 (`memory`,
`artifacts`) and Phase-3 (`engineering`) surfaces; it never reaches Phase-1 runtime internals or the
Phase-2 host, never mutates a store or the Loop State, and never starts or drives a Loop Run. Design detail
lives in [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts), and
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–6).

**Primary Dependencies**: the public Phase-3 `loopplane.engineering` surface (`LoopState`, `RunReference`,
`ArtifactRef`, `InputSource`, `Prompt`, `StaticInput`) and the public Phase-1 surfaces `loopplane.memory`
(`MemoryEntry`, `select_entries`) and `loopplane.artifacts` (`ArtifactMeta`), plus the stdlib. **No new
third-party dependency.**

**Storage**: None. The layer owns no store. Stores and indexes are **host-supplied**; recall reads them
through narrow read protocols and never writes (FR-070, NFR-006).

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted Loop State + scripted in-memory stores/indexes are the deterministic
instruments (NFR-001, SC-002) — no filesystem dependency, no credentials, no network.

**Target Platform**: Cross-platform library embedded in a host process; a pure-composition layer with no
host, transport, or UI dependency.

**Project Type**: Single library — one new sub-package (`loopplane.recall`) added to the existing
src-layout package, keeping the one-package-per-component-boundary convention from Phases 1–6.

**Performance Goals**: Negligible — recall is O(entries) plus the host store's own lookup; the budget caps
the injected size. Determinism preserved (NFR-001).

**Constraints**: `InputSource`-only integration (FR-054, FR-060); public-surface-only reads (FR-061);
loop-aware scoping (FR-062); determinism (NFR-001, SC-002); fail-safe on every failure mode (NFR-005,
SC-005); non-mutation (NFR-006); bounded injection (NFR-007, SC-004); public-safe (NFR-002, SC-006/007).

**Scale/Scope**: One new package (~8 modules), one example, one doc, unit/integration/contract suites.
**No Phase-1/2/3 source is modified.**

## Dependency on Phases 1 & 3

This phase is **strictly additive** and consumes only public value types and one function from earlier
phases — it composes them and re-derives none of them (NFR-003, FR-070):

- **Phase-3 (`loopplane.engineering`)**: `LoopState` / `RunReference` / `ArtifactRef` (the public scope it
  reads), and `InputSource` / `Prompt` / `StaticInput` (the integration seam it produces).
- **Phase-1 (`loopplane.memory`)**: `MemoryEntry` and the deterministic `select_entries` (memory-entry
  recall reuses selection rather than re-implementing ranking — FR-031).
- **Phase-1 (`loopplane.artifacts`)**: `ArtifactMeta` (the public-safe metadata artifact recall surfaces —
  FR-020/FR-021).

The concrete stores (`MemoryStore`, `ArtifactStore`) and the host are **not** imported: recall depends on
narrow read protocols the host satisfies (a `Sequence[MemoryEntry]`, an `ArtifactReader`, a
`KnowledgeIndex`), so tests use scripted in-memory doubles and no filesystem.

**Non-duplication guarantee (FR-070, SC-008)**: the layer contains *no* storage, selection, looping,
scheduling, host, or runtime logic. It adds only loop-aware recall sources and an injection policy above
the public surfaces.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.recall` depends on `loopplane.engineering`,
`loopplane.memory`, and `loopplane.artifacts`; the loop, scheduler, packs, review, host, and runtime core
have **zero** knowledge of the recall layer.

```text
platform developer
     │ configures recall sources + a budget over host-supplied stores/index
     ▼
loopplane.recall.build_recall_input(base_input, sources, budget, *, state)
     │ produces a Phase-3 InputSource
     ▼
LoopDefinition(input_source=<recall input>)   ◄── Phase-3 (the loop calls initial() to get the prompt)
     │ initial(): run sources(state, stores) → dedupe/order → apply budget → preamble + base.initial()
     ▼
recalled context (bounded, deterministic) prepended to the loop's first prompt
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/injection-boundary.md](./contracts/injection-boundary.md)):

- The layer integrates **only** by producing an `InputSource`; it never calls the Phase-3 loop entry point
  and never starts, drives, or observes a Loop Run (FR-060).
- It reads **only** the public `LoopState` (and host-supplied stores/index through narrow read protocols)
  and **never mutates** any of them (FR-061, NFR-006).
- It imports only `loopplane.engineering`, `loopplane.memory`, `loopplane.artifacts` (value types +
  `select_entries`) and stdlib; it does **not** import `loopplane.host`, `loopplane.model`,
  `loopplane.controller`, any runtime internal, or a sibling layer (FR-061, NFR-003).

## Project Structure

### Documentation (this feature)

```text
specs/007-loopplane-memory-recall-knowledge/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── recall.md             # RecalledEntry, RecallSource, the 3 sources, KnowledgeIndex, RetrievalBudget
│   └── injection-boundary.md # build_recall_input (InputSource seam), the boundary + import audit
├── checklists/requirements.md
└── tasks.md                  # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/recall/
├── __init__.py        # public exports
├── entry.py           # RecalledEntry + RecallSource protocol (FR-001, FR-002)
├── conversation.py    # conversation_recall — reads LoopState.run_refs, most-recent-first (FR-010-FR-013)
├── artifacts.py       # ArtifactReader protocol + artifact_recall, newest-first metadata (FR-020-FR-022)
├── memory.py          # memory_entry_recall — reuses Phase-1 select_entries (FR-030-FR-032)
├── knowledge.py       # KnowledgeIndex protocol + InMemoryKnowledgeIndex + knowledge_recall (FR-040-FR-043)
├── budget.py          # RetrievalBudget + apply_budget, explicit order-stable truncation (FR-052, FR-053)
└── injection.py       # build_recall_input -> InputSource; compose/dedupe/order/inject (FR-050-FR-055)

examples/
└── recall_quickstart.py  # runnable: recall over a scripted loop state + in-memory stores (public-safe)

docs/
└── memory-recall.md   # public-safe guide: sources -> budget -> injection -> InputSource; knowledge index

tests/
├── unit/
│   └── test_recall_core.py        # RecalledEntry, conversation/memory recall, budget truncation, dedupe
├── integration/
│   ├── test_recall_us1.py         # US1: conversation recall injected into the loop's input (SC-001/002/003)
│   ├── test_recall_us2.py         # US2: artifact recall, newest-first, public-safe metadata (SC-007)
│   ├── test_recall_us3.py         # US3: memory-entry recall via select_entries (SC-002)
│   ├── test_recall_us4.py         # US4: compose + budget + injection, explicit truncation (SC-004/009)
│   └── test_recall_us5.py         # US5: knowledge index lookup + fail-safe index (SC-005)
└── contract/
    └── test_recall_boundary.py    # import-boundary audit + non-mutation + determinism (SC-002/003/008)
```

**Structure Decision**: one new sub-package `loopplane.recall`, mirroring the Phase-1..6
one-package-per-boundary convention so the recall layer is a single, clearly-bounded, independently
revertible addition. It depends inward on the public Phase-1 (`memory`, `artifacts`) and Phase-3
(`engineering`) value types only. No Phase-1/2/3 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| KA — Foundational: entry + budget + injection seam | `entry.py` (`RecalledEntry`, `RecallSource`, `default_query`), `budget.py` (`RetrievalBudget`, `apply_budget`), `injection.py` (`assemble_recall`, `build_recall_input`) + package skeleton + `__init__` — **blocks all stories** | `test_recall_core.py` green | Revert package; nothing depends on it |
| KB — Conversation recall (US1) 🎯 MVP | `conversation.py` (`conversation_recall`) | `test_recall_us1.py` green (SC-001/002/003) | Revert KB |
| KC — Artifact recall (US2) | `artifacts.py` (`ArtifactReader`, `artifact_recall`) | `test_recall_us2.py` green; public-safe metadata only (SC-007) | Revert KC |
| KD — Memory-entry recall (US3) | `memory.py` (`memory_entry_recall` over `select_entries`) | `test_recall_us3.py` green (SC-002) | Revert KD |
| KE — Compose + cross-source de-dup (US4) | `injection.py` de-duplication by identifier + budget composition across sources | `test_recall_us4.py` green; 0 over-budget, explicit truncation (SC-004/009) | Revert KE |
| KF — Knowledge index (US5) | `knowledge.py` (`KnowledgeIndex`, `InMemoryKnowledgeIndex`, `knowledge_recall`) | `test_recall_us5.py` green; fail-safe index (SC-005) | Revert KF |
| KG — Example, docs, boundary | `examples/recall_quickstart.py`, `docs/memory-recall.md`, `test_recall_boundary.py` + public-safety `PHASE7_TARGETS` | boundary + non-mutation + determinism green; example runs; scan clean (SC-003/006/008) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Reaching into the Phase-2 host or Phase-1 runtime internals to resolve content | Recall depends on narrow host-supplied read protocols (`Sequence[MemoryEntry]`, `ArtifactReader`, `KnowledgeIndex`); import-boundary audit asserts `loopplane.recall` imports only `engineering` / `memory` / `artifacts` value types + stdlib and references no `loopplane.host` / `loopplane.model` / runtime-internal symbol (FR-061, NFR-003, SC-008) |
| A store/index raising and crashing input assembly | Every source is fail-safe: a raising store/index or a missing item maps to empty/skipped recall with a diagnostic, never a crash (NFR-005, SC-005) |
| Recalled context growing unbounded into the prompt | The Retrieval Budget is applied before injection; truncation is explicit and order-stable with a surfaced dropped count; a budget test asserts 0 over-budget injections (FR-052, FR-053, NFR-007, SC-004/009) |
| Leaking raw artifact content or a local path | Artifact recall surfaces only the reference + declared metadata (size, kind, timestamps); never content or a path; public-safety scan over committed files + PHASE7 targets (FR-021, NFR-002, SC-006/007) |
| Mutating a store or the Loop State | Sources and injection are read-only and never write; a non-mutation test asserts the store and `LoopState` are unchanged after recall (NFR-006) |
| Non-determinism creeping in | No I/O/network/clock in the layer; conversation/memory ordering is derived from public state and `select_entries`; a determinism test runs recall twice for a byte-identical prompt (NFR-001, SC-002) |
| Cross-loop leakage | Recall is scoped by the public `LoopState` (loop id, run refs, artifacts); a scoping test asserts another loop's content never appears (FR-062, SC-003) |
| Scope creep into embeddings / semantic / remote / RAG | Out-of-scope list + reserved extension points (FR-090–FR-095); Constitution III review gate; only deterministic, offline recall ships |

**Rollback posture**: `loopplane.recall` is purely **additive** over Phases 1 & 3 — small, task-scoped
commits, each phase (KA–KG) independently revertible. The layer owns no state and no storage, so reverting
any or all leaves the loop, scheduler, packs, review, and runtime behavior untouched.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.recall` written fresh; composes public Phase-1/3 surfaces; no legacy code copied (FR-070) |
| III | Agent Harness Before Loop Automation | PASS | A deterministic, offline recall layer over the existing loop input seam; ships **no** embeddings/semantic/remote/RAG and names every reserved extension point (FR-090–FR-095, NFR-007) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (compose loop-aware recalled context into a Phase-3 `InputSource`); depends inward on public Phase-1/3 value types; boundary table assigns ownership; no store/loop/host logic (FR-060, FR-061) |
| V | Tool Gateway Ownership | PASS | The layer resolves/authorizes/executes no tools; it only reads host-supplied stores through narrow read protocols |
| VI | Runtime Event Bus Ownership | PASS | Consumes and emits no Runtime/Loop Events; recall diagnostics are plain return values, never a competing event stream (FR-080) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; recalled entries are public-safe; artifact recall surfaces only references + metadata (FR-021, NFR-002); scan extended with PHASE7 targets (SC-006/007) |
| VIII | No SDK Replacement | PASS | No retrieval/RAG framework introduced; pure stdlib composition over LoopPlane's own public surfaces |
| IX | Reference, Not Clone | PASS | Recall/knowledge concepts re-derived public-safe from the spec and the public surfaces; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (KA–KG) has required tests, a validation gate, and a rollback note; the package is additive and revertible; determinism + fail-safe + non-mutation first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and no
Phase-1/2/3 modification. The layer owns no mutable runtime state; the only stateful object
(`InMemoryKnowledgeIndex`) is a host-owned, in-process reference double. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
