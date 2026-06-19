# Requirements Quality Checklist — Compaction Summarizer (042)

A self-review of the spec's quality, traceability, and constitution alignment.

## Additivity & reuse

- [x] CHK001 — The summarizer is an additive, default-`None`
  `RuntimeConfig.compaction_summarizer: ModelBoundary | None`. (PASS — FR-001.)
- [x] CHK002 — `compaction_summarizer = None` is byte-identical to today (the
  mechanical digest; no model call). (PASS — FR-002; SC-002; C3.)
- [x] CHK003 — Reuses the existing `SummaryMarkerBlock` / `SummaryDigest` (summary
  into `excerpts`); no new block, no new field. (PASS — FR-003; C8.)
- [x] CHK004 — `compact_history` is unchanged and is both the default and the
  fail-safe fallback. (PASS — FR-008; C8.)
- [x] CHK005 — No new public package or `__all__` name (internal summarizer
  module; `RuntimeConfig` already exported; `ModelBoundary` already public). (PASS
  — FR-012; SC-005.)

## FAIL-SAFE (the non-negotiable property)

- [x] CHK006 — ANY summarizer failure (exception, timeout, `ContextOverflowError`,
  empty output) falls back to the mechanical digest. (PASS — FR-005; C4/C5/C6/C7.)
- [x] CHK007 — Compaction always succeeds and a run is NEVER broken by the
  summarizer. (PASS — FR-005; SC-003.)
- [x] CHK008 — A guard timeout bounds a slow/hung summarizer. (PASS — FR-006; C6.)
- [x] CHK009 — The summarizer does not recurse into compaction/the assembler; a
  `ContextOverflowError` from it is a failure, not a compact-and-retry trigger.
  (PASS — FR-007; C7.)
- [x] CHK010 — There is an explicit fail-safe test (raising/empty/timeout
  summarizer → mechanical digest, run continues). (PASS — FR-013; US3.)

## Seam correctness (no breaking change)

- [x] CHK011 — `PromptAssembler.assemble` and `compact_history` stay synchronous;
  the summarizer runs at the loop's existing async seams (after assembly; in the
  overflow handler). (PASS — research.md Decision 1; FR-010.)
- [x] CHK012 — The agent loop's turn-cycle structure is preserved (one additive
  awaited overlay step at the two existing compaction points). (PASS — FR-010;
  SC-006.)
- [x] CHK013 — The summarizer receives the dropped turns and no tools. (PASS —
  FR-004; SC-004; C2.)

## Boundaries & constitution

- [x] CHK014 — No event-schema change, no `SCHEMA_VERSION` bump, no content-model
  change (Constitution VI). (PASS — FR-011; C8.)
- [x] CHK015 — The summarizer is just another `ModelBoundary`, not a runtime-core
  change (Constitution VIII). (PASS — plan Constitution Check.)
- [x] CHK016 — No secret on the config; a summarizer's credential lives in the
  host model object (Constitution VII). (PASS — FR-009; C9.)
- [x] CHK017 — Threaded through the existing `RuntimeConfig` → `assemble()` →
  `RuntimeController` → `AgentLoop` wiring (the `auto_compact_threshold`
  precedent). (PASS — FR-009.)

## Testability & rollback (Constitution X)

- [x] CHK018 — Deterministic offline tests with a `ScriptedModel` summarizer (no
  live calls). (PASS — FR-013; research.md Decision 6.)
- [x] CHK019 — Rollback is `compaction_summarizer = None` (or revert the overlay +
  wiring) → exact pre-042 behavior. (PASS — Assumptions.)
- [x] CHK020 — Default-off byte-identity keeps the existing loop / compaction /
  assembly tests green. (PASS — FR-002; SC-005.)
