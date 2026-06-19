# Requirements Quality Checklist — 041 Configurable Auto-Compaction

Purpose: verify the spec is complete, unambiguous, additive, and constitution-
aligned before planning. Each item is PASS/FAIL against `spec.md`.

## Completeness

- [x] CHK001 — Every functional requirement (FR-001…FR-013) is testable offline. (PASS — threshold trigger, byte-identity, the reactive backstop, the effective-capacity math, and the invalid-threshold rejection are all assertable with the scripted model + a controller, no live calls.)
- [x] CHK002 — Success criteria are measurable and tied to FRs. (PASS — SC-001..SC-006.)
- [x] CHK003 — Edge cases are enumerated (threshold None / 1.0 / near-0, nothing-to-compact, invalid threshold, no assembler). (PASS.)

## Clarity / Unambiguity

- [x] CHK004 — The trigger is defined concretely: estimate `≥ threshold * capacity`, compared in the **existing** pre-send check; `None` → full capacity. (PASS — FR-002/FR-003.)
- [x] CHK005 — "Reuse `compact_history` unchanged" is explicit (same digest, no new algorithm). (PASS — FR-004.)
- [x] CHK006 — The default-off byte-identity guarantee is explicit and its mechanism stated (None → effective capacity == full capacity == today's `> capacity`). (PASS — FR-002, Assumptions.)

## Additivity / Boundaries (Constitution III/IV/VI)

- [x] CHK007 — No change to the agent loop's turn cycle, runtime core, Tool Gateway, or Event Bus. (PASS — FR-009.)
- [x] CHK008 — No event-schema, content-model, or `TokenUsage`-shape change; compaction stays silent (no new event). (PASS — FR-009/FR-010.)
- [x] CHK009 — The change is confined to the assembler sizing + the controller's assembler construction + the host config wiring/validation + tests/docs. (PASS — FR-009.)
- [x] CHK010 — `compact_history`'s output is unchanged, so the existing compaction/assembly/loop tests stay green. (PASS — FR-004; SC-005/SC-006.)

## Reuse-first (Constitution IX)

- [x] CHK011 — The proactive trigger reuses the existing `assemble`-time check; only its threshold is new. (PASS — Overview, FR-003.)
- [x] CHK012 — The size estimate reuses the existing `_estimate_tokens` heuristic; no new tokenizer/dependency. (PASS — FR-006.)

## Public surface / Packaging (unit 014)

- [x] CHK013 — No new public package or `__all__` name → the api-reference bijection stays green with no doc edit. (PASS — FR-011; the toggle is a field on `RuntimeConfig`, the assembler/controller gain only constructor parameters.)

## Scope discipline

- [x] CHK014 — The cheap-model summarizer is explicitly deferred to a documented follow-on (spec 042), not forced in. (PASS — FR-012; research.md Decision 3.)

## Testability / Rollback (Constitution X)

- [x] CHK015 — Deterministic offline coverage for the threshold trigger (at/over/under), default-off byte-identity, the reactive backstop, and the invalid-threshold rejection; no live check needed. (PASS — FR-013.)
- [x] CHK016 — Rollback is `auto_compact_threshold = None` (or revert the assembler/controller/config additions) → exact pre-threshold behavior. (PASS — Assumptions.)

## Public-safety (Constitution VII)

- [x] CHK017 — No secrets, internal paths, or private names introduced (the threshold is a float; the wiring is a constructor parameter). (PASS.)
