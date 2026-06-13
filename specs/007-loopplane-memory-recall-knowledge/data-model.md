# Data Model: Memory Recall & Knowledge Layer (Phase-7)

All types are public-safe value types or narrow protocols. The layer owns **no** mutable runtime state; the
only stateful object is the in-process `InMemoryKnowledgeIndex` reference double, which is host-owned. Types
mirror the existing Phase-1/3 style: frozen dataclasses + `Protocol`, `from __future__ import annotations`,
`TYPE_CHECKING` imports to keep the boundary tight.

## 1. Recalled Context Entry (FR-001)

```python
@dataclass(frozen=True)
class RecalledEntry:
    text: str                      # the recalled context body (public-safe)
    origin: str                    # producing source: "conversation" | "artifact" | "memory" | "knowledge"
    identifier: str | None = None  # stable id for de-duplication/ordering; None ⇒ never de-duplicated
```

- Carries no secrets or domain data of its own; content comes from the host's stores/index or public state.
- `identifier` is used by the injection policy to de-duplicate across sources (FR-051). `None` means the
  entry is always kept (no stable identity to collapse on).

## 2. Recall Source (FR-002, FR-062)

```python
RecallSource = Callable[[LoopState], tuple[RecalledEntry, ...]]
```

- A pure callable: given the **public** `LoopState`, return an ordered, bounded tuple of entries.
- Stores / readers / indexes are **bound at construction** by the factories below, so every source has the
  same `(LoopState) -> entries` shape and the injection policy can call them uniformly.
- MUST NOT mutate the `LoopState` or any bound store (NFR-006). MUST be deterministic (NFR-001).

A query helper (used by memory/knowledge recall):

```python
QueryFn = Callable[[LoopState], str]

def default_query(state: LoopState) -> str:
    # Deterministic, public-safe: the loop id plus the latest validation reason if present.
    ...
```

## 3. Conversation Recall (US1, FR-010–FR-013)

```python
def conversation_recall(*, limit: int = 10) -> RecallSource: ...
```

- Reads `LoopState.run_refs`, emits one entry per prior run **most-recent-first**
  (`origin="conversation"`, `identifier=session_id`), `text` summarizing
  `session_id` + `termination_reason`. Bounded by `limit`.
- Empty `run_refs` ⇒ empty result (FR-013). No external store; pure state read.

## 4. Artifact Recall (US2, FR-020–FR-022)

```python
class ArtifactReader(Protocol):
    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None: ...

def artifact_recall(reader: ArtifactReader, *, limit: int = 10) -> RecallSource: ...
```

- Iterates `LoopState.artifacts` (`ArtifactRef`), fetches `ArtifactMeta` via `reader.metadata(...)`, orders
  **newest-first** by `ArtifactMeta.created_at`, emits a public-safe summary
  (`origin="artifact"`, `identifier=reference`, `text` = reference + size + media kind + created-at).
- An `ArtifactRef` whose metadata is `None` is **skipped** by the documented rule (FR-022); a `reader` that
  raises contributes nothing (fail-safe, NFR-005). Never surfaces content or a filesystem path (FR-021).
- `ArtifactMeta` is the public Phase-1 type (`loopplane.artifacts`); the host's `ArtifactStore` structurally
  satisfies `ArtifactReader`, as does a scripted double.

## 5. Memory-Entry Recall (US3, FR-030–FR-032)

```python
def memory_entry_recall(
    entries: Sequence[MemoryEntry], *, query: QueryFn = default_query, limit: int = 5
) -> RecallSource: ...
```

- Binds a `Sequence[MemoryEntry]` (the host passes `store.list_entries()` or a scripted list). On call,
  derives a query from the `LoopState` via `query`, calls the **existing** Phase-1
  `select_entries(entries, query, limit=limit)`, and adapts each selected entry into a `RecalledEntry`
  (`origin="memory"`, `identifier=entry.name`, `text` from name/description/body).
- Re-implements no ranking — selection authority stays in Phase-1 (FR-031). Deterministic via
  `select_entries` (FR-032).

## 6. Knowledge Index (US5, FR-040–FR-043)

```python
@dataclass(frozen=True)
class KnowledgeEntry:
    identifier: str
    text: str

class KnowledgeIndex(Protocol):
    def lookup(self, query: str, *, limit: int) -> Sequence[KnowledgeEntry]: ...

class InMemoryKnowledgeIndex:                       # public-safe reference double
    def __init__(self, entries: Sequence[KnowledgeEntry] = ()) -> None: ...
    def lookup(self, query: str, *, limit: int) -> Sequence[KnowledgeEntry]: ...   # deterministic match

def knowledge_recall(
    index: KnowledgeIndex, *, query: QueryFn = default_query, limit: int = 5
) -> RecallSource: ...
```

- `InMemoryKnowledgeIndex` is empty by default and carries no domain data; `lookup` is a deterministic
  token/substring match over its seeded entries (stable order, bounded by `limit`).
- `knowledge_recall` derives the query deterministically from the `LoopState` (FR-042), looks it up, and
  adapts results into entries (`origin="knowledge"`, `identifier=KnowledgeEntry.identifier`). An index that
  raises ⇒ empty recall + diagnostic (NFR-005).
- No external/remote/embedding index ships (FR-043; reserved FR-090/FR-091/FR-093).

## 7. Retrieval Budget (US4, FR-052, FR-053)

```python
@dataclass(frozen=True)
class RetrievalBudget:
    max_entries: int | None = None   # cap on number of entries
    max_chars: int | None = None     # cap on total characters of entry text

@dataclass(frozen=True)
class BudgetResult:
    kept: tuple[RecalledEntry, ...]
    dropped: int                     # how many entries were truncated (explicit, never silent)

def apply_budget(entries: Sequence[RecalledEntry], budget: RetrievalBudget) -> BudgetResult: ...
```

- Keeps entries **in order** until a bound would be exceeded, then stops; the remaining are dropped and
  counted. Character counting is over `RecalledEntry.text` (deterministic, model-agnostic).
- A `None` bound is unbounded on that axis. With both `None`, all entries are kept (`dropped=0`).
- Truncation is order-stable and explicit (FR-053, SC-009); never a silent drop.

## 8. Memory Injection Policy (US4, FR-050–FR-055)

```python
@dataclass(frozen=True)
class RecallAssembly:
    preamble: str                    # the bounded recalled context block ("" when nothing recalled)
    entries: tuple[RecalledEntry, ...]
    dropped: int                     # surfaced budget truncation count (FR-053)
    skipped: tuple[str, ...]         # diagnostics: labels of sources that raised / items skipped

def assemble_recall(
    sources: Sequence[RecallSource], budget: RetrievalBudget, *, state: LoopState
) -> RecallAssembly: ...

def build_recall_input(
    base: InputSource,
    sources: Sequence[RecallSource],
    budget: RetrievalBudget,
    *,
    state: LoopState,
) -> InputSource: ...
```

**`assemble_recall` flow** (pure, deterministic):

1. For each source in order, call `source(state)`; a source that raises contributes nothing and its label is
   recorded in `skipped` (fail-safe, NFR-005).
2. Concatenate entries in **source order, then within-source order** (FR-051 precedence).
3. De-duplicate by `identifier`, keeping the **first** (highest-precedence) occurrence; `identifier=None`
   entries are always kept.
4. `apply_budget(...)` ⇒ `kept` + `dropped`.
5. Format `kept` into a bounded text `preamble` (a labeled context block); empty `kept` ⇒ `preamble=""`.

**`build_recall_input`** returns an `InputSource` whose `initial()`:

- computes `assemble_recall(sources, budget, state=state)`;
- if `base.initial()` is a `str`: returns `preamble + "\n\n" + base` when `preamble` is non-empty, else the
  base string unchanged (FR-055);
- if `base.initial()` is a `Sequence[ContentBlock]`: returns it **unchanged** (recall augments string
  prompts this phase; documented — keeps the layer free of `loopplane.model`).
- never mutates `base`, the `state`, or any store (NFR-006).

## Relationships

```text
LoopState ──read──► RecallSource (conversation | artifact | memory | knowledge)
                          │ produces
                          ▼
                    RecalledEntry[]
                          │ assemble_recall: source-order concat → dedupe(identifier) → apply_budget
                          ▼
                    RecallAssembly (preamble + entries + dropped + skipped)
                          │ build_recall_input wraps a base InputSource
                          ▼
        InputSource.initial() = preamble + base.initial()   ──► consumed by Phase-3 run_loop
```

## Validation & invariants

- **Determinism (NFR-001)**: every source and `assemble_recall` are pure functions of `(state, bound
  stores)`; no I/O, clock, or randomness.
- **Bounded (NFR-007)**: the injected preamble never exceeds `RetrievalBudget`.
- **Public-safe (NFR-002)**: entries carry references/metadata/text only — no content bytes, no paths, no
  secrets.
- **Non-mutation (NFR-006)**: all reads; stores and `LoopState` are unchanged after recall.
- **Fail-safe (NFR-005)**: a raising/empty source or missing item ⇒ empty/skipped + diagnostic, never a
  crash; input assembly always returns a valid `Prompt`.
