# Memory Recall & Knowledge (`loopplane.recall`)

Begin each Agent Run of a loop with **relevant recalled context** — the loop's prior runs,
the artifacts it produced, durable memory entries, and host knowledge — assembled
deterministically and injected through the loop's existing input contract.

The layer is pure composition over the public Phase-1 (`loopplane.memory`,
`loopplane.artifacts`) and Phase-3 (`loopplane.engineering`) surfaces. It reads only the
public Loop State (and host-supplied stores through narrow read protocols), mutates
nothing, and starts no Loop Run.

## The pieces

| Piece | What it does |
|---|---|
| `RecalledEntry` | A public-safe unit of recalled context: `text`, `origin`, optional `identifier`. |
| `RecallSource` | A pure callable `(LoopState) -> tuple[RecalledEntry, ...]`. |
| `conversation_recall(*, limit=10)` | The loop's prior-run trail (`LoopState.run_refs`), most-recent-first. |
| `artifact_recall(reader, *, limit=10)` | Newest-first, public-safe references + metadata of the loop's artifacts (metadata only — never content or a path). |
| `memory_entry_recall(entries, *, query=default_query, limit=5)` | Durable entries selected through the Phase-1 `select_entries` (no re-implemented ranking). |
| `knowledge_recall(index, *, query=default_query, limit=5)` | A host `KnowledgeIndex` lookup keyed off the Loop State; `InMemoryKnowledgeIndex` is a public-safe reference. |
| `RetrievalBudget(max_entries, max_chars)` | An explicit bound applied before injection; truncation is order-stable with a surfaced `dropped` count. |
| `assemble_recall(sources, budget, *, state)` | Compose sources → de-duplicate by `identifier` → apply the budget → bounded preamble. Returns a `RecallAssembly`. |
| `build_recall_input(base, sources, budget, *, state)` | Wrap a base `InputSource` so its first prompt is prefixed with the recalled preamble. |

## Wiring it into a loop

```python
from loopplane.engineering import LoopDefinition, StaticInput
from loopplane.recall import (
    RetrievalBudget, build_recall_input, conversation_recall, memory_entry_recall,
)

sources = [conversation_recall(), memory_entry_recall(store.list_entries())]
budget = RetrievalBudget(max_entries=6, max_chars=600)
recall_input = build_recall_input(StaticInput("do the task"), sources, budget, state=state)

definition = LoopDefinition(..., input_source=recall_input)
```

The host provides the `state` (a public `LoopState`) — for example the terminal state of a
prior run, or a state reconstructed from the Loop Event stream via
`loopplane.engineering.reconstruct_state`.

See [`examples/recall_quickstart.py`](../examples/recall_quickstart.py) for a runnable demo.

## Determinism, fail-safe, non-mutation

- **Deterministic**: no I/O, clock, or randomness; the same Loop State and store snapshot
  yield an identical injected prompt every run.
- **Fail-safe**: a missing item, a raising store/index, or an over-budget set maps to an
  empty/skipped/truncated result with a diagnostic — never a crash, hang, or fabricated
  context. Input assembly always returns a valid prompt.
- **Non-mutating**: sources and injection only read; stores and the Loop State are never
  changed.
- **Bounded**: the injected preamble never exceeds the `RetrievalBudget`.

## Boundary

`loopplane.recall` imports only `loopplane.engineering`, `loopplane.memory`,
`loopplane.artifacts` value types (plus `select_entries`) and the stdlib. It never imports
the Phase-2 host, the content model, or any runtime internal, and it never calls the loop
entry point. Recall injects context; it does not drive runs.

## Reserved extension points (named, not built)

Embedding/vector stores and similarity search; semantic or model-graded ranking; LLM-based
query rewriting or summarization; external/remote knowledge bases and retrieval services;
RAG pipelines; a persistent cross-restart recall cache. This phase ships only deterministic,
offline recall.
