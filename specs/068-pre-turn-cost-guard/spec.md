# Feature Specification: Pre-Turn Cost Guard

**Feature Branch**: `068-pre-turn-cost-guard`

**Created**: 2026-06-22

**Status**: Draft - P2 (review backlog batch 064-072, unit 5/9; ADR 0014 pre-settled)

**Input**: User description: "P2 ADR 0005 extension: pre-turn predictive cost guard - estimate a turn's USD at assemble time (request tokens x input rate + configured max-output estimate) and refuse a likely-overage turn BEFORE the model call. Additive, fail-open, default-off; reuses `budget-exceeded` (no new reason/SCHEMA bump). ADR 0014 settled: add pre-turn estimate."

## Boundary Note

055 enforces USD caps only after a model turn finishes, because actual token usage is known only on
turn completion. That keeps accounting honest, but a single expensive turn can still exceed a cap
before the post-turn checker can react. This unit adds an opt-in pre-turn estimate before each model
call: estimate the already-assembled request's input cost plus a host-configured maximum output cost,
compare it with the remaining configured USD budget, and refuse a turn that is likely to exceed the
cap before calling the model.

This is an extension of the 055/ADR 0005 budget model, not a replacement. The post-turn actual-cost
checker remains authoritative after any allowed model call. The pre-turn guard is default-off and
fail-open: if pricing, token estimation, the max-output estimate, or remaining-budget state is
unavailable, the model call proceeds and the existing post-turn budget enforcement remains the
fallback. A refusal reuses the existing `budget-exceeded` termination reason and does not change the
event schema version.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refuse an obviously over-budget turn before the model call (Priority: P1)

A host has configured USD budget caps and pricing. Before a turn is sent to the model, the runtime
estimates the turn's worst expected cost from the assembled request plus the configured output
estimate. If that estimate would exceed the remaining budget, the run terminates with
`budget-exceeded` without making the model call.

**Why this priority**: This closes the main gap left by 055: avoiding a predictable single-turn
overage when enough information is available before the model call.

**Independent Test**: configure pricing, a budget cap, and an output estimate; drive a run whose
pre-turn estimate exceeds the remaining cap; verify the model is not called and the run terminates
with `budget-exceeded`.

**Acceptance Scenarios**:

1. **Given** pricing, a USD cap, and an output estimate that make the next turn likely to exceed the
   remaining cap, **When** the turn is assembled, **Then** the model is not called and the run
   terminates with `budget-exceeded`.
2. **Given** the same configuration but an estimate within the remaining cap, **When** the turn is
   assembled, **Then** the model call proceeds and normal post-turn budget accounting remains active.

---

### User Story 2 - Missing estimate inputs never block a run (Priority: P1)

If the guard cannot make a complete estimate, it allows the turn to proceed. This includes missing
pricing, an unpriced model, no configured output estimate, unavailable request-token estimate, or no
active USD cap. The runtime may emit a public-safe diagnostic, but it must not crash or deny based on
a guess.

**Why this priority**: Cost safety must not become a false-positive availability risk. The board
requires fail-open behavior for this feature.

**Independent Test**: omit each required estimate input one at a time and verify the model is called;
the existing post-turn checker still handles actual overages when it has enough information.

**Acceptance Scenarios**:

1. **Given** a cap but no usable pre-turn estimate, **When** a run is driven, **Then** the model call
   proceeds and the run does not fail solely because the estimate is unavailable.
2. **Given** an unpriced model, **When** a pre-turn check would otherwise be attempted, **Then** the
   guard skips pre-turn denial and surfaces only a public-safe diagnostic if diagnostics are emitted.

---

### User Story 3 - Preserve existing budget and event contracts (Priority: P2)

The pre-turn guard uses the same public budget outcome as 055: `budget-exceeded`. It does not add a
new termination reason, does not bump the event schema, and does not weaken actual post-turn budget
accounting for allowed turns.

**Why this priority**: 055 already established the budget contract and consumer handling. 068 should
extend that contract without another schema or vocabulary change.

**Independent Test**: run event serialization and consumer coverage for a pre-turn refusal; verify
the termination reason is the existing `budget-exceeded` value and existing post-turn budget tests
still pass.

**Acceptance Scenarios**:

1. **Given** a pre-turn refusal, **When** events are emitted and replayed, **Then** the terminal
   reason is `budget-exceeded` and the event schema version is unchanged.
2. **Given** a turn allowed by the pre-turn estimate, **When** actual post-turn usage later crosses a
   cap, **Then** the existing post-turn `budget-exceeded` behavior still terminates the run.

---

### User Story 4 - Default-off behavior stays byte-identical (Priority: P3)

With no pre-turn cost guard configured, the runtime behavior and event stream stay exactly as they
were after 067.

**Why this priority**: The feature is an opt-in safety layer. Hosts that do not choose a pre-turn
estimate must not inherit behavior changes.

**Independent Test**: run the existing no-budget and post-turn budget flows without the new guard
configuration and verify no new behavior, events, diagnostics, or model-call skips occur.

**Acceptance Scenarios**:

1. **Given** the default runtime configuration, **When** a run executes, **Then** the model is called
   exactly as before and no pre-turn budget decision is made.
2. **Given** existing post-turn budget caps without a pre-turn estimate configured, **When** a run
   executes, **Then** 055 behavior remains unchanged.

### Edge Cases

- **Estimate exactly equals remaining budget**: allow the model call; actual post-turn accounting
  remains authoritative if the real cost later exceeds the cap.
- **Estimate exceeds one configured cap but not another**: refuse if any active known cap would be
  exceeded by the estimated next turn.
- **No active cap**: do not estimate for denial; proceed exactly as today.
- **Unpriced model or missing rates**: fail-open; no guessed or zero-masked price.
- **Unavailable request-token estimate**: fail-open; do not deny based on incomplete data.
- **Configured output estimate is zero**: valid but host-owned; estimate only the input side and let
  post-turn accounting catch actual output cost.
- **Pre-turn refusal before assistant output**: keep history, checkpoint rebuild, and replay
  semantics consistent; do not mislabel the refusal as `cancelled`.
- **Public safety**: diagnostics must not include prompts, private paths, credentials, principals,
  raw prices, or cap amounts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support an opt-in pre-turn cost guard that evaluates before a model
  call and is inactive by default.
- **FR-002**: When active, the guard MUST estimate the next turn's USD cost from the assembled
  request's input-token estimate and a host-configured maximum-output-token estimate using the
  host-supplied pricing rates.
- **FR-003**: If the estimated next-turn cost would exceed any known remaining active USD cap, the
  system MUST refuse the turn before the model call and terminate the run with `budget-exceeded`.
- **FR-004**: The guard MUST be fail-open when it cannot make a complete estimate, including missing
  pricing, an unpriced model, unavailable request-token estimate, missing output estimate, or no
  active cap.
- **FR-005**: The guard MUST NOT replace post-turn actual-cost accounting; every allowed model call
  remains subject to the existing post-turn budget checker.
- **FR-006**: The feature MUST reuse the existing `budget-exceeded` termination reason; it MUST NOT
  add a new termination reason and MUST NOT change the event schema version.
- **FR-007**: Default behavior MUST be byte-identical when the guard is not configured: no pre-turn
  estimate, denial, diagnostic, or event change.
- **FR-008**: A pre-turn refusal MUST keep history, checkpoint, replay, and UI-visible termination
  semantics consistent; it MUST NOT strand user input or reuse `cancelled`.
- **FR-009**: Any diagnostic emitted for skipped pre-turn enforcement MUST be public-safe and generic,
  with no prompt text, private paths, credentials, raw prices, cap amounts, or principal identifiers.
- **FR-010**: The feature MUST be additive to the existing budget and pricing contracts and recorded
  under the pre-settled ADR 0014 decision during planning.

### Key Entities *(include if feature involves data)*

- **Pre-turn cost estimate**: the predicted USD cost for one upcoming model call, derived from input
  token estimate plus configured maximum output estimate.
- **Maximum output estimate**: a host-chosen token count used only for pre-turn prediction; absent by
  default.
- **Remaining budget view**: the known remaining amount for each active USD cap before the next model
  call.
- **Pre-turn budget decision**: an allow or refuse outcome; refusal maps to `budget-exceeded`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of covered over-budget pre-turn scenarios, the model call count is zero and the
  run terminates with `budget-exceeded`.
- **SC-002**: In 100% of covered under-estimate scenarios, the model call proceeds and existing
  post-turn budget accounting still terminates if actual usage later crosses a cap.
- **SC-003**: In 100% of covered incomplete-estimate scenarios, the guard fails open: no crash, no
  pre-turn refusal, and no guessed price.
- **SC-004**: With the guard unset, existing default-off and post-turn budget tests remain unchanged;
  no event schema version changes.
- **SC-005**: Public-safety scans find no prompt text, private paths, internal names, credentials,
  raw prices, cap amounts, or principal identifiers in new diagnostics or docs.

## Assumptions

- "At assemble time" means after the request has been composed for the model but before the model
  call begins.
- The host supplies pricing and the maximum output estimate; LoopPlane does not bundle prices,
  fetch prices, or infer provider-specific maximum output behavior.
- The request-token value may be an estimate, but the guard must not deny unless the estimate inputs
  are complete enough to compute a concrete USD prediction.
- Existing post-turn budget accounting remains the source of truth for actual spend after the model
  returns usage.
- Durable monthly-budget behavior is not expanded by this unit; any unavailable durable ledger state
  stays fail-open under the existing monthly-budget rules.
- ADR 0014 is pre-settled by the board for "add pre-turn estimate"; the plan step records the
  boundary decision and rollback strategy.
