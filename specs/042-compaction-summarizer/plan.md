# Implementation Plan: Optional Cheap-Model Compaction Summarizer

**Branch**: `042-compaction-summarizer` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/042-compaction-summarizer/spec.md`

## Summary

Add an **optional** cheap-model summarizer to compaction, the deferred half of
spec 041. Today `compact_history` produces a mechanical `SummaryMarkerBlock`
(turn count + tool names + bounded excerpts). This unit lets a host supply a
summarizer `ModelBoundary` via an additive, default-`None`
`RuntimeConfig.compaction_summarizer`; when set, the runtime summarizes the
dropped conversation span and places the model summary into the **existing**
`SummaryMarkerBlock` (replacing its mechanical `excerpts`; keeping `turn_count`
/ `tool_names`). When `None` (default), the mechanical digest is produced exactly
as today — **byte-identical**.

The single most important property is **FAIL-SAFE**: the mechanical
`compact_history` always runs first and is the fallback; the summarizer is a pure
overlay applied after. Any summarizer failure (exception, timeout,
`ContextOverflowError`, empty output) is swallowed and the mechanical digest
stands — compaction always succeeds and a run is **never** broken by the
summarizer.

Because `compact_history` and `PromptAssembler.assemble` are **synchronous**
(and `assemble` has direct synchronous callers, so it cannot become async), the
summarizer runs as an **additive async overlay at the loop's existing async
seams**: once after assembly (the proactive trigger, signalled by a one-shot
assembler flag) and once in the overflow handler (the reactive trigger). The
agent loop's turn cycle is preserved — one awaited overlay step is added at the
two points compaction already runs. `compact_history` itself is unchanged.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: none new — `anyio` (already a dependency) provides the
timeout guard (`anyio.fail_after`); the summarizer is any `ModelBoundary`.

**Storage**: N/A (compaction mutates in-memory history; the durable stream is
append-only and keeps the originals — unchanged. The marker augmentation is a
pure in-memory swap, like `replace_prefix`, and does not invoke the recording
hook).

**Testing**: pytest (offline) — a `ScriptedModel` as the summarizer
(`ScriptedTurn` for a summary, `ScriptedFailure` / `ScriptedOverflow` / empty
turn / a slow stub for the fail-safe cases) + a request-recording wrapper to
assert the summarizer received the dropped turns and no tools + a
`RuntimeController` driven to compact. Mirrors `tests/unit/test_auto_compaction.py`
and `tests/integration/test_us4_memory_skills.py`'s compaction/overflow harness.

**Target Platform**: cross-platform library runtime

**Project Type**: single project — embeddable Python library/runtime

**Constraints**: no change to the agent loop's turn-cycle structure, the runtime
core, the Tool Gateway, the Runtime Event Bus, the event schema, the content
model, or `compact_history`'s output; the default-`None` path is byte-identical;
no new public package/`__all__` name (the 014 bijection stays green); FAIL-SAFE
is non-negotiable; neither `assemble` nor `compact_history` becomes async.

**Scale/Scope**: one new `RuntimeConfig` field (object collaborator, no
coercion/validation); one new internal module `loop/summarizer.py` (the async
overlay + the summarize-request builder); one tiny one-shot flag on
`PromptAssembler`; one tiny additive `SessionHistory.replace_entry`; the loop
gains a summarizer field + two additive awaited overlay calls; the
controller/host-assembly thread the field through; one new offline test module;
docs/tracking touches.

## Constitution Check

*GATE: pass before Phase 0; re-check after design.*

- **I — Spec-First**: PASS (traces to spec 042; it is the documented follow-on
  named in spec 041 research.md Decision 3).
- **II — Greenfield**: PASS (the overlay + request builder are written fresh;
  nothing copied).
- **III — Harness before loop automation**: PASS. The summarizer is a **bounded,
  opt-in, fail-safe overlay** on the existing mechanical compaction; it is **not**
  the reserved full loop-automation layer (no scheduler/validator/evaluator/
  auto-iteration). The loop's turn cycle is preserved (one additive awaited step
  at the two existing compaction points); default-off is byte-identical.
- **IV — Runtime Boundary Clarity**: PASS. The summarizer is just another
  `ModelBoundary`. The overlay lives in the loop package next to compaction; the
  loop already owns the compaction call sites. The controller threads the
  collaborator through the existing wiring. No boundary is blurred (the summarizer
  does not reach into the gateway, the event bus, or the assembler's internals).
- **V — Tool Gateway Ownership**: N/A (the summarizer advertises no tools and
  calls none; no tool concern).
- **VI — Event Bus**: PASS — **a headline gate**. Compaction emits **no** runtime
  event today (it mutates in-memory history only; `replace_prefix` skips the
  recording hook). The summarizer overlay emits none either, and reuses the
  **existing** `SummaryMarkerBlock` / `SummaryDigest` — **no event-schema change,
  no `SCHEMA_VERSION` bump, no content-model change**.
- **VII — Public-Safe**: PASS (a `ModelBoundary | None` field; no secret — a
  summarizer's credential lives in the host model object — no internal path, no
  private name).
- **VIII — No SDK Replacement**: PASS — **a headline gate**. The summarizer is a
  host-supplied `ModelBoundary`, not a framework; the runtime core (loop,
  controller, gateway, event bus) is unchanged and remains LoopPlane's own.
- **IX — Reference, not clone**: PASS (the overlay + fail-safe fallback are
  re-derived for LoopPlane's seams; `compact_history` / `SummaryMarkerBlock` are
  reused unchanged, not re-implemented; recorded in research.md).
- **X — Testable Evolution**: PASS — **the FAIL-SAFE gate**. Deterministic offline
  tests, including the critical "raising/empty/timeout summarizer falls back to the
  mechanical digest and the run continues" case. Rollback =
  `compaction_summarizer = None` or revert the overlay + wiring → exact pre-042
  behavior.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/042-compaction-summarizer/
├── plan.md, research.md, data-model.md, quickstart.md, spec.md, tasks.md
├── contracts/compaction-summarizer.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/loop/summarizer.py      # NEW (internal; no __all__): the async overlay
                                      #   `summarize_compaction(...)` — build the summarize
                                      #   ModelRequest from the dropped span (+ instruction,
                                      #   no tools), collect TextIncrement text under an
                                      #   anyio.fail_after guard, and return a marker with the
                                      #   model summary in its digest, OR the unchanged
                                      #   mechanical marker on ANY failure (FAIL-SAFE).
src/loopplane/loop/history.py         # MODIFY: + `replace_entry(index, entry)` — a tiny
                                      #   additive in-memory swap (mirrors replace_prefix;
                                      #   does not invoke the recording hook).
src/loopplane/loop/assembly.py        # MODIFY: + a one-shot `take_compacted()` flag set when
                                      #   the proactive path compacts (parallel to the existing
                                      #   mark_compacted/_needs_reestablish). compact_history /
                                      #   _estimate_tokens reuse unchanged.
src/loopplane/loop/loop.py            # MODIFY: AgentLoop gains a `summarizer: ModelBoundary |
                                      #   None = None` ctor param; after self._assemble(...) and
                                      #   in the overflow handler, call the overlay (capturing the
                                      #   pre-compaction snapshot for the dropped span). One
                                      #   additive awaited step each; the turn cycle is preserved.
src/loopplane/controller/controller.py # MODIFY: + `compaction_summarizer: ModelBoundary | None =
                                       #   None` kwarg; store it; pass to AgentLoop(summarizer=...).
src/loopplane/host/config.py          # MODIFY: + `compaction_summarizer: ModelBoundary | None =
                                      #   None` field on RuntimeConfig + from_mapping pass-through
                                      #   (object collaborator; no coercion, no validation rule).
src/loopplane/host/assembly.py        # MODIFY: thread config.compaction_summarizer into the
                                      #   RuntimeController(...) kwargs (when not None).

# Usage doc: the feature quickstart.md is the usage guide (no standalone docs/*.md,
# matching the 038/040/041 precedent → the unit-014 docs-index contract stays green).

tests/unit/
└── test_compaction_summarizer.py     # NEW: summarizer summary lands in the marker; summarizer
                                      #   receives the dropped turns + no tools; default-None is
                                      #   byte-identical (mechanical digest, no model call); the
                                      #   FAIL-SAFE cases (raise / empty / overflow / timeout →
                                      #   mechanical digest, run continues); no-recursion.
```

**Structure Decision**: The summarizer is a **host-supplied `ModelBoundary`
collaborator** threaded through the existing `RuntimeConfig` → `assemble()` →
`RuntimeController` → `AgentLoop` wiring (the same path as
`auto_compact_threshold`). The summarize logic is a **new internal module**
(`loop/summarizer.py`, no `__all__`) invoked by the loop at its two existing
async compaction seams — **not** a change to `compact_history` (which stays the
sync mechanical default and the fail-safe fallback) and **not** an async
conversion of `assemble`. The marker is augmented in place via a tiny additive
`SessionHistory.replace_entry`, reusing the existing `SummaryMarkerBlock` /
`SummaryDigest` (the summary goes into `excerpts`). No new runtime component, no
new public name.

## Complexity Tracking

> No Constitution Check violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
