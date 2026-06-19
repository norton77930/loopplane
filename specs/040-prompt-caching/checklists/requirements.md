# Requirements Quality Checklist — 040 Prompt Caching

Purpose: verify the spec is complete, unambiguous, additive, and constitution-
aligned before planning. Each item is PASS/FAIL against `spec.md`.

## Completeness

- [x] CHK001 — Every functional requirement (FR-001…FR-010) is testable offline. (PASS — breakpoint placement, byte-identity, and the OpenAI mapping are all assertable on assembled dicts / a stub chunk.)
- [x] CHK002 — Success criteria are measurable and tied to FRs. (PASS — SC-001..SC-005.)
- [x] CHK003 — Edge cases are enumerated (no tools, single message, empty content, below cacheable minimum, caching off). (PASS.)

## Clarity / Unambiguity

- [x] CHK004 — "Stable prefix" is defined concretely: tools block + the first message; the rolling last message is explicitly excluded. (PASS — FR-001/FR-002/FR-003.)
- [x] CHK005 — The 4-breakpoint maximum is stated and the placement never exceeds it (≤2 here). (PASS — FR-003.)
- [x] CHK006 — The default on/off decision is stated with rationale, and the byte-identity guarantee for the off path is explicit. (PASS — Assumptions + FR-004.)

## Additivity / Boundaries (Constitution IV/V/VI/VIII)

- [x] CHK007 — No change to the loop, runtime core, Tool Gateway, or Event Bus. (PASS — FR-005.)
- [x] CHK008 — No event-schema, content-model, or `TokenUsage`-shape change. (PASS — FR-005/FR-008; caching is observed via the existing `cached_tokens`.)
- [x] CHK009 — The change is confined to the Anthropic adapter package + tests + docs. (PASS — FR-005.)
- [x] CHK010 — The existing `build_messages` / `build_tools` outputs stay byte-identical (breakpoints applied by a separate opt-in step), so unit-020 mapping tests are untouched. (PASS — FR-006.)

## Reuse-first (Constitution IX)

- [x] CHK011 — Breakpoints are a pure overlay on existing mapping output; the stream decoder + usage mapping are reused unchanged. (PASS — Assumptions; FR-001/FR-002.)
- [x] CHK012 — OpenAI requires no request change; `cached_tokens` is already mapped. (PASS — FR-007.)

## Public surface / Packaging (unit 014)

- [x] CHK013 — No new public package or `__all__` name → the api-reference bijection stays green with no doc edit. (PASS — FR-010; the toggle is a field on `AnthropicConfig`, the helper is a non-exported module function.)

## Testability / Rollback (Constitution X)

- [x] CHK014 — Deterministic offline coverage for ON placement, OFF byte-identity, and the OpenAI mapping; any live check is opt-in. (PASS — FR-009.)
- [x] CHK015 — Rollback is `prompt_caching=False` (or revert the helper + the one adapter call) → exact pre-caching behavior. (PASS — Assumptions.)

## Public-safety (Constitution VII)

- [x] CHK016 — No secrets, internal paths, or private names introduced (the toggle is a bool; `cache_control` is a public API constant). (PASS.)
