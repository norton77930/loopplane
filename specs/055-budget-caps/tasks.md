# Tasks: USD Budget Caps (In-Loop Enforcement)

**Feature**: 055-budget-caps | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0005](../../docs/adr/0005-usd-budget-enforcement.md)

**Scope**: cross-cutting but additive + default-off — a new `loopplane.budget` module (the checker)
+ one additive `TerminationReason` member + an optional `AgentLoop` collaborator + controller/config
wiring + a consumer audit + tests. Byte-identical when no caps set. Reuses 053 `PricingTable.cost`.
Per ADR 0005. **No SCHEMA_VERSION bump; no Phase C (durable ledger).**

**Tests**: requested (TDD-friendly).

## Phase 1: Event vocabulary + config (Foundational)

- [ ] T001 Add `"budget-exceeded"` to the `TerminationReason` Literal in
  `src/loopplane/events/envelope.py:194` (additive; **no SCHEMA_VERSION bump**). Update the
  runtime-events contract doc (specs/011 `contracts/runtime-events.md`) to list the new reason.
- [ ] T002 Add `RuntimeConfig.per_message_usd` + `per_session_usd` (`Decimal | None = None`) to
  `src/loopplane/host/config.py` (coerce in `from_mapping`, validate non-negative Decimal in
  `validate_config`; no secret). Default None = off.

## Phase 2: The budget checker (P1) 🎯

- [ ] T003 Create `src/loopplane/budget.py` (a NEW module — keep 053's `loopplane.pricing` pure +
  unwired): a `BudgetChecker` that holds the caps + a `PricingTable` + the model-id + the prior
  per-session spend, with `record_turn(usage: TokenUsage)` (add this turn's USD via
  `PricingTable.cost`; on `None` → mark unpriced, do not accumulate) + `exceeded() -> bool`
  (per-message OR per-session total crossed) + a `spent` Decimal + an `unpriced` flag (for the
  fail-soft diagnostic). Pure + offline-testable. It imports `loopplane.pricing` +
  `loopplane.model` (NOT `loopplane.tools` — the loop boundary audit stays green).

## Phase 3: In-loop enforcement (P1)

- [ ] T004 [loop] Thread an optional `budget_checker: BudgetChecker | None = None` into
  `AgentLoop.__init__` (the assembler/hooks/summarizer default-None collaborator pattern). In the
  turn cycle: where `TurnEnd.usage` is handled (`loop.py` `_stream_model_turn` ~296-298) feed it to
  the checker; after `turns_completed += 1` (~197), if the checker is set and `exceeded()`, emit a
  `diagnostic` (warning) for an unpriced turn if applicable, then
  `self._emitter.run_terminated("budget-exceeded", turns_completed)` and `return` — retaining the
  just-finished turn's output (mirror the turn-budget guard at `loop.py:135-138`). The off-path
  (checker None) is byte-identical.

## Phase 4: Controller / host wiring (P1)

- [ ] T005 [controller] Build the `BudgetChecker` in `RuntimeController._assemble` from the caps
  (`per_message_usd`/`per_session_usd`) + a host-supplied `PricingTable` + model-id (additive
  optional `RuntimeController` kwargs, mirroring the 048-054 optional-injection pattern); thread it
  into the `AgentLoop`. Carry per-session spend on `_Session` (fold the run's `spent` back after a
  run); the per-session counter resets on `resume()` (documented). Only build the checker when caps
  are configured → default-off byte-identical.

## Phase 5: Consumer audit + tests (P2/P3)

- [ ] T006 Audit every `TerminationReason` consumer for the new `budget-exceeded` value and fix any
  that would mishandle it: `cli/render.py` (reason rendering — should be reason-agnostic),
  `checkpoint/rebuild.py` (MUST NOT strand the user input — verify it only special-cases
  `cancelled`, so `budget-exceeded` is safe), `webapi` run-terminated handling, `apps/web`
  (frontend run-terminated). Add the new reason where an exhaustive match exists.
- [ ] T007 Write `tests/unit/test_budget_caps.py` (offline, a scripted model emitting `TokenUsage`
  + a `PricingTable`): cap crossed → terminate `budget-exceeded` (crossing turn's output retained);
  under-cap → `natural-completion`; per-session cumulative cap; default-off byte-identity (no caps →
  no accounting/events); unpriced model → fail-soft (no terminate + a warning diagnostic); the
  reason is `budget-exceeded` (NOT `cancelled`); the checker unit-tested directly. Add/extend an
  events test asserting `budget-exceeded` serializes/round-trips with `SCHEMA_VERSION` unchanged.

## Phase 6: Polish & Cross-Cutting

- [ ] T008 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof + default-off byte-identity). ALSO confirm: the structural
  audits (`test_no_execution_path_outside_the_gateway` [loop must not import `loopplane.tools`],
  `test_public_safety`) and the events serialize/`SCHEMA_VERSION` tests stay green (additive, no
  bump). Export any new public name (`BudgetChecker`?) + api-reference if needed.

## Dependencies

- T001, T002 → block. T003 → T004 → T005. T001/T004 → T006, T007. All → T008 (gates last).

## Implementation strategy

- Cross-cutting (events + a new module + loop + controller + config + a consumer audit) — a fork
  subagent MAY do it (mirror 048-054); then the four gates + the structural audits + the events
  schema tests + an adversarial verify (default-off byte-identity, in-loop correctness +
  stop-after-overage, the reason-not-cancelled + no-SCHEMA-bump + consumer-audit, fail-soft,
  public-safety) run before commit — Workflow if available, else MANUAL (the API session limit).
  Commit only on a clean review / GO.
- All additive + default-off; per ADR 0005; no Phase C.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
