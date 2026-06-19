# Feature Specification: Configurable Proactive Auto-Compaction

**Feature Branch**: `041-auto-compaction` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Tier-3 efficiency unit. LoopPlane compacts history
only reactively (on a model `ContextOverflowError`, compact-and-retry once). Add
proactive, configurable, threshold-based auto-compaction: compact *before* the
limit when the assembled context grows past a configurable fraction of the
model's capacity. Additive, reuse-first; default off = today's behavior
byte-identical. Reuse `compact_history` unchanged (only the proactive trigger is
new); reuse the existing size estimate if one exists. The cheap-model summarizer
is secondary — defer it unless cleanly additive. No core-loop rewrite, no
event-schema or content-model change."

## Overview

LoopPlane's prompt assembler already runs a **proactive** pre-send compaction
check today: in `PromptAssembler.assemble`, after composing the request it
estimates the assembled context's token count (`_estimate_tokens`, a
`chars ÷ 4` heuristic with a fixed per-non-text-block cost) and, when that
estimate exceeds the model's **full** `context_capacity()`, it runs the existing
mechanical `compact_history` once and rebuilds. The loop additionally keeps a
**reactive** backstop: when the model raises `ContextOverflowError` despite that,
the loop compacts and retries exactly once before surfacing the failure (FR-008).

The single limitation: the proactive check fires only at **100% of capacity** —
the same point the model is about to reject the request. There is no way to
compact **earlier**, at a safety-margin fraction of capacity, to avoid ever
reaching the overflow at all.

This unit makes that existing proactive trigger **configurable**: an additive,
default-`None` `RuntimeConfig.auto_compact_threshold: float | None`. When `None`
(the default), the assembler behaves **exactly** as today — the pre-send check
compares against the full capacity, so the default-off path is byte-identical.
When set to a fraction `f` in `(0, 1]`, the pre-send check compares the estimate
against `f * context_capacity()` instead, so the mechanical compaction runs once
*before* the context reaches the model's limit. The reactive
`ContextOverflowError` path is unchanged and remains the backstop.

It **reuses** `compact_history` verbatim (no new compaction algorithm; the
`SummaryMarkerBlock` / `SummaryDigest` output is unchanged) and **reuses** the
existing `_estimate_tokens` size heuristic. It is **transparent to the loop and
the event stream**: compaction emits no runtime event today (it mutates history
only; the durable stream keeps the originals via `replace_prefix`), and the
proactive path emits none either — so there is **no event-schema change, no
`SCHEMA_VERSION` bump, no content-model change**. The threshold is threaded
through the same wiring path as `plan_mode` / `allow_network`
(`RuntimeConfig` → `assemble()` → `RuntimeController` → `PromptAssembler`).

The **cheap-model summarizer** (an optional second `ModelBoundary` used only to
summarize during compaction) is **deferred** to a documented follow-on (spec
042): folding a model call into the loop's compaction path adds real complexity
and risk (error handling, latency, a second model dependency, new tests) for a
secondary benefit, and the mechanical digest already frees space. See
research.md Decision 3.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Proactive compaction at a configured threshold (Priority: P1)

An embedder sets `auto_compact_threshold = 0.8`. As a conversation grows, once
the assembled context's estimated size reaches 80% of the model's capacity, the
runtime compacts history **before** the next turn is sent — so the model receives
an already-compacted request and the overflow is avoided entirely.

**Why this priority**: This is the unit's entire value — compacting on a safety
margin instead of waiting for the model to reject the request.

**Independent Test**: Drive a controller whose model has a small capacity with a
threshold set, grow the history past `threshold * capacity` (estimated), and
assert the request the model received on the triggering turn was already
compacted (its assembled context carries a `SummaryMarkerBlock` and is smaller
than the un-compacted context would have been) — with **no** `ContextOverflowError`
raised by the model.

**Acceptance Scenarios**:

1. **Given** `auto_compact_threshold = 0.8` and a history whose estimated size is
   `≥ 0.8 * capacity` but `< capacity`, **When** the next turn is assembled,
   **Then** `compact_history` runs before the model call and the assembled
   request carries a `SummaryMarkerBlock`.
2. **Given** the same threshold and a history whose estimated size is
   `< 0.8 * capacity`, **When** the next turn is assembled, **Then** no proactive
   compaction runs and the request carries no `SummaryMarkerBlock`.
3. **Given** a threshold is set, **When** proactive compaction runs, **Then** the
   existing mechanical digest is produced (turn count, tool names, bounded
   excerpts) — identical to the reactive path's output (no new algorithm).

### User Story 2 - Default off is byte-identical to today (Priority: P1)

An embedder does not set `auto_compact_threshold` (it stays `None`). The
assembler's proactive check then compares against the **full** capacity, exactly
as it does today — the same trigger point, the same behavior. No earlier
compaction happens.

**Why this priority**: Additivity and reversibility (Constitution X) require the
off path to be provably unchanged, so the threshold is a pure, safe overlay.

**Independent Test**: With `auto_compact_threshold = None`, assemble a request
whose estimate is below the full capacity and assert it equals the request the
pre-threshold assembler produced (no compaction). Assemble one whose estimate
exceeds the full capacity and assert it still compacts once (today's behavior).

**Acceptance Scenarios**:

1. **Given** `auto_compact_threshold = None` and an estimate `< capacity`,
   **When** a turn is assembled, **Then** no proactive compaction runs (identical
   to today).
2. **Given** `auto_compact_threshold = None` and an estimate `> capacity`,
   **When** a turn is assembled, **Then** the existing full-capacity proactive
   compaction still runs once (the pre-threshold behavior is preserved).

### User Story 3 - The reactive overflow backstop still works (Priority: P1)

Regardless of the threshold (or its absence), if the model still raises
`ContextOverflowError` on a turn, the loop compacts and retries exactly once
before surfacing the failure — the existing FR-008 backstop is untouched.

**Why this priority**: Proactive compaction is a safety margin, not a guarantee
(the estimate is approximate); the reactive path must remain the backstop so a
real overflow is still handled.

**Independent Test**: With a threshold set, script the model to overflow on a
turn and assert the existing compact-and-retry-once behavior is unchanged (one
retry → success; a second overflow → `unrecoverable-error`).

**Acceptance Scenarios**:

1. **Given** any `auto_compact_threshold` value (incl. `None`), **When** the
   model raises `ContextOverflowError`, **Then** the loop compacts and retries
   exactly once (the existing backstop).
2. **Given** the model overflows twice, **When** the loop has already retried
   once, **Then** the run terminates `unrecoverable-error` (unchanged).

### Edge Cases

- **Threshold `None` (default)** → the pre-send check uses the full capacity →
  byte-identical to today (US2).
- **Threshold `1.0`** → the pre-send check uses `1.0 * capacity = capacity` →
  the same trigger point as today (`> capacity`), so `1.0` is equivalent to the
  default behavior (the threshold is the full window).
- **Threshold near 0 (e.g. `0.01`)** → the effective capacity is tiny, so a
  proactive compaction fires aggressively. This is the host's choice; compaction
  is bounded (`compact_history` returns `False` when there is nothing worth
  compacting, so no infinite loop and no error).
- **Nothing worth compacting** → `compact_history` returns `False`; the assembler
  sends the (un-compacted) request anyway and the reactive backstop still
  applies if the model rejects it (today's behavior on the full-capacity path).
- **Invalid threshold (`≤ 0`, `> 1`, or `NaN`)** → rejected fast at config
  assembly with a public-safe `ConfigError` (fail-fast, FR-005), never silently
  ignored.
- **No assembler attached** (assembly disabled) → there is no proactive path at
  all (the bare loop has no assembler); the threshold is inert. (Setting a
  threshold does not by itself enable assembly; the proactive path requires the
  assembler, exactly like the existing full-capacity check.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The runtime MUST support a configurable proactive auto-compaction
  threshold as an additive, public-safe `RuntimeConfig.auto_compact_threshold:
  float | None` field, defaulting to `None`.
- **FR-002**: When `auto_compact_threshold` is `None`, the assembled context's
  proactive pre-send compaction check MUST compare the estimated size against the
  model's **full** `context_capacity()` — i.e. the existing behavior — so the
  default-off path is **byte-identical** to today (no earlier compaction).
- **FR-003**: When `auto_compact_threshold` is a value `f` in `(0, 1]`, the
  proactive pre-send check MUST compare the estimated size against
  `f * context_capacity()`, running the **existing** `compact_history` once
  before the model call when the estimate reaches that effective capacity.
- **FR-004**: Proactive compaction MUST reuse `compact_history` **unchanged** —
  the same mechanical `SummaryMarkerBlock` / `SummaryDigest` output as the
  reactive path. The unit MUST NOT add a new compaction algorithm or change the
  digest output.
- **FR-005**: An invalid `auto_compact_threshold` (`≤ 0`, `> 1`, or not a finite
  number) MUST be rejected at config assembly with a public-safe `ConfigError`
  (fail-fast), never silently ignored.
- **FR-006**: The size estimate MUST reuse the existing `_estimate_tokens`
  heuristic in `PromptAssembler` (sum of text-block character lengths plus a
  fixed per-non-text-block cost, divided by a chars-per-token constant). No new
  tokenizer or dependency is introduced.
- **FR-007**: The reactive `ContextOverflowError` compact-and-retry-once backstop
  in the loop MUST be unchanged and remain in force regardless of the threshold.
- **FR-008**: The threshold MUST be threaded through the existing wiring path —
  `RuntimeConfig` → `assemble()` → `RuntimeController` constructor → the
  per-session `PromptAssembler` — the same way `plan_mode` / `allow_network` are
  wired. It MUST be coerced in `RuntimeConfig.from_mapping` and carry no secret.
- **FR-009**: The change MUST be **additive** and confined to: the assembler's
  proactive sizing, the controller's assembler construction, and the host config
  wiring/validation. It MUST NOT change the agent loop's turn cycle, the runtime
  event bus, the event schema, the content model, the Tool Gateway, or
  `compact_history`'s output.
- **FR-010**: Compaction (proactive or reactive) MUST emit **no new runtime
  event** — today it mutates history only and emits nothing; the proactive path
  emits nothing either. No `SCHEMA_VERSION` bump (Constitution VI).
- **FR-011**: The unit MUST add **no new public package or `__all__` name** (the
  threshold is a new field on the existing `RuntimeConfig`; the assembler/
  controller gain only constructor parameters, no new exported symbol), so the
  unit-014 api-reference bijection stays green with no doc edit.
- **FR-012**: The cheap-model summarizer (an optional summarizer `ModelBoundary`
  used during compaction) is **out of scope** for this unit and MUST be deferred
  to a documented follow-on (spec 042). This unit ships only the configurable
  threshold over the mechanical digest.
- **FR-013**: The unit MUST be covered by **deterministic offline tests** (no
  live calls): proactive compaction at/over/under the threshold; default-off
  byte-identity (off == today, including the preserved full-capacity trigger);
  the reactive backstop unchanged; the effective-capacity computation; and an
  invalid threshold rejected fast.

### Key Entities

- **`RuntimeConfig.auto_compact_threshold: float | None`** — the additive,
  default-`None` proactive-compaction threshold (a fraction of the model's
  context capacity). `None` → the existing full-capacity proactive check (off).
  A value in `(0, 1]` → compact proactively at `value * capacity`.
- **`PromptAssembler` `compact_threshold` parameter** — the constructor parameter
  carrying the threshold into the assembler; it gates the new
  `_effective_capacity(capacity)` used by the existing proactive check. `None`
  preserves today's `> capacity` comparison exactly.
- **`compact_history` (reused, unchanged)** — the mechanical compaction the
  proactive path invokes; the digest output is identical to the reactive path's.
- **`_estimate_tokens` (reused, unchanged)** — the existing size heuristic the
  proactive check uses.

### Out of Scope

- The **cheap-model summarizer** (a summarizer `ModelBoundary` for compaction) —
  deferred to spec 042 (research.md Decision 3).
- Any new compaction algorithm, any change to the `SummaryMarkerBlock` /
  `SummaryDigest` digest, or a different keep-last policy.
- An exact tokenizer or a per-provider token count — the heuristic is a
  safety-margin trigger, not an exact budget (research.md Decision 2).
- Any new event, content block, or `TokenUsage` field; any change to the loop's
  turn cycle, the runtime core, the Tool Gateway, or the Event Bus.
- A per-turn "compacted" diagnostic/event (compaction is silent today; emitting
  one would be a VI contract change → a separate spec if ever wanted).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `auto_compact_threshold = f` and an estimated context size
  `≥ f * capacity` (and `< capacity`), the assembled request sent to the model
  carries a `SummaryMarkerBlock` and no `ContextOverflowError` is raised
  (verified offline).
- **SC-002**: With `auto_compact_threshold = None`, the assembler's proactive
  behavior is byte-identical to today — no compaction below the full capacity, and
  the existing full-capacity compaction still fires above it (verified offline by
  comparison).
- **SC-003**: The reactive `ContextOverflowError` compact-and-retry-once backstop
  behaves identically with or without a threshold (verified offline).
- **SC-004**: An invalid threshold (`0`, negative, `> 1`, `NaN`) is rejected at
  config assembly with `ConfigError` (verified offline).
- **SC-005**: The four quality gates stay green, including the unit-014
  api-reference bijection (no new public name) and the existing loop/compaction/
  assembly tests (unchanged).
- **SC-006**: The agent loop's turn cycle, the event schema, the content model,
  the Tool Gateway, and `compact_history`'s output are unchanged (no diff outside
  the assembler sizing, the controller wiring, the host config, and tests/docs).

## Assumptions

- **Reuse over re-implement**: the proactive trigger already exists in
  `PromptAssembler.assemble`; this unit only makes its threshold configurable.
  `compact_history` and `_estimate_tokens` are reused unchanged (Constitution IX).
- **Default-off is byte-identical**: `auto_compact_threshold = None` maps the
  effective capacity to the full capacity, so the pre-send check is the exact
  `> capacity` comparison shipped today; the existing assembly/compaction tests
  pass unchanged.
- **The estimate is a safety margin, not a budget**: the `chars ÷ 4` heuristic is
  approximate; the reactive `ContextOverflowError` path remains the backstop for
  any case the estimate under-counts (research.md Decision 2).
- **Compaction is silent**: it mutates in-memory history and the durable stream
  keeps the originals; no event is emitted today and none is added (Constitution
  VI; FR-010).
- **Additive, reversible**: setting `auto_compact_threshold = None` (or reverting
  the assembler/controller/config additions) restores the exact pre-threshold
  behavior (Constitution X rollback).
