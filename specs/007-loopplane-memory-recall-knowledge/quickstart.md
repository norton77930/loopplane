# Quickstart & Validation: Memory Recall & Knowledge Layer (Phase-7)

A validation guide for `loopplane.recall`. It proves recall sources compose into a Phase-3 `InputSource`
that injects bounded, deterministic, public-safe recalled context — over scripted Loop State and in-memory
stores, with no filesystem, credentials, or network. Implementation detail lives in
[data-model.md](./data-model.md) and [contracts/](./contracts); these are runnable scenarios.

## Prerequisites

- The repo installed editable with dev tools: `python -m pip install -e .` and `pytest` + `anyio`.
- Phases 1 and 3 are Verified (the public `loopplane.memory`, `loopplane.artifacts`, and
  `loopplane.engineering` surfaces this layer composes).

## What the example shows

`examples/recall_quickstart.py` (public-safe, credential-free):

1. Builds a scripted `LoopState` for a loop with a couple of prior `run_refs` and an `ArtifactRef`.
2. Builds three recall sources — `conversation_recall()`, `artifact_recall(reader)` over a scripted
   in-memory artifact reader, and `memory_entry_recall(entries)` over a scripted `MemoryEntry` list — plus an
   optional `knowledge_recall(InMemoryKnowledgeIndex([...]))`.
3. Composes them with `build_recall_input(StaticInput("do the task"), sources, RetrievalBudget(max_entries=5,
   max_chars=600), state=state)`.
4. Prints `assemble_recall(...)` (the preamble, kept entries, and the `dropped` count) and the final
   `InputSource.initial()` prompt.

Run:

```bash
python examples/recall_quickstart.py
```

Expected: a bounded recalled preamble (most-recent-first conversation, newest-first artifact metadata, the
selected memory entries) prepended to `"do the task"`, with an explicit `dropped` count when the budget
truncates, and no secrets, content bytes, or filesystem paths in the output.

## Validation scenarios (map to user stories & success criteria)

| Scenario | How to validate | Proves |
|---|---|---|
| US1 — conversation recall injected | Build `build_recall_input(StaticInput("X"), [conversation_recall()], budget, state=<2 run_refs>)`; assert `initial()` contains both runs most-recent-first; a no-run state ⇒ `"X"` unchanged | SC-001, FR-010–FR-013, FR-055 |
| Determinism | Call `initial()` twice over the same state + stores; assert byte-identical | SC-002, NFR-001 |
| Loop scoping | Recall over loop `A`'s state never contains loop `B`'s run/artifact data | SC-003, FR-062 |
| US2 — artifact recall, public-safe | `artifact_recall(reader)` over scripted metadata; assert newest-first, reference+metadata only, no content/path; missing metadata is skipped | SC-007, FR-020–FR-022 |
| US3 — memory-entry recall | `memory_entry_recall(entries)` returns exactly the `select_entries(entries, query, limit)` result, adapted | SC-002, FR-030–FR-032 |
| US4 — compose + budget | Two sources with overlapping ids + a small budget; assert de-dup by precedence, injected size within budget, `dropped` surfaced | SC-004, SC-009, FR-050–FR-053 |
| US5 — knowledge index | `knowledge_recall(InMemoryKnowledgeIndex([...]))` returns the matched entries; a raising index ⇒ empty recall + diagnostic | SC-005, FR-040–FR-043, NFR-005 |
| Non-mutation | After recall, the bound stores and the `LoopState` are unchanged | NFR-006 |
| Boundary | Import-boundary audit: `loopplane.recall` imports only `engineering` / `memory` / `artifacts` value types + stdlib; drives no run | SC-008, FR-060, FR-061 |
| Public-safety | Scan committed files + `PHASE7_TARGETS`; no secrets/paths/private names | SC-006, NFR-002 |

## Test commands

```bash
# Unit + integration + contract suites for this layer
python -m pytest tests/unit/test_recall_core.py tests/integration -k recall --basetemp=".pytmp" -q
python -m pytest tests/contract/test_recall_boundary.py --basetemp=".pytmp" -q

# Full gates (run before any commit touching source/tests)
python -m ruff format && python -m ruff check && python -m mypy
python -m pytest --basetemp=".pytmp" -q
```

Expected: all recall suites green; ruff + mypy(strict) clean; public-safety scan green.

## What this layer does NOT do

No embeddings/vector/semantic search, no ML/LLM ranking or rewriting, no remote/external index, no RAG, no
persistent cache (reserved — FR-090–FR-095). It starts/drives no Loop Run and stores/selects nothing
itself; it only composes recalled context into a Phase-3 `InputSource`.
