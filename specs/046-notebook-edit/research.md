# Research: Notebook Editing (`notebook_edit`)

No open `NEEDS CLARIFICATION`. Decisions below.

## Decision 1 — Where the tool lives

**Decision**: A handler on the existing `InternalToolAdapter` (`src/loopplane/tools/internal.py`),
added to the always-on `_DESCRIPTORS`, exactly like unit 044's `todo_write` and the file tools.

**Rationale**: It is a dependency-free, working-scope file tool, like `edit_file`. Reuses the
adapter's `_resolve` (scope confinement) and dispatch; no wiring/host change.

**Alternatives considered**: a separate adapter (rejected — unjustified new component).

## Decision 2 — Notebook parsing (no Jupyter dependency)

**Decision**: Parse and re-serialize the `.ipynb` with the standard-library `json` module
(add `import json` to `internal.py`). Round-trip the whole parsed document and mutate only the
`cells` list, so unknown/other fields (`nbformat`, `metadata`, other cells' `outputs`) are
preserved.

**Rationale**: `.ipynb` is JSON; the standard library suffices (Constitution X, no new
dependency). Round-tripping preserves everything outside the targeted cell.

**Alternatives considered**: the `nbformat` library (rejected — a new dependency for no gain);
regex/string editing (rejected — would corrupt JSON).

## Decision 3 — Guards reuse `edit_file`'s pattern

**Decision**: Confine the path with the existing `_resolve` (working scope) and apply the
existing stale-write guard via `self._reads` — the notebook must have been read in this session
(`read_file`) and be unchanged since; on success, refresh the recorded digest (so a second edit
without an intervening read still works, like `edit_file`).

**Rationale**: Reuse-first; identical safety semantics to the other mutating file tools.

**Alternatives considered**: no guard (rejected — clobbers concurrent/under-foot changes);
a separate guard (rejected — duplicates `edit_file`).

## Decision 4 — Operations & selection

**Decision**: Three operations selected by `mode` — `replace` (set `cells[index].source`),
`insert` (insert a new cell of `cell_type` `code`/`markdown` with `source` at `index`;
`index == len(cells)` appends), `delete` (remove `cells[index]`). Selection is by integer
`index`. Validate the parsed document is a notebook (a dict with a `cells` list) and the index
is in range (insert allows `== len`); otherwise a normalized `VALIDATION` error, file unchanged.

**Rationale**: Covers the reference harnesses' cell edit/insert/delete by index; minimal and
unambiguous. New cells are built as minimal valid cells (`cell_type`, `source`, plus empty
`metadata`, and for code an empty `outputs`/`execution_count: null`) so the notebook stays valid.

**Alternatives considered**: selection by cell id (deferred — a later refinement); editing
outputs/execution (out of scope).

## Decision 5 — No event-schema / content-model change

**Decision**: Result is a `TextBlock`; failures are `ErrorOutput`. No new content block, event,
or `SCHEMA_VERSION` bump; no ADR.

**Rationale**: Expressible with existing primitives (Constitution VI, X).
