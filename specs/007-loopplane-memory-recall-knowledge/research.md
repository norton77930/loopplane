# Research: Memory Recall & Knowledge Layer (Phase-7)

Phase-0 decisions for `loopplane.recall`. Every decision composes the public Phase-1/3 surfaces and
re-derives none of them.

## Inherited context, no re-derivation (NFR-003)

The layer consumes these **public** surfaces verbatim and adds only recall + injection above them:

| Surface | Source (public) | Used by |
|---|---|---|
| `LoopState` (`loop_id`, `iteration_index`, `run_refs`, `artifacts`) | `loopplane.engineering` | the recall scope every source reads |
| `RunReference` (`session_id`, `termination_reason`) | `loopplane.engineering` | conversation recall |
| `ArtifactRef` (`session_id`, `reference`) | `loopplane.engineering` | artifact recall |
| `InputSource` (`initial() -> Prompt`), `StaticInput`, `Prompt` | `loopplane.engineering` | the integration seam the policy produces |
| `MemoryEntry`, `select_entries(entries, prompt, *, limit)` | `loopplane.memory` | memory-entry recall |
| `ArtifactMeta` (`reference`, `session_id`, `size`, `media_kind`, `created_at`, …) | `loopplane.artifacts` | artifact recall (metadata it surfaces) |

The concrete `MemoryStore` / `ArtifactStore` and the Phase-2 host are **not** imported — recall depends on
narrow host-supplied read protocols so tests use scripted in-memory doubles (Decision 8).

## Decision 1 — Integration seam is the Phase-3 `InputSource`

- **Decision**: the layer integrates by producing a Phase-3 `InputSource` whose `initial()` returns the
  base input's prompt with a bounded recalled preamble prepended. A host sets
  `LoopDefinition(input_source=build_recall_input(base, sources, budget, state=...))`.
- **Rationale**: `InputSource.initial()` is the public, sanctioned way to supply a Loop Run's first prompt
  (FR-003 of Phase-3). Producing an `InputSource` keeps the layer to **composition** — it never calls the
  loop entry point or touches the controller (FR-054, FR-060, SC-008).
- **Alternatives rejected**: *Per-iteration injection via the controller's repair augmentation* — that is
  controller-internal and would force a reach-through across the boundary; rejected. *A new Phase-3 hook* —
  would modify Phase-3 source; rejected (additive-only).

## Decision 2 — Conversation recall is the loop's prior-run trail (`LoopState.run_refs`)

- **Decision**: conversation recall reads `LoopState.run_refs` (the ordered Agent Run references the loop
  accumulated) and emits one Recalled Context Entry per prior run, **most-recent-first**, carrying the
  public `session_id` + `termination_reason`. No external store is needed.
- **Rationale**: `run_refs` is the only public, loop-scoped record of "what ran before" (FR-061 of Phase-3
  keeps Loop State reference-only — no transcript bytes). It is deterministic, public-safe, and naturally
  scoped to the loop. At a fresh run's first iteration `run_refs` is empty ⇒ empty recall (FR-013).
- **Alternatives rejected**: *Recalling raw conversation transcripts* — there is no public transcript
  surface across the composed phases (Loop State holds references only); inventing one would exceed scope
  and risk leaking content. *Reading session content via the host* — crosses the Phase-2 boundary.

## Decision 3 — Artifact recall surfaces metadata only (public-safe)

- **Decision**: artifact recall iterates `LoopState.artifacts` (`ArtifactRef`), fetches `ArtifactMeta`
  through a narrow `ArtifactReader` protocol (`metadata(session_id, reference) -> ArtifactMeta | None`),
  orders **newest-first** by `ArtifactMeta.created_at`, and emits a public-safe summary (reference +
  declared metadata). It never fetches or surfaces artifact **content** or a filesystem path.
- **Rationale**: FR-021/SC-007 require public-safe artifact recall; metadata (reference, size, media kind,
  timestamp) is sufficient context and carries no private bytes. A reference whose metadata is missing is
  skipped by a documented rule (FR-022). The host's `ArtifactStore` structurally satisfies `ArtifactReader`;
  a scripted double does too.
- **Alternatives rejected**: *Embedding artifact content in the prompt* — risks leaking private bytes and
  is unbounded; rejected (metadata-only + the budget keep it safe and small).

## Decision 4 — Memory-entry recall reuses Phase-1 `select_entries`

- **Decision**: memory-entry recall takes a `Sequence[MemoryEntry]` (the host passes `store.list_entries()`
  or a scripted list) and a query derived from the public Loop State, calls the existing deterministic
  `select_entries(entries, query, limit=...)`, and adapts each selected entry into a Recalled Context Entry.
- **Rationale**: selection/ranking authority stays in Phase-1 (FR-031, non-duplication). `select_entries` is
  already deterministic (token overlap + stable tie-break), so recall inherits determinism for free.
- **Alternatives rejected**: *Re-implementing relevance in the recall layer* — duplicates Phase-1 and risks
  divergent behavior; rejected.

## Decision 5 — Knowledge Index is a host protocol with an in-memory reference

- **Decision**: define a `KnowledgeIndex` protocol — `lookup(query: str, *, limit: int) -> Sequence[...]`
  — and ship an `InMemoryKnowledgeIndex` reference seeded by the host (empty by default, public-safe). A
  `knowledge_recall` source derives the query deterministically from the Loop State (e.g., `loop_id` plus
  the latest validation reason) and adapts the looked-up entries into Recalled Context Entries.
- **Rationale**: establishes the host-knowledge extension seam while keeping this phase deterministic and
  offline (FR-040–FR-043). The reference index lets examples/tests run with no external service and no
  domain data.
- **Alternatives rejected**: *An embedding/semantic/remote index* — non-deterministic and out of scope
  (reserved FR-090/FR-091/FR-093).

## Decision 6 — Retrieval Budget: max entries and/or max characters, applied before injection

- **Decision**: `RetrievalBudget(max_entries: int | None, max_chars: int | None)`. `apply_budget(entries,
  budget)` keeps entries in order until a bound is reached, then truncates; it returns the kept entries plus
  an explicit **dropped count**. Character counting is on the entry text (deterministic, model-agnostic).
- **Rationale**: FR-052/FR-053/NFR-007/SC-004/SC-009 — recalled context must be bounded and any truncation
  must be explicit and order-stable, never silent. Characters (not tokens) keep it deterministic without a
  model tokenizer.
- **Alternatives rejected**: *Token budgets* — depend on a model tokenizer (non-deterministic across
  models); reserved. *Silent trimming* — violates SC-009.

## Decision 7 — Injection: text preamble over a string base input; non-string passes through

- **Decision**: `build_recall_input(base, sources, budget, *, state)` returns an `InputSource`. At
  `initial()` it runs each source over `(state, store/index)`, concatenates entries, de-duplicates by
  stable identifier (keeping the highest-precedence occurrence), orders by **source order then within-source
  order**, applies the budget, formats a bounded text **preamble**, and returns `preamble + base.initial()`
  when the base prompt is a string. With an empty recalled set it returns `base.initial()` unchanged
  (FR-055). If the base prompt is a `Sequence[ContentBlock]` (not a string), it returns it **unchanged**
  with a diagnostic — recall augments string prompts this phase (documented), keeping the layer free of the
  `loopplane.model` content-block types.
- **Rationale**: string prompts are the dominant, public-safe, deterministic case (`StaticInput` is a
  string). Passing block prompts through untouched is fail-safe (NFR-005) and keeps the import boundary to
  `{engineering, memory, artifacts}` (no `loopplane.model`). De-dup precedence is documented (FR-051).
- **Alternatives rejected**: *Importing `loopplane.model` to prepend a content block* — widens the boundary
  for a non-MVP case; deferred. *Mutating the base `InputSource`* — violates NFR-006; the policy wraps, it
  does not mutate.

## Decision 8 — Narrow host-supplied read protocols (no concrete stores, no filesystem in tests)

- **Decision**: recall depends on the minimum it needs — a `Sequence[MemoryEntry]`, an `ArtifactReader`
  (`metadata(...)`), and a `KnowledgeIndex` (`lookup(...)`). The host wires its real stores; tests pass
  scripted in-memory doubles. The layer imports only the public **value types** (`MemoryEntry`,
  `ArtifactMeta`) and the **function** `select_entries`.
- **Rationale**: keeps recall deterministic and filesystem-free in tests (NFR-001), composes the public
  contracts without importing concrete stores or the host, and lets any host store satisfy the protocols
  structurally (FR-061, NFR-003).
- **Alternatives rejected**: *Depending on `MemoryStore`/`ArtifactStore` directly* — couples to filesystem
  stores and complicates deterministic tests; unnecessary since the value types + protocols suffice.

## Decision 9 — Determinism, fail-safe, and non-mutation are first-class

- **Determinism (NFR-001/SC-002)**: no I/O, network, clock, or randomness in the layer; ordering derives
  from public state and `select_entries`; a determinism test asserts a byte-identical injected prompt across
  two runs over the same state + store snapshot.
- **Fail-safe (NFR-005/SC-005)**: a raising store/index, a missing artifact, or an empty source maps to an
  empty or skipped result with a public-safe diagnostic — never a crash, hang, or fabricated content. The
  injection swallows a source that raises (that source contributes nothing) so input assembly never fails.
- **Non-mutation (NFR-006)**: sources and injection only read; a non-mutation test asserts the store and the
  `LoopState` are unchanged after recall.

## Decision 10 — Diagnostics are plain return values, not an event stream

- **Decision**: recall diagnostics (dropped count, skipped artifacts, raising-source fall-throughs,
  empty results) are carried on the returned result / injection summary, not on the Runtime or Loop Event
  bus.
- **Rationale**: FR-080 + Constitution VI — the layer owns no event stream and must not compete with or
  wrap the existing buses; a plain, public-safe summary is sufficient and keeps the boundary clean.
