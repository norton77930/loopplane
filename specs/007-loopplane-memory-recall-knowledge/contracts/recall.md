# Contract: Recall Sources, Knowledge Index, Retrieval Budget

The public surface of `loopplane.recall` for producing recalled context. All types are public-safe and
deterministic. Behaviour is normative; signatures are illustrative Python.

## Recalled Context Entry & Recall Source (FR-001, FR-002)

```python
@dataclass(frozen=True)
class RecalledEntry:
    text: str
    origin: str                    # "conversation" | "artifact" | "memory" | "knowledge"
    identifier: str | None = None

RecallSource = Callable[[LoopState], tuple[RecalledEntry, ...]]
QueryFn = Callable[[LoopState], str]

def default_query(state: LoopState) -> str: ...
```

- A `RecallSource` reads only the public `LoopState` (plus stores bound at construction), returns an
  ordered, bounded tuple, mutates nothing, and is deterministic (NFR-001, NFR-006).
- `default_query` derives a deterministic, public-safe query from the loop id and the latest validation
  reason (if any).

## Conversation Recall (FR-010–FR-013)

```python
def conversation_recall(*, limit: int = 10) -> RecallSource: ...
```

- Emits one entry per `LoopState.run_refs` item, **most-recent-first**, `origin="conversation"`,
  `identifier=session_id`, `text` from `session_id` + `termination_reason`, bounded by `limit`.
- Empty `run_refs` ⇒ `()` (FR-013). Loop-scoped: only this Loop State's runs (FR-011).

## Artifact Recall (FR-020–FR-022)

```python
class ArtifactReader(Protocol):
    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None: ...

def artifact_recall(reader: ArtifactReader, *, limit: int = 10) -> RecallSource: ...
```

- For each `LoopState.artifacts` (`ArtifactRef`), fetch `reader.metadata(session_id, reference)`; order
  **newest-first** by `ArtifactMeta.created_at`; emit `origin="artifact"`, `identifier=reference`, `text` =
  a public-safe summary (reference, size, media kind, created-at). Bounded by `limit`.
- `metadata(...) is None` ⇒ skip that ref (documented rule, FR-022). A raising `reader` ⇒ that source
  contributes nothing (NFR-005). Never surfaces content or a filesystem path (FR-021, SC-007).

## Memory-Entry Recall (FR-030–FR-032)

```python
def memory_entry_recall(
    entries: Sequence[MemoryEntry], *, query: QueryFn = default_query, limit: int = 5
) -> RecallSource: ...
```

- Calls the existing Phase-1 `select_entries(entries, query(state), limit=limit)` and adapts each result
  into `origin="memory"`, `identifier=entry.name`, `text` from the entry. Re-implements no ranking
  (FR-031). Deterministic via `select_entries` (FR-032).

## Knowledge Index (FR-040–FR-043)

```python
@dataclass(frozen=True)
class KnowledgeEntry:
    identifier: str
    text: str

class KnowledgeIndex(Protocol):
    def lookup(self, query: str, *, limit: int) -> Sequence[KnowledgeEntry]: ...

class InMemoryKnowledgeIndex:
    def __init__(self, entries: Sequence[KnowledgeEntry] = ()) -> None: ...
    def lookup(self, query: str, *, limit: int) -> Sequence[KnowledgeEntry]: ...

def knowledge_recall(
    index: KnowledgeIndex, *, query: QueryFn = default_query, limit: int = 5
) -> RecallSource: ...
```

- `InMemoryKnowledgeIndex.lookup` is a deterministic token/substring match over its seeded (public-safe,
  empty-by-default) entries, stable order, bounded by `limit`.
- `knowledge_recall` derives the query deterministically from the `LoopState` (FR-042); a raising index ⇒
  empty recall + diagnostic (NFR-005). No external/remote/embedding index ships (FR-043).

## Retrieval Budget (FR-052, FR-053)

```python
@dataclass(frozen=True)
class RetrievalBudget:
    max_entries: int | None = None
    max_chars: int | None = None

@dataclass(frozen=True)
class BudgetResult:
    kept: tuple[RecalledEntry, ...]
    dropped: int

def apply_budget(entries: Sequence[RecalledEntry], budget: RetrievalBudget) -> BudgetResult: ...
```

- Keeps entries in order until a bound would be exceeded; the rest are dropped and counted. Character
  counting is over `RecalledEntry.text`. A `None` bound is unbounded on that axis. Truncation is explicit
  and order-stable (SC-009); never silent.

## Determinism & fail-safe (NFR-001, NFR-005)

- Same `LoopState` + same bound store/index snapshot ⇒ identical entries in identical order, every run.
- Every failure mode (empty source, raising store/index, missing item, over-budget) ⇒ an explicit,
  public-safe result (empty/skipped/truncated + diagnostic) — never a crash, hang, or fabricated content.
