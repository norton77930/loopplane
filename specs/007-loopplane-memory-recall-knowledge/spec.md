# Feature Specification: LoopPlane Memory Recall & Knowledge Layer

**Feature Branch**: `main` (main-only autopilot)

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Define the LoopPlane Memory Recall & Knowledge layer (unit 007) on top of the completed Phase-1 runtime foundation and the Phase-3 Loop Engineering Layer, composing ONLY their public contracts: deterministic, public-safe loop-aware context sources (conversation recall, artifact recall, memory-entry recall), a named knowledge-index contract with an in-memory reference implementation, a memory injection policy with a retrieval budget, and loop-aware scoping — never bypassing the loop layer, never reaching Phase-1/Phase-2 internals, never driving runs."

## Overview

The Memory Recall & Knowledge layer (Phase-7) lets a host begin each Agent Run of a
loop with **relevant recalled context** — the loop's own prior conversation/memory,
the artifacts it produced, durable memory entries, and host knowledge — assembled
deterministically and injected through the loop's existing input contract.

It is a **composition layer**: it reuses the Phase-1 public Memory and Artifact
Storage contracts for content and the Phase-3 public Loop State and Input Source
contracts for loop-aware integration. It never re-implements storage, selection, or
looping; it never reaches into Phase-1 runtime internals or the Phase-2 host; and it
never starts, drives, or observes a Loop Run. Recall is deterministic, bounded, and
fail-safe by construction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Begin each run with the loop's prior conversation (Priority: P1)

A host runs a multi-iteration loop and wants every Agent Run after the first to begin
already aware of what the loop established earlier. The host plugs a **Conversation
Recall** source into the Loop Definition's input. On each iteration the loop's input
is prefixed with a bounded, most-recent-first block of the loop's prior
conversation/memory content, scoped to that loop only.

**Why this priority**: Loop-aware recall is the core value of the layer — without it,
each iteration restarts cold. This is the minimum slice that delivers user value and
exercises the full recall-source → injection → Prompt path.

**Independent Test**: With a scripted Loop State carrying prior runs and a scripted
memory store, build a loop whose input source is the conversation-recall injection;
assert the produced Prompt contains the recalled block (most-recent-first, bounded)
and that a loop with no prior runs produces the base input unchanged.

**Acceptance Scenarios**:

1. **Given** a loop with prior-run memory content and a Conversation Recall source,
   **When** the loop's input is assembled, **Then** the Prompt contains the recalled
   content ordered most-recent-first within the configured budget.
2. **Given** the same Loop State and the same store snapshot, **When** input assembly
   runs twice, **Then** the produced Prompt is byte-identical both times.
3. **Given** a loop with no prior runs (empty store), **When** input is assembled,
   **Then** the base input is returned unchanged with no recalled block.

---

### User Story 2 - Recall the artifacts the loop produced (Priority: P2)

A host wants later iterations to reference the artifacts earlier iterations produced
(e.g., a draft the loop wrote). The host plugs an **Artifact Recall** source that
surfaces public-safe references and metadata of the loop's artifacts, newest-first,
fetching only through the public Artifact Storage contract.

**Why this priority**: Artifacts are a primary loop output; recalling them closes the
produce-then-reuse cycle. Independent of conversation recall.

**Independent Test**: With a Loop State listing artifact references and a scripted
artifact store, assert the recalled entries are newest-first public-safe summaries
(reference + declared metadata), that a reference with no retrievable content is
skipped explicitly, and that no raw private content or absolute local path appears.

**Acceptance Scenarios**:

1. **Given** a loop that produced artifacts, **When** Artifact Recall runs, **Then** it
   returns newest-first entries each carrying a public-safe reference and metadata.
2. **Given** an artifact reference whose content is not retrievable, **When** Artifact
   Recall runs, **Then** that reference is skipped by the documented rule and no error
   is raised.
3. **Given** any artifact, **When** it is recalled, **Then** the entry contains no raw
   private file content and no absolute local filesystem path.

---

### User Story 3 - Recall durable memory entries via the existing selection (Priority: P2)

A host maintains durable memory entries and wants the loop to recall the relevant ones
as context. The host plugs a **Memory-Entry Recall** source that selects entries
through the existing Phase-1 deterministic selection and adapts the result into
recalled context — without re-implementing ranking.

**Why this priority**: Reuses an existing Phase-1 capability to feed the loop; keeps
selection authority in Phase-1 (non-duplication).

**Independent Test**: With a scripted memory store and selection inputs, assert the
recalled entries match the Phase-1 selection result (same items, same order) adapted
into recalled context, and that recall adds no ranking of its own.

**Acceptance Scenarios**:

1. **Given** durable memory entries and selection inputs, **When** Memory-Entry Recall
   runs, **Then** the recalled entries correspond exactly to the Phase-1 selection
   result, in the same order.
2. **Given** identical inputs, **When** recall runs twice, **Then** the result is
   identical.

---

### User Story 4 - Compose sources and inject within a retrieval budget (Priority: P2)

A host wants to combine several recall sources into one bounded context block. The host
configures a **Memory Injection Policy** that composes the sources, orders and
de-duplicates their entries by a documented precedence, applies a **Retrieval Budget**,
and injects the result into the loop's input as a bounded preamble — never mutating the
underlying stores or the base input.

**Why this priority**: Real use combines sources and must stay bounded; the budget is
what makes recalled context safe to inject every iteration.

**Independent Test**: With two recall sources that produce overlapping entries and a
budget smaller than their union, assert the injected block is ordered and de-duplicated
by the documented precedence, never exceeds the budget, and reports the truncated count.

**Acceptance Scenarios**:

1. **Given** multiple recall sources with overlapping entries, **When** the policy
   composes them, **Then** duplicates are removed by stable identifier keeping the
   highest-precedence occurrence and the order follows the documented precedence.
2. **Given** recalled context larger than the budget, **When** the policy injects it,
   **Then** the injected block is within the budget, truncation is order-stable, and the
   dropped count is surfaced.
3. **Given** an empty recalled set, **When** the policy runs, **Then** the base input is
   returned unchanged and nothing is injected.

---

### User Story 5 - A named knowledge-index contract with a public-safe reference (Priority: P3)

A host wants to supply an out-of-band knowledge source keyed off the loop. The layer
defines a **Knowledge Index** contract — a deterministic lookup from a query derived
from the public Loop State to a bounded set of knowledge entries — and ships an
in-memory, public-safe **reference index** for examples and tests. No external, remote,
embedding, or semantic index is built.

**Why this priority**: Establishes the extension seam for host knowledge while keeping
this phase deterministic and offline; lowest priority because the recall sources deliver
value without it.

**Independent Test**: With the reference index seeded with public-safe entries and a
scripted Loop State, assert the query is derived deterministically from the Loop State,
the lookup returns the seeded entries within the bound, and an empty/missing index
yields empty recall.

**Acceptance Scenarios**:

1. **Given** a reference Knowledge Index seeded with entries and a Loop State, **When**
   knowledge recall runs, **Then** it returns the matching entries deterministically
   within the configured bound.
2. **Given** an index that raises on lookup, **When** knowledge recall runs, **Then** it
   returns empty recall with a diagnostic and never crashes.

---

### Edge Cases

- **No prior runs / empty store / empty index** → empty recall; base input unchanged.
- **A store, artifact fetch, or index raises** → empty (or skipped) recall with an
  explicit public-safe diagnostic; never a crash, hang, or fabricated content.
- **Recalled context exceeds the budget** → explicit, order-stable truncation with a
  surfaced dropped count; never a silent drop.
- **Duplicate entries across sources** → de-duplicated by stable identifier under the
  documented precedence.
- **Artifact reference without retrievable content** → skipped by the documented rule.
- **Recall requested for a loop with unrelated content present in the store** → only the
  current loop's content is recalled (loop-scoped).
- **Iterating an unknown future recalled-entry origin** → consumers tolerate it (the
  entry's text and origin are forward-compatible).

## Requirements *(mandatory)*

### Foundational contract

- **FR-001**: The layer MUST define a **Recalled Context Entry** — a public-safe unit of
  recalled context carrying a text body, an origin label (which source produced it), and
  an optional stable identifier used for ordering and de-duplication. It MUST carry no
  secrets or domain data of its own.
- **FR-002**: The layer MUST define a **Recall Source** contract: a pure callable that,
  given the public Loop State and a configured store or index, returns an ordered,
  bounded sequence of Recalled Context Entries. A Recall Source MUST read only public
  surfaces and MUST NOT mutate any store, index, or the Loop State.
- **FR-003**: The layer MUST hardcode no domain knowledge: every entry's content
  originates from a host-supplied store, a host-supplied index, or the public Loop State.

### Conversation recall (US1)

- **FR-010**: The layer MUST provide a **Conversation Recall** source that recalls the
  loop's prior conversation/memory content scoped to the current loop, ordered
  most-recent-first.
- **FR-011**: Conversation Recall MUST derive its scope from the public Loop State
  (loop id and run references) and MUST NOT include content from unrelated loops.
- **FR-012**: Conversation Recall MUST be deterministic: the same Loop State and the same
  store snapshot yield identical entries in identical order.
- **FR-013**: With no prior runs or an empty store, Conversation Recall MUST return an
  empty result and MUST NOT fabricate content.

### Artifact recall (US2)

- **FR-020**: The layer MUST provide an **Artifact Recall** source that recalls the
  references and metadata of artifacts the loop produced, ordered newest-first, reading
  artifact references from the public Loop State and fetching metadata only through the
  public Artifact Storage contract.
- **FR-021**: Artifact Recall MUST surface only a public-safe summary (a reference key
  and declared metadata); it MUST NOT surface raw private artifact content or an absolute
  local filesystem path.
- **FR-022**: Artifact Recall MUST be deterministic and loop-scoped; an artifact
  reference whose content/metadata is not retrievable MUST be skipped by a documented
  rule, never raising.

### Memory-entry recall (US3)

- **FR-030**: The layer MUST provide a **Memory-Entry Recall** source that selects
  durable memory entries through the existing Phase-1 deterministic selection and adapts
  the selected entries into Recalled Context Entries.
- **FR-031**: Memory-Entry Recall MUST NOT re-implement selection or ranking; it MUST
  reuse the Phase-1 selection contract and only adapt its result.
- **FR-032**: Memory-Entry Recall MUST be deterministic given the same entries and
  selection inputs.

### Knowledge index (US5)

- **FR-040**: The layer MUST define a **Knowledge Index** contract: a host-implemented,
  deterministic lookup from a query or key derived from the public Loop State to a
  bounded set of knowledge entries.
- **FR-041**: The layer MUST provide an in-memory, public-safe **reference Knowledge
  Index** for examples and tests; it MUST carry no domain data by default and MUST be
  deterministic.
- **FR-042**: The Knowledge Index query MUST be derived deterministically from the public
  Loop State; the layer MUST NOT derive queries from non-deterministic sources.
- **FR-043**: The layer MUST ship no external, remote, persistent, embedding, or semantic
  index; those are reserved extension points (FR-090–FR-095).

### Memory injection policy & retrieval budget (US4)

- **FR-050**: The layer MUST provide a **Memory Injection Policy** that composes one or
  more recall sources into a single loop-input contribution.
- **FR-051**: The policy MUST order and de-duplicate entries across sources by a
  **documented precedence** (source order, then within-source order; duplicates removed
  by stable identifier, keeping the highest-precedence occurrence).
- **FR-052**: The layer MUST define a **Retrieval Budget**: an explicit, deterministic
  bound (a maximum number of entries and/or a maximum number of characters) applied
  before injection.
- **FR-053**: When recalled context exceeds the budget, truncation MUST be explicit and
  order-stable under the documented precedence; the policy MUST NOT silently drop entries
  and MUST surface that truncation occurred (e.g., a dropped count).
- **FR-054**: The policy MUST inject the recalled context as a **bounded context
  preamble** composed with the loop's base input through the Phase-3 Input Source / Prompt
  contract, producing the loop's Prompt without mutating the base input or any store.
- **FR-055**: With an empty recalled set, the policy MUST inject nothing and yield the
  loop's base input unchanged (zero behavior change when there is nothing to recall).

### Loop-aware integration & boundary

- **FR-060**: Every source and the policy MUST integrate through the Phase-3 Input
  Source / Prompt contract; the layer MUST NOT start, drive, or observe a Loop Run and
  MUST NOT invoke the Phase-3 loop entry point.
- **FR-061**: The layer MUST read only the **public** Phase-1 Memory and Artifact Storage
  contracts and the **public** Phase-3 Loop State and Input Source contracts. It MUST NOT
  import or reference Phase-1 runtime internals or any Phase-2 host symbol.
- **FR-062**: Recall MUST be **loop-aware** — keyed and scoped by public Loop State
  (loop id, iteration index, run references) and reproducible per iteration.

### Non-duplication & extension points

- **FR-070**: The layer MUST NOT re-implement Phase-1 Memory storage or selection,
  Artifact Storage, or Phase-3 looping; it composes them.
- **FR-090** (reserved, named-not-built): embedding/vector stores and similarity search.
- **FR-091** (reserved): semantic or model-graded ranking and relevance.
- **FR-092** (reserved): LLM-based query rewriting or summarization of recalled context.
- **FR-093** (reserved): external or remote knowledge bases and retrieval services.
- **FR-094** (reserved): RAG pipelines.
- **FR-095** (reserved): a persistent cross-restart recall cache.
  Each reserved point MUST be named in docs and MUST NOT be implemented this phase.

### Diagnostics

- **FR-080**: Recall diagnostics (truncation counts, skipped artifacts, empty results,
  raising-store fall-throughs) MUST be explicit and public-safe; the layer MUST NOT emit
  secrets or private references in any diagnostic.

### Non-Functional Requirements

- **NFR-001 (Determinism)**: Given a scripted Loop State and a scripted store/index,
  every recall source and the injection policy MUST produce identical recalled context
  and an identical injected Prompt on every run.
- **NFR-002 (Public-safety)**: No committed artifact may contain secrets, credentials,
  private paths, private project/repository names, internal names, or internal network
  addresses. Artifact recall surfaces only public-safe references and metadata.
- **NFR-003 (Boundary)**: The layer composes only the public Phase-1 (Memory, Artifact
  Storage) and Phase-3 (Loop State, Input Source) surfaces; it references no Phase-2 host
  symbol and no Phase-1 runtime internal — enforced by an import-boundary audit.
- **NFR-004 (Language & safety)**: All artifacts are English and public-safe.
- **NFR-005 (Fail-safe)**: Every failure mode — a missing/empty store, a raising
  store/index, an unretrievable artifact, an over-budget recalled set — MUST map to an
  explicit, public-safe result (empty recall, a skipped entry, explicit truncation),
  never a crash, a hang, or fabricated context.
- **NFR-006 (Non-mutation)**: Recall and injection MUST NOT mutate any store, Memory,
  Artifact Storage, the Loop State, or the base Input Source.
- **NFR-007 (Boundedness)**: Recalled context injected into a loop is always bounded by
  the Retrieval Budget; unbounded growth MUST be impossible.

### Key Entities

- **Recalled Context Entry**: a public-safe unit of recalled context — text body, origin
  label, optional stable identifier.
- **Recall Source**: a pure callable `(Loop State, store/index) → ordered, bounded
  Recalled Context Entries`.
- **Conversation Recall / Artifact Recall / Memory-Entry Recall**: the three concrete
  recall sources.
- **Knowledge Index**: a host-implemented deterministic lookup, plus an in-memory
  public-safe reference implementation.
- **Memory Injection Policy**: composes recall sources, orders/de-duplicates, applies the
  Retrieval Budget, and injects a bounded preamble into the loop's input.
- **Retrieval Budget**: an explicit deterministic bound (max entries and/or max
  characters).
- **Injected Loop Input / Prompt contribution**: the base input composed with the
  bounded recalled preamble.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A host makes a loop begin each run with its own prior conversation by
  plugging a single recall source into the Loop Definition, with no other changes.
- **SC-002**: Recall is 100% reproducible — re-running the same scripted loop and store
  yields a byte-identical injected Prompt.
- **SC-003**: Recall never crosses loops — content scoped to one loop never appears in
  another loop's recall (0 cross-loop leaks across the test suite).
- **SC-004**: Injected recalled context is always within the configured budget (0
  over-budget injections across the test suite).
- **SC-005**: Every failure mode yields an explicit safe result (0 crashes or hangs; a
  raising store/index yields empty recall plus a diagnostic).
- **SC-006**: No committed artifact contains secrets, private paths, internal names, or
  internal network addresses (public-safety scan green).
- **SC-007**: Artifact recall surfaces only public-safe references and metadata (no raw
  private content, no absolute local filesystem path) in 100% of recalled artifact
  entries.
- **SC-008**: The layer drives no Loop Run and imports no Phase-2 host symbol or Phase-1
  runtime internal (import-boundary audit green).
- **SC-009**: Truncation is always explicit — whenever recall exceeds the budget the
  dropped count is reported (0 silent drops).
- **SC-010**: The reserved extension points (embedding/vector, semantic ranking, LLM
  rewriting, remote/external index, RAG, persistent cache) are absent from the shipped
  surface.

## Assumptions

- The layer composes the existing public Phase-1 Memory contract (memory store, memory
  entry, and the deterministic entry selection) and Artifact Storage contract (artifact
  store and artifact metadata), and the public Phase-3 Loop State and Input Source /
  Prompt contracts. These surfaces exist and are stable (units 001 and 003 are Verified).
- **Conversation recall** recalls the publicly exposed memory/knowledge content
  associated with the loop's prior runs (via the Phase-1 Memory contract and the Loop
  State run references). It does not assume a separate raw-transcript store, which is not
  part of the composed public surface; "conversation" here means the loop's prior recalled
  memory content.
- Stores and indexes are **host-supplied**. The layer ships only public-safe in-memory
  reference implementations (and scripted doubles) for examples and tests; it bundles no
  real knowledge data.
- The **Retrieval Budget** is measured in entries and/or characters (deterministic and
  model-agnostic); token-based budgets are out of scope because they depend on a model
  tokenizer.
- Injection composes the recalled preamble with the loop's existing base Input Source
  (wrapping it), producing the Prompt; it does not replace the base input and does not
  start a run.
- A recall call observes a stable store/index snapshot for its duration (determinism is
  defined relative to that snapshot).

## Out of Scope

- Embeddings, vector databases, and semantic or similarity search.
- ML- or LLM-based ranking, relevance, query rewriting, or summarization.
- External or remote knowledge bases and retrieval services; RAG pipelines.
- Persistent cross-restart recall caches.
- Cloud deployment, web, or UI surfaces.
- Any non-deterministic retrieval or ordering.
- Starting, driving, or observing Loop Runs (owned by Phase-3); storing or selecting
  memory/artifacts (owned by Phase-1).
