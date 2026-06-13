# Contract: Memory Injection Policy & the Layer Boundary

The public surface of `loopplane.recall` for composing recall sources into a Phase-3 `InputSource`, plus the
import/runtime boundary the layer guarantees.

## Memory Injection Policy (FR-050–FR-055)

```python
@dataclass(frozen=True)
class RecallAssembly:
    preamble: str
    entries: tuple[RecalledEntry, ...]
    dropped: int
    skipped: tuple[str, ...]

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

- `assemble_recall` is pure and deterministic. It calls each source in order; a source that raises
  contributes nothing and its label is recorded in `skipped` (NFR-005). It concatenates entries in **source
  order, then within-source order**, de-duplicates by `identifier` keeping the first (highest-precedence)
  occurrence (`identifier=None` always kept), applies the budget (`dropped` carries the truncation count,
  FR-053), and formats `kept` into a bounded text `preamble` (`""` when nothing is recalled).
- `build_recall_input` returns an `InputSource` whose `initial()`:
  - assembles recall for the bound `state`;
  - **string base** ⇒ returns `preamble + "\n\n" + base.initial()` when `preamble` is non-empty, else the
    base string unchanged (FR-055);
  - **`Sequence[ContentBlock]` base** ⇒ returns it unchanged (recall augments string prompts this phase);
  - mutates neither `base`, the `state`, nor any store (NFR-006).
- The injected preamble is always within `RetrievalBudget` (NFR-007, SC-004); the `dropped` count is
  available via `assemble_recall` for callers that surface truncation (SC-009).

## Boundary (FR-060, FR-061, NFR-003)

```text
loopplane.recall  ──imports──►  loopplane.engineering  (LoopState, RunReference, ArtifactRef,
                                                         InputSource, Prompt, StaticInput)
                  ──imports──►  loopplane.memory        (MemoryEntry, select_entries)
                  ──imports──►  loopplane.artifacts     (ArtifactMeta)
                  ──imports──►  (stdlib only otherwise)
```

Prohibited (asserted by the import-boundary audit, `test_recall_boundary.py`):

- The layer drives **no** Loop Run: it never imports or calls `run_loop` / `LoopController` and never starts
  or observes a run; it only **produces** an `InputSource` the host wires into a `LoopDefinition` (FR-060).
- It imports **no** Phase-2 host symbol (`loopplane.host`, `LoopPlaneHost`, `RuntimeConfig`), **no** content
  model (`loopplane.model`), and **no** Phase-1 runtime internal (`loopplane.controller`,
  `loopplane.gateway`, `loopplane.context`, `loopplane.approval`, …) or sibling layer
  (`loopplane.scheduling`, `loopplane.packs`, `loopplane.review`) (FR-061, NFR-003).
- It **mutates nothing**: no store, no Memory, no Artifact Storage, no `LoopState`, no base `InputSource`
  (NFR-006).

Allowed prefixes for `loopplane.*` imports: `loopplane.engineering`, `loopplane.memory`,
`loopplane.artifacts`, `loopplane.recall`. Everything else is a boundary violation.

## Non-duplication (FR-070, SC-008)

The layer contains no storage, selection, looping, scheduling, host, or runtime logic. Selection authority
stays in Phase-1 (`select_entries`); the loop entry point stays in Phase-3 (`run_loop`); content stores stay
host-owned. The recall layer only reads the public surfaces and composes recalled context into an
`InputSource`.
