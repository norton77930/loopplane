# Implementation Plan: Configurable Proactive Auto-Compaction

**Branch**: `041-auto-compaction` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/041-auto-compaction/spec.md`

## Summary

Make LoopPlane's **existing** proactive pre-send compaction trigger
**configurable**. Today `PromptAssembler.assemble` already estimates the
assembled context (`_estimate_tokens`, a `chars ÷ 4` heuristic) and, when that
estimate exceeds the model's **full** `context_capacity()`, runs the mechanical
`compact_history` once before the model call; the loop keeps the reactive
`ContextOverflowError` compact-and-retry-once backstop (FR-008). This unit adds
an additive, default-`None` `RuntimeConfig.auto_compact_threshold: float | None`.
`None` → the pre-send check compares against the **full** capacity (today's exact
behavior → byte-identical). A value `f` in `(0, 1]` → the check compares against
`f * context_capacity()`, so the existing compaction runs *earlier*, at a safety
margin. The threshold is threaded through the same wiring as `plan_mode` /
`allow_network` (`RuntimeConfig` → `assemble()` → `RuntimeController` →
`PromptAssembler`), validated fail-fast at assembly. `compact_history` and
`_estimate_tokens` are reused **unchanged**; compaction stays silent (no event).
The cheap-model summarizer is **deferred** to spec 042 (research.md Decision 3).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: none new — pure-stdlib arithmetic over the existing
estimate and capacity.

**Storage**: N/A (compaction mutates in-memory history; the durable stream is
append-only and keeps the originals via `replace_prefix` — unchanged).

**Testing**: pytest (offline) — a scripted model (`model/scripted.py`) +
`RecordingModel` (records each assembled request) + a `RuntimeController` with the
threshold set; assert the triggering turn's request was already compacted (carries
a `SummaryMarkerBlock`); assert default-`None` matches today (no compaction below
full capacity, the full-capacity compaction still fires above it); assert the
reactive backstop is unchanged; unit-test the effective-capacity computation and
the invalid-threshold `ConfigError`. Mirrors the existing
`tests/integration/test_us4_memory_skills.py` compaction/overflow harness and
`tests/contract/test_host_config.py` config-wiring tests.

**Target Platform**: cross-platform library runtime

**Project Type**: single project — embeddable Python library/runtime

**Constraints**: no change to the agent loop's turn cycle, the runtime core, the
Tool Gateway, the Runtime Event Bus, the event schema, the content model, or
`TokenUsage`'s shape; `compact_history`'s output stays byte-identical; the
default-`None` path is the existing behavior; no new public package/`__all__`
name (the 014 bijection stays green).

**Scale/Scope**: one new optional parameter on `PromptAssembler.__init__` + a
tiny `_effective_capacity` helper, one new constructor kwarg on
`RuntimeController` threaded to the assembler, one new `RuntimeConfig` field +
`from_mapping` coercion + `validate_config` rule + the `assemble()` wiring line,
one new offline test module (plus a config-validation test), and docs/tracking
touches.

## Constitution Check

*GATE: pass before Phase 0; re-check after design.*

- **I — Spec-First**: PASS (traces to spec 041).
- **II — Greenfield**: PASS (the threshold + effective-capacity logic is written
  fresh; nothing copied).
- **III — Harness before loop automation**: PASS — **the headline gate**.
  Proactive compaction is a **bounded, opt-in efficiency trigger** that **reuses
  the existing** mechanical compaction; it is **not** the reserved full
  loop-automation layer (no scheduler/validator/evaluator/auto-iteration). The
  agent loop's turn cycle is untouched; the only new behavior is a configurable
  multiplier on an already-present pre-send check. Default-off is byte-identical,
  so the foundation's behavior is preserved unless a host opts in.
- **IV — Runtime Boundary Clarity**: PASS (the trigger lives in the assembler —
  which already owns proactive compaction sizing per its module docstring — and
  the config wiring; the loop/controller/gateway/bus boundaries are unchanged).
- **V — Tool Gateway Ownership**: N/A (no tool concern).
- **VI — Event Bus**: PASS — **the second headline gate**. Compaction emits **no
  runtime event** today (it mutates in-memory history only; the reactive path
  emits nothing either), so the proactive path emits nothing and there is **no
  event-schema change and no `SCHEMA_VERSION` bump**. The normalized event stream
  is identical.
- **VII — Public-Safe**: PASS (a `float | None` threshold; no secret, internal
  path, or private name).
- **VIII — No SDK Replacement**: N/A (no framework/SDK involved).
- **IX — Reference, not clone**: PASS (the threshold semantics are re-derived for
  LoopPlane's existing assembler check; `compact_history` / `_estimate_tokens` are
  reused unchanged, not re-implemented — Constitution IX; recorded in research.md).
- **X — Testable Evolution**: PASS (deterministic offline tests; rollback =
  `auto_compact_threshold = None` or revert the assembler/controller/config
  additions → exact pre-threshold behavior).

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/041-auto-compaction/
├── plan.md, research.md, data-model.md, quickstart.md, spec.md, tasks.md
├── contracts/auto-compaction.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/loop/assembly.py        # MODIFY: + `compact_threshold: float | None = None`
                                      #   param on PromptAssembler.__init__; the proactive
                                      #   check uses `_effective_capacity(capacity)`
                                      #   (= int(capacity * threshold) when set, else capacity).
                                      #   `_estimate_tokens` / `compact_history` reuse unchanged.
src/loopplane/controller/controller.py # MODIFY: + `auto_compact_threshold: float | None = None`
                                       #   kwarg; store it; pass to PromptAssembler(...).
src/loopplane/host/config.py          # MODIFY: + `auto_compact_threshold: float | None = None`
                                      #   field on RuntimeConfig + from_mapping coercion +
                                      #   validate_config range check (0 < f <= 1, finite).
src/loopplane/host/assembly.py        # MODIFY: thread config.auto_compact_threshold into the
                                      #   RuntimeController(...) kwargs (when not None).

# Usage doc: the feature quickstart.md is the usage guide (no standalone docs/*.md,
# matching the 038/040 precedent → the unit-014 docs-index contract stays green).

tests/unit/
└── test_auto_compaction.py           # NEW: effective-capacity math; proactive at/over/under
                                      #   threshold; default-None == today; reactive backstop;
                                      #   invalid-threshold ConfigError; from_mapping round-trip.
```

**Structure Decision**: The threshold is a **constructor parameter** on the
existing `PromptAssembler` (carried through the existing controller→assembler
wiring), not a new module or a change to `compact_history`. The proactive check
already lives in `PromptAssembler.assemble`; this unit only replaces its
`> capacity` comparison with `> _effective_capacity(capacity)`, where
`_effective_capacity` returns the full capacity when the threshold is `None`
(preserving today's behavior exactly). The config field sits on the existing
`RuntimeConfig` alongside `plan_mode` / `allow_network` / `permission_rules`,
wired through the same `assemble()` → `RuntimeController` path — no new runtime
component, no new public name.

## Complexity Tracking

> No Constitution Check violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
