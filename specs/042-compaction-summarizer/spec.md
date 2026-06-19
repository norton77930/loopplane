# Feature Specification: Optional Cheap-Model Compaction Summarizer

**Feature Branch**: `042-compaction-summarizer` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Tier-3 unit, the deferred half of spec 041. Today
compaction produces a mechanical digest (`compact_history` → a
`SummaryMarkerBlock` with turn count + tool names + excerpts). Add an optional
cheap-model summarizer: when a host supplies a (cheap) summarizer model,
compaction uses it to write a better summary; when absent (default), the
mechanical digest is used unchanged. The single most important property:
FAIL-SAFE — a summarizer error/timeout/empty-output must fall back to the
mechanical digest and NEVER break a run. Additive, reuse-first: an additive
default-`None` `RuntimeConfig.compaction_summarizer` (default = today's
mechanical digest, byte-identical), reuse the existing `SummaryMarkerBlock` (NO
content-model/event-schema change), no core-loop rewrite."

## Overview

Spec 041 made the proactive compaction trigger configurable and **deferred** the
cheap-model summarizer to this unit (041 research.md Decision 3). Today
compaction is a pure, synchronous, mechanical transform: `compact_history`
replaces a history prefix with one `SummaryMarkerBlock` whose `SummaryDigest`
carries a turn count, the sorted tool names used, and up to three bounded
excerpts of the earliest user intents. That mechanical digest frees context
space but reads poorly — it is a list of fragments, not a summary.

This unit adds an **optional** cheap-model summarizer. When a host supplies a
(typically cheap) summarizer `ModelBoundary`, the runtime uses it to write a
human-readable summary of the conversation span that compaction dropped, and
places that summary into the **existing** `SummaryMarkerBlock` (it replaces the
mechanical `excerpts`; `turn_count` and `tool_names` stay mechanical). When no
summarizer is supplied (the default), the mechanical digest is produced exactly
as today — **byte-identical**.

The single most important property is **FAIL-SAFE**: the summarizer is a pure
overlay on top of the mechanical digest. The mechanical `compact_history` always
runs first and produces a complete, valid `SummaryMarkerBlock`; the summarizer
then *augments* that marker. If the summarizer raises, times out, signals
context overflow, or returns empty text, the augmentation is skipped and the
**mechanical digest stays** — compaction always succeeds and a run is **never**
broken because the summarizer failed. The summarizer never recurses into
compaction (it is a single, plain model turn with no assembler and no tools).

### The seam (verified against the code — see research.md)

`compact_history` is **synchronous** and is invoked at two sites: proactively
inside the **synchronous** `PromptAssembler.assemble` (spec 041), and reactively
inside the **async** `AgentLoop.run` overflow handler (FR-008). A model call
(`ModelBoundary.stream_turn`) is **async**. Because `assemble` is synchronous and
has exactly one production caller (`AgentLoop._assemble`) plus synchronous test
callers, it **cannot** await a model call without a breaking sync→async change —
which is forbidden.

The summarizer therefore runs as an **additive async overlay at the loop's
existing async seams**, after the mechanical compaction has already produced the
marker: once after assembly (covering the proactive trigger, which the assembler
signals with a one-shot flag) and once in the overflow handler (the reactive
trigger). `compact_history` itself is **unchanged** — it is both the default and
the fail-safe fallback. The agent loop's turn cycle is preserved; the only new
behavior is one additive awaited step that enhances the just-produced marker.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A supplied summarizer writes the compaction summary (Priority: P1)

An embedder supplies a cheap summarizer model (e.g. a small/fast model) as
`RuntimeConfig.compaction_summarizer`. When compaction runs (proactively or
reactively), the runtime asks that model to summarize the dropped conversation
span and stores the model's summary in the `SummaryMarkerBlock`, so subsequent
turns carry a readable summary instead of mechanical fragments.

**Why this priority**: This is the unit's entire value — a model-written summary
in place of the mechanical excerpts.

**Independent Test**: Drive a controller whose model overflows once so compaction
runs, with a `ScriptedModel` configured as the summarizer that emits a known
summary string; assert the resulting `SummaryMarkerBlock`'s digest carries the
scripted summary text (and that the summarizer received the dropped turns).

**Acceptance Scenarios**:

1. **Given** a `compaction_summarizer` is set and a compaction is triggered,
   **When** compaction runs, **Then** the `SummaryMarkerBlock` in history carries
   the **model's** summary text (the scripted summary appears) and keeps the
   mechanical `turn_count` and `tool_names`.
2. **Given** a `compaction_summarizer` is set, **When** it is asked to summarize,
   **Then** it receives a `ModelRequest` whose context contains the **dropped**
   turns (the span being compacted) plus a concise summarize instruction, and no
   tools.

### User Story 2 - No summarizer is byte-identical to today (Priority: P1)

An embedder does not supply a summarizer (`compaction_summarizer` stays `None`,
the default). Compaction then produces the mechanical digest exactly as today —
the same `SummaryMarkerBlock` / `SummaryDigest` with turn count, tool names, and
excerpts. Nothing about the off path differs from the pre-042 behavior.

**Why this priority**: Additivity and reversibility (Constitution X) require the
off path to be provably unchanged, so the summarizer is a pure, safe overlay.

**Independent Test**: With `compaction_summarizer = None`, run a compaction and
assert the produced `SummaryMarkerBlock` equals the one the pre-042 mechanical
path produces (same digest fields, excerpts intact); assert the summarizer is
never consulted.

**Acceptance Scenarios**:

1. **Given** `compaction_summarizer = None`, **When** compaction runs, **Then**
   the mechanical digest is produced unchanged (turn count, tool names,
   excerpts) — byte-identical to today.
2. **Given** `compaction_summarizer = None`, **When** compaction runs, **Then**
   no model call is made for summarization.

### User Story 3 - A failing summarizer falls back to the mechanical digest (Priority: P1)

An embedder supplies a summarizer that errors, hangs (times out), signals context
overflow, or returns empty output. Compaction still succeeds: the mechanical
digest stands and the run continues normally — the summarizer failure is
swallowed and never surfaces as a run failure.

**Why this priority**: **FAIL-SAFE is the non-negotiable property.** A summarizer
is an optional convenience; it must never be able to break a run.

**Independent Test**: With a `compaction_summarizer` that raises (a
`ScriptedFailure`), trigger a compaction and assert (a) the run still terminates
normally, and (b) the `SummaryMarkerBlock` carries the **mechanical** digest
(excerpts present, not the model summary). Repeat for an empty-output summarizer
and a slow (timeout) summarizer.

**Acceptance Scenarios**:

1. **Given** a summarizer that raises an exception, **When** compaction runs,
   **Then** the mechanical `SummaryMarkerBlock` stands and the run completes
   without an `unrecoverable-error` caused by the summarizer.
2. **Given** a summarizer that returns empty text (or only whitespace), **When**
   compaction runs, **Then** the mechanical digest is kept (empty is not a valid
   summary).
3. **Given** a summarizer that does not respond within the guard timeout,
   **When** compaction runs, **Then** the summarize attempt is abandoned and the
   mechanical digest is kept; the run continues.
4. **Given** a summarizer that signals `ContextOverflowError`, **When**
   compaction runs, **Then** it is treated like any failure (mechanical digest
   kept); the summarizer is **never** retried by compacting again (no recursion).

### Edge Cases

- **No compaction occurs** → there is nothing to summarize; the summarizer is
  never consulted (the overlay only runs when `compact_history` produced a
  marker).
- **No assembler attached** (assembly disabled) → there is no proactive path; the
  reactive overflow path still applies, and the summarizer overlay runs there if
  configured. (A summarizer alone does not enable assembly.)
- **Summarizer returns multiple text increments** → they are concatenated in
  order into one summary string.
- **Summarizer emits tool-call increments** → ignored; only `TextIncrement` text
  is collected (the summarizer turn advertises no tools, so a well-behaved model
  emits none; a misbehaving one is simply ignored).
- **Marker already summarized** → the overlay is a one-shot per compaction; it
  only augments a freshly produced mechanical marker, so it never re-summarizes
  an already-summarized one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The runtime MUST support an optional cheap-model summarizer as an
  additive, public-safe `RuntimeConfig.compaction_summarizer: ModelBoundary |
  None` field, defaulting to `None`.
- **FR-002**: When `compaction_summarizer` is `None` (the default), compaction
  MUST produce the existing mechanical digest **unchanged** — the same
  `SummaryMarkerBlock` / `SummaryDigest` (turn count, tool names, excerpts) — so
  the default-off path is **byte-identical** to today, and no model call is made
  for summarization.
- **FR-003**: When `compaction_summarizer` is set and a compaction is triggered,
  the runtime MUST ask the summarizer to summarize the conversation span that
  compaction dropped, and place the resulting summary text into the **existing**
  `SummaryMarkerBlock` (replacing the mechanical `excerpts` of its `SummaryDigest`
  while keeping `turn_count` and `tool_names` mechanical). It MUST NOT add a new
  block type, a new digest field, or any event-schema change.
- **FR-004**: The summarizer MUST receive a `ModelRequest` built from the dropped
  turns plus a concise summarize instruction, and advertising **no tools**. The
  summary is the concatenation of the `TextIncrement` text the summarizer emits.
- **FR-005 (FAIL-SAFE, non-negotiable)**: ANY summarizer failure — an exception,
  a timeout, a `ContextOverflowError`, or empty/whitespace-only output — MUST be
  swallowed and fall back to the **mechanical** digest. Compaction MUST always
  succeed and a run MUST NEVER terminate in error because the summarizer failed.
- **FR-006**: The summarize attempt MUST be bounded by a guard timeout so a slow
  or hung summarizer cannot stall a run; on timeout the mechanical digest is kept
  (FR-005).
- **FR-007**: The summarizer MUST NOT recurse into compaction or the assembler: it
  is a single, plain model turn (no assembler, no tools, no proactive/reactive
  compaction of its own). A `ContextOverflowError` from the summarizer is a
  failure (FR-005), never a trigger to compact-and-retry.
- **FR-008**: `compact_history`'s mechanical path MUST be **unchanged** and remain
  both the default and the fail-safe fallback. The summarizer is an overlay
  applied **after** the mechanical marker is produced; it never replaces the
  mechanical algorithm.
- **FR-009**: The summarizer MUST be threaded through the existing wiring path —
  `RuntimeConfig` → `assemble()` → `RuntimeController` constructor → the
  per-session loop/assembler — the same way `auto_compact_threshold` / `plan_mode`
  are wired. As an object collaborator (like `model`), it passes through
  `RuntimeConfig.from_mapping` unchanged and carries no secret (a summarizer's
  credential lives in the host-supplied model object, never in the config).
- **FR-010**: The change MUST be **additive** and MUST NOT change the agent loop's
  turn-cycle structure (it adds only one awaited overlay step at the two points
  compaction already runs), the runtime event bus, the event schema, the content
  model, the Tool Gateway, or `compact_history`'s output.
- **FR-011**: Compaction (with or without a summarizer) MUST emit **no new runtime
  event** — it mutates in-memory history only, as today. No `SCHEMA_VERSION` bump
  (Constitution VI).
- **FR-012**: The unit MUST add **no new public package or `__all__` name**
  (`compaction_summarizer` is a new field on the existing `RuntimeConfig`;
  `ModelBoundary` is already public; the summarize helper is an internal module
  with no `__all__`), so the unit-014 api-reference bijection stays green with no
  doc edit.
- **FR-013**: The unit MUST be covered by **deterministic offline tests** (no live
  calls) using a `ScriptedModel` (and `ScriptedFailure`) as the summarizer: a set
  summarizer puts its summary into the marker; the summarizer receives the dropped
  turns; `compaction_summarizer = None` is byte-identical (mechanical digest, no
  model call); and — the critical fail-safe case — a raising / empty-output /
  timing-out summarizer falls back to the mechanical digest and the run continues.

### Key Entities

- **`RuntimeConfig.compaction_summarizer: ModelBoundary | None`** — the additive,
  default-`None` optional summarizer model. `None` → today's mechanical digest
  (off, byte-identical). A `ModelBoundary` → compaction asks it to summarize the
  dropped span into the `SummaryMarkerBlock`. An object collaborator (no
  coercion; no secret).
- **The summarize overlay** (`loopplane.loop.summarizer`, internal) — an async
  helper that, given the freshly produced mechanical marker, the dropped span, and
  the summarizer, builds the summarize `ModelRequest`, collects the summary text
  under a timeout guard, and returns a marker with the model summary in its digest
  — or the unchanged mechanical marker on any failure (FAIL-SAFE).
- **`SummaryMarkerBlock` / `SummaryDigest` (reused, unchanged)** — the existing
  compaction block; the model summary goes into `SummaryDigest.excerpts`. No new
  block, no new field.
- **`compact_history` (reused, unchanged)** — the mechanical compaction that
  always runs first; both the default and the fail-safe fallback.

### Out of Scope

- Any change to `compact_history`'s mechanical algorithm, the keep-last policy, or
  the cut-point rules.
- A new block type, a new `SummaryDigest` field, or any event/content-model
  change (the summary reuses `SummaryDigest.excerpts`).
- A per-compaction "summarized" diagnostic/event (compaction is silent today;
  emitting one would be a Constitution VI contract change → a separate spec).
- Making `PromptAssembler.assemble` or `compact_history` async (forbidden — a
  breaking sync→async change; the overlay runs at the loop's existing async seam).
- Live summarizer calls in tests; provider selection or pricing for the
  summarizer (the host picks any `ModelBoundary`).
- Streaming the summary to the event bus, or surfacing summarizer token usage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `compaction_summarizer` set and a compaction triggered, the
  resulting `SummaryMarkerBlock` carries the model's summary text (verified
  offline with a scripted summarizer), with the mechanical `turn_count` /
  `tool_names` preserved.
- **SC-002**: With `compaction_summarizer = None`, the produced
  `SummaryMarkerBlock` is byte-identical to the pre-042 mechanical digest and no
  summarization model call is made (verified offline).
- **SC-003 (FAIL-SAFE)**: With a summarizer that raises, returns empty, or times
  out, compaction still succeeds with the mechanical digest and the run completes
  without a summarizer-caused `unrecoverable-error` (verified offline).
- **SC-004**: The summarizer receives the dropped turns and no tools (verified
  offline by inspecting the request it is handed).
- **SC-005**: The four quality gates stay green, including the unit-014
  api-reference bijection (no new public name) and the existing loop / compaction
  / assembly tests (unchanged).
- **SC-006**: The agent loop's turn-cycle structure, the event schema, the content
  model, the Tool Gateway, and `compact_history`'s output are unchanged (no diff
  outside the summarizer overlay module, the loop's two additive overlay calls,
  the controller/assembler wiring, the host config, and tests/docs).

## Assumptions

- **Reuse over re-implement**: `compact_history` and `SummaryMarkerBlock` /
  `SummaryDigest` are reused unchanged; the summary text lives in the existing
  `excerpts` field (Constitution IX). No new block, no new field.
- **The summarizer is an overlay, not a replacement**: the mechanical marker is
  always produced first and is the fail-safe fallback; the summarizer only
  augments it (FR-008).
- **Default-off is byte-identical**: `compaction_summarizer = None` makes the
  overlay a no-op, so compaction is exactly the pre-042 mechanical transform; the
  existing compaction/assembly tests pass unchanged.
- **FAIL-SAFE above all**: any summarizer failure degrades to the mechanical
  digest; a run is never broken by the summarizer (FR-005). The reactive
  `ContextOverflowError` backstop is unaffected.
- **The sync `assemble` cannot await**: the overlay runs at the loop's async
  seams (after assembly for the proactive trigger; in the overflow handler for the
  reactive trigger), so neither `assemble` nor `compact_history` becomes async
  (research.md).
- **Additive, reversible**: setting `compaction_summarizer = None` (or reverting
  the overlay + wiring additions) restores the exact pre-042 behavior
  (Constitution X rollback).
