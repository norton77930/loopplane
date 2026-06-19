# Phase 0 Research: Optional Cheap-Model Compaction Summarizer

## Seam verification (read before designing) — the findings the brief asked for

The brief asked to verify five seams **before** designing. Findings:

### 1. The mechanical compaction (`src/loopplane/loop/compaction.py`)

- `compact_history(history, *, keep_last=DEFAULT_KEEP_LAST) -> bool` is a **pure,
  synchronous** function. It snapshots history, computes a cut point that never
  splits a tool call from its result, builds a `SummaryDigest` over the dropped
  prefix (`entries[:keep_from]`), wraps it in a `SummaryMarkerBlock`, and replaces
  the prefix with one `user` marker entry via `SessionHistory.replace_prefix`. It
  returns `False` when there is nothing worth compacting (no model call anywhere).
- **Where the human-readable summary lives**: `SummaryDigest` (in
  `src/loopplane/model/content.py`) has three fields — `turn_count: int`,
  `tool_names: list[str]`, `excerpts: list[str]`. The mechanical "summary" is the
  `excerpts` list (up to 3 bounded user-intent fragments, 80 chars each). **The
  model summary will replace `excerpts`** (one element: the model's summary text),
  keeping `turn_count` and `tool_names` mechanical. `SummaryMarkerBlock` and
  `SummaryDigest` are reused **unchanged** — no new block, no new field (FR-003).

### 2. Where compaction runs (`src/loopplane/loop/assembly.py` + `loop.py`)

Two call sites, confirmed:

- **Proactive** — inside `PromptAssembler.assemble` (spec 041): after composing
  the request, if `_estimate_tokens(request) > _effective_capacity(capacity)` it
  calls `compact_history(history, keep_last=self.keep_last)` and rebuilds. **This
  method is SYNCHRONOUS (`def assemble`, not `async def`).**
- **Reactive** — inside `AgentLoop.run`'s `except ContextOverflowError` block
  (`loop.py` ~line 144): `compact_history(self._history, keep_last=...)` then a
  single retry (FR-008). **This site is in an `async def run` — it can await.**

**The crux (the brief's central question — is the compaction path async?)**:
`PromptAssembler.assemble` is **synchronous** and has exactly **one** production
caller — `AgentLoop._assemble` (`loop.py:214`), itself a sync helper called from
the async `run` at `loop.py:136` — plus **synchronous** test callers
(`tests/unit/test_auto_compaction.py` calls `off.assemble(...)` /
`on.assemble(...)` directly). Making `assemble` `async` would be a **breaking
sync→async change** to a method with direct sync callers and would ripple into the
loop and tests. The brief forbids that ("do NOT make the loop sync→async in a
breaking way"). So **the summarizer model call cannot be awaited inside
`assemble` or inside `compact_history`.**

### 3. The model boundary (`src/loopplane/model/boundary.py` + `scripted.py`)

- `ModelBoundary` is a `runtime_checkable` Protocol: `stream_turn(request:
  ModelRequest) -> AsyncIterator[ModelIncrement]` + `context_capacity() -> int`.
  `ModelRequest(context: list[Message], tools: list[ToolDescriptor], limits)`;
  `Message(role, blocks)`; increments are `TextIncrement` / `ReasoningIncrement` /
  `ToolCallRequest` / `TurnEnd`. To summarize: build a `ModelRequest` from the
  dropped turns + a summarize instruction (no tools), iterate `stream_turn`, and
  collect `TextIncrement.text`.
- `ScriptedModel(script, context_capacity)` is the deterministic offline test
  instrument; `ScriptedTurn(increments=[TextIncrement(...)])` plays back a summary,
  `ScriptedFailure(error=...)` raises, `ScriptedOverflow()` signals overflow. This
  is the test summarizer — no network.

### 4. Existing adapters/providers

A host could pass a cheap real model (`openai_model("gpt-5-mini")`,
`ollama_model(...)`, etc.) as the summarizer. We depend only on the
`ModelBoundary` contract and test exclusively with `ScriptedModel`. No adapter
change is needed.

### 5. Config wiring (`src/loopplane/host/config.py` + `host/assembly.py`)

`RuntimeConfig` threads collaborators/flags through `host/assembly.py:assemble()`
→ `RuntimeController.__init__` → `_assemble()` → the per-session `PromptAssembler`
/ `AgentLoop`. `auto_compact_threshold` (041) is the exact precedent: a field on
`RuntimeConfig`, coerced in `from_mapping`, passed via `controller_kwargs` when
non-`None`, stored on the controller, handed to the assembler. **The summarizer
follows the same path** — but as an *object collaborator* (like `model`), so
`from_mapping` passes it through unchanged (no coercion).

### Constitution touchpoints

- **VI (event bus)**: compaction emits **no** runtime event today (it mutates
  in-memory history via `replace_prefix`, which deliberately skips the recording
  hook). The summarizer overlay emits none either → no event-schema change, no
  `SCHEMA_VERSION` bump, no content-model change. Confirmed by grep of
  `src/loopplane/events` for `compact`/`digest`/`SummaryMarker` (nothing).
- **VIII (no SDK replacement)**: the summarizer is just another `ModelBoundary`,
  not a runtime-core change. The loop/controller/gateway/bus stay LoopPlane's own.
- **X (TDD + rollback)**: deterministic offline tests; rollback =
  `compaction_summarizer = None` or revert the overlay + wiring → exact pre-042
  behavior.

## Decision 1 — Run the summarizer as a post-compaction async overlay (not inside `compact_history`/`assemble`)

- **Decision**: Keep `compact_history` and `PromptAssembler.assemble` **fully
  synchronous and unchanged**. Add an internal async helper
  `summarize_compaction(...)` (new module `loopplane/loop/summarizer.py`) that the
  **loop** invokes at its existing async seams, **after** the mechanical
  compaction has produced the marker:
  - after `self._assemble(prompt)` returns — covering the **proactive** trigger,
    which the assembler signals to the loop via a one-shot `take_compacted()` flag
    (parallel to the existing `mark_compacted`/`_needs_reestablish` flag);
  - in the `except ContextOverflowError` block, right after the existing reactive
    `compact_history(...)` call — covering the **reactive** trigger.
- **Rationale**: This is the **only** way to await a model call without making the
  sync compaction path async (which is forbidden and would break direct sync test
  callers of `assemble`). The loop already `await`s at both points, so the overlay
  is a single additive awaited step — **not** a turn-cycle rewrite. `compact_history`
  stays the pure mechanical default **and** the fail-safe fallback (Decision 3).
- **Why the assembler needs a one-shot flag**: proactive compaction happens
  *inside* the sync `assemble`, so the loop cannot otherwise know it occurred.
  Mirroring the existing `mark_compacted`/`_needs_reestablish` pattern, the
  assembler records "I just proactively compacted" and the loop reads-and-clears
  it after assembly. When no assembler is attached, there is no proactive path and
  the flag is irrelevant; the reactive overlay still runs.
- **Why not inside `compact_history`**: it is sync and is also called directly by
  integration tests as a pure transform — folding an async model call into it
  would change its character and break its synchronous contract.
- **Why not make `assemble` async**: it has a direct synchronous production caller
  (`AgentLoop._assemble`) and direct synchronous test callers; an async signature
  is a breaking change the brief forbids. The overlay sidesteps this entirely.

## Decision 2 — How the marker is augmented: model summary into `SummaryDigest.excerpts`

- **Decision**: The overlay locates the freshly produced `SummaryMarkerBlock`
  (compaction places it as the **first** history entry, a single-block `user`
  entry — `replace_prefix` writes it at index 0), and, on a successful summary,
  rewrites that entry with a new `SummaryMarkerBlock(digest=SummaryDigest(
  turn_count=<mechanical>, tool_names=<mechanical>, excerpts=[<model summary>]))`.
  `turn_count` and `tool_names` are copied verbatim from the mechanical digest;
  only `excerpts` is replaced (with a single element: the model's summary text).
- **Rationale**: Reuses the existing block and digest fields (no content-model
  change; FR-003). The summary is a coherent paragraph, so a single `excerpts`
  element is the natural carrier; consumers that already render `excerpts` show the
  model summary with no change. `turn_count` / `tool_names` remain mechanically
  accurate (they are facts about the dropped span, not prose).
- **Re-writing the entry**: `SummaryMarkerBlock` / `SummaryDigest` /
  `HistoryEntry` are frozen pydantic models, so augmentation builds a new entry and
  swaps it via a tiny additive `SessionHistory.replace_entry(index, entry)` helper
  (the in-memory durable stream already keeps the originals; `replace_prefix`
  established that the marker is a pure in-memory artifact). The new helper does
  **not** invoke the recording hook (consistent with `replace_prefix`).

## Decision 3 — FAIL-SAFE: the mechanical digest is always the fallback

- **Decision (the non-negotiable property)**: The mechanical `compact_history`
  **always runs first** and produces a complete, valid `SummaryMarkerBlock`. The
  overlay then *tries* to augment it. The entire summarize attempt is wrapped so
  that **any** failure leaves the mechanical marker untouched:
  - an exception from `stream_turn` (including `ContextOverflowError`) → caught;
  - a timeout (the attempt exceeds a guard deadline) → cancelled, treated as
    failure;
  - empty or whitespace-only collected text → rejected (not a valid summary).
  In every failure case the overlay is a **no-op** and the mechanical digest
  stands. Compaction has already succeeded (the marker exists); the run never
  fails because of the summarizer (FR-005).
- **Timeout guard (FR-006)**: `anyio.fail_after(<deadline seconds>)` around the
  stream-collection wraps a hung/slow summarizer; on `TimeoutError` the attempt is
  abandoned. The deadline is a small constant (a summarizer is meant to be cheap
  and fast); a hung summarizer cannot stall the run.
- **No recursion (FR-007)**: the summarize call uses the summarizer's
  `stream_turn` **directly** with a plain `ModelRequest` — no `PromptAssembler`, no
  tools, no compaction. A `ContextOverflowError` from the summarizer is just a
  failure (mechanical fallback), never a trigger to compact-and-retry. The
  summarizer is a different `ModelBoundary` from the main model and is only ever
  consulted to summarize, so it cannot re-enter the compaction path.
- **Why this is safe by construction**: the success path is the *only* path that
  mutates the marker, and it mutates it to a strictly-valid alternative (same
  digest shape, non-empty summary). Every other path is a no-op over an
  already-valid marker.

## Decision 4 — The summarize request (FR-004)

- **Decision**: Build `ModelRequest(context=[<instruction message>,
  <dropped-span messages>], tools=[])`. The instruction is a concise system/user
  text block: "Summarize the following conversation so far, preserving the key
  facts, decisions, and context needed to continue. Be concise." The dropped span
  is the same `entries[:keep_from]` prefix the mechanical digest summarized,
  converted to `Message`s (role + blocks). No tools are advertised (the summarizer
  must not call tools). The summary is the concatenation, in order, of every
  `TextIncrement.text` the summarizer yields; non-text increments are ignored.
- **How the overlay knows the dropped span**: the loop captures the pre-compaction
  history snapshot (before `compact_history` runs) so the overlay receives the
  exact dropped prefix. Equivalently the overlay derives it from the marker plus
  the surviving suffix; capturing the pre-snapshot is simpler and exact.

## Decision 5 — Config & wiring (FR-009)

- **Decision**: Add `compaction_summarizer: ModelBoundary | None = None` to
  `RuntimeConfig` (alongside `auto_compact_threshold`). It is an **object
  collaborator** like `model`, so `from_mapping` passes it through unchanged
  (`data.get("compaction_summarizer")`); no coercion, no validation rule (any
  object satisfying the `ModelBoundary` protocol is valid; `None` is off). It
  carries no secret. `host/assembly.py:assemble()` adds it to `controller_kwargs`
  when set; `RuntimeController.__init__` stores it and hands it to the per-session
  `AgentLoop` (and the assembler need not know about it — the overlay lives in the
  loop). No new public `__all__` name (FR-012): `RuntimeConfig` is already
  exported and `ModelBoundary` is already public; the summarize helper module has
  no `__all__`, so `public_packages()` ignores it and the 014 bijection stays
  green with no doc edit.

## Decision 6 — Offline-only, deterministic tests (FR-013)

- **Decision**: All new tests are offline. A `ScriptedModel` plays the summarizer:
  `ScriptedTurn(increments=[TextIncrement(text="<known summary>")])` for the happy
  path; `ScriptedFailure(error=RuntimeError(...))` and `ScriptedOverflow()` for the
  fail-safe path; an empty `ScriptedTurn()` for empty output; a custom slow
  summarizer (an `async` `stream_turn` that sleeps past the guard) for the timeout
  path. A `RecordingModel`-style wrapper captures the `ModelRequest` handed to the
  summarizer so we can assert it carries the dropped turns and no tools. Mirrors
  `tests/unit/test_auto_compaction.py` and the compaction/overflow harness in
  `tests/integration/test_us4_memory_skills.py`.
