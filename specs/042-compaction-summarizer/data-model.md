# Data Model: Optional Cheap-Model Compaction Summarizer

This unit adds **no new content block and no new event**. It reuses the existing
`SummaryMarkerBlock` / `SummaryDigest` (the model summary lives in the existing
`excerpts` field) and adds one optional config field plus an internal overlay.

## Reused, unchanged

- **`compact_history(history, *, keep_last)`** (`loopplane.loop.compaction`) — the
  pure, synchronous mechanical compaction. **Unchanged.** It always runs first and
  is the fail-safe fallback. Produces a `SummaryMarkerBlock`.
- **`SummaryMarkerBlock` / `SummaryDigest`** (`loopplane.model.content`) —
  **unchanged.** `SummaryDigest` has `turn_count: int`, `tool_names: list[str]`,
  `excerpts: list[str]`. The model summary replaces `excerpts` (a single element);
  `turn_count` / `tool_names` stay mechanical. Both are frozen pydantic models, so
  augmentation builds a new instance.
- **`ModelBoundary`** (`loopplane.model.boundary`) — **unchanged.** The summarizer
  is any object satisfying this protocol (`stream_turn` + `context_capacity`).
  Already a public name.

## New field: `RuntimeConfig.compaction_summarizer` (`loopplane.host.config`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `compaction_summarizer` | `ModelBoundary \| None` | `None` | `None` → compaction produces the mechanical digest, byte-identical to today (off). A `ModelBoundary` → compaction asks it to summarize the dropped span into the `SummaryMarkerBlock` (FAIL-SAFE fallback to mechanical on any failure). An **object collaborator** (like `model`); carries no secret. |

- `from_mapping`: pass-through — `compaction_summarizer=data.get(
  "compaction_summarizer")`. No coercion (it is an object, like `model`/handlers).
- `validate_config`: **no new rule** — any `ModelBoundary` is valid; `None` is off.
  (Unlike `auto_compact_threshold`, there is no numeric range to check.)

## New internal module: `loopplane.loop.summarizer` (no `__all__`)

```python
async def summarize_compaction(
    *,
    summarizer: ModelBoundary,
    dropped: tuple[HistoryEntry, ...],   # the pre-compaction prefix that was compacted
    marker: SummaryMarkerBlock,          # the mechanical marker just produced
    timeout_seconds: float = ...,        # the guard deadline (a small constant)
) -> SummaryMarkerBlock:
    """Return a marker with the MODEL's summary in its digest, or the unchanged
    mechanical `marker` on ANY failure (FAIL-SAFE)."""
```

- Builds `ModelRequest(context=[instruction, *messages_from(dropped)], tools=[])`.
- Iterates `summarizer.stream_turn(request)` under `anyio.fail_after(timeout)`,
  collecting `TextIncrement.text` in order.
- **Success** (non-empty, non-whitespace text) → returns
  `SummaryMarkerBlock(digest=SummaryDigest(turn_count=marker.digest.turn_count,
  tool_names=marker.digest.tool_names, excerpts=[summary]))`.
- **Any failure** (exception incl. `ContextOverflowError`, `TimeoutError`, empty
  output) → returns `marker` unchanged. **Never raises.**
- Advertises no tools and uses no assembler → no recursion into compaction
  (FR-007).

## New helper: `SessionHistory.replace_entry` (`loopplane.loop.history`)

| Method | Signature | Meaning |
|--------|-----------|---------|
| `replace_entry` | `(self, index: int, entry: HistoryEntry) -> None` | Replace the in-memory entry at `index` (used by the summarizer overlay to swap the mechanical marker for the augmented one). Mirrors `replace_prefix`: the durable stream is append-only and keeps the originals, and the recording hook is **not** invoked. |

## New one-shot flag: `PromptAssembler.take_compacted` (`loopplane.loop.assembly`)

| Method | Signature | Meaning |
|--------|-----------|---------|
| `take_compacted` | `(self) -> bool` | Read-and-clear: returns `True` exactly once after the proactive path ran `compact_history` in `assemble`, so the loop knows a proactive compaction occurred (and can run the summarizer overlay). Parallel to the existing `mark_compacted` / `_needs_reestablish`. `False` when no proactive compaction occurred. |

- `assemble`: when the proactive branch calls `compact_history(...)` and it returns
  `True`, set `self._just_compacted = True`. Default `False`.

## `AgentLoop` (`loopplane.loop.loop`)

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `summarizer` | `ModelBoundary \| None` | `None` | The optional compaction summarizer. `None` → the overlay is a no-op (mechanical digest only). |

- After `request = self._assemble(prompt)`: if `self._summarizer is not None` and
  the assembler reports `take_compacted()`, run the overlay over the captured
  pre-compaction snapshot, and re-`_assemble` is **not** needed (the marker is
  swapped in place; the already-composed `request` still references the old marker,
  so the loop re-composes — see contract C1 note). The simplest correct form
  captures the snapshot, lets `_assemble` compact + compose, then augments the
  marker and **recomposes** the request so the model sees the summarized marker.
- In `except ContextOverflowError`: after the existing `compact_history(...)`
  returns `True`, run the overlay over the captured pre-compaction snapshot before
  the retry, so the retry's assembly carries the summarized marker.

## `RuntimeController` (`loopplane.controller.controller`)

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `compaction_summarizer` | `ModelBoundary \| None` | `None` | Stored as `self._compaction_summarizer`; passed to the per-session `AgentLoop(summarizer=...)` in `_assemble`. `None` → the loop's overlay is inert. |

## Traceability

- FR-001 / FR-009: `RuntimeConfig.compaction_summarizer` (object collaborator),
  threaded `RuntimeConfig` → `assemble()` → `RuntimeController` → `AgentLoop`.
- FR-002 / FR-008: `compaction_summarizer is None` → overlay no-op →
  `compact_history`'s mechanical marker stands, byte-identical; no model call.
- FR-003: success path rewrites only `excerpts`; `turn_count` / `tool_names`
  copied; `SummaryMarkerBlock` / `SummaryDigest` reused unchanged.
- FR-004: `ModelRequest(context=[instruction, *dropped], tools=[])`; summary =
  concatenated `TextIncrement.text`.
- FR-005 / FR-006 / FR-007: the overlay never raises; `anyio.fail_after` guard;
  no assembler/tools/compaction recursion; `ContextOverflowError` is a failure.
- FR-010 / FR-011 / FR-012: no event, no content-model change, no new public name
  (internal module without `__all__`; `RuntimeConfig` already exported).
