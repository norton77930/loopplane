# Tasks: Per-User-Monthly USD Cap

**Feature**: 063-monthly-budget | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0010](../../docs/adr/0010-usd-ledger-monthly-budget.md)

**Scope**: additive — extend 055's `BudgetChecker` with an optional monthly dimension backed by 062's
`UsdLedger`; `record_turn` → async; reuse the existing `budget-exceeded` reason; fail-open; thread
principal_id on create + resume; default-off byte-identical. Per ADR 0010 (all forks settled).

**Tests**: requested.

## Phase 1: BudgetChecker monthly dimension (P1) 🎯

- [x] T001 In `src/loopplane/budget/__init__.py`: add the optional monthly dimension to
  `BudgetChecker` — `ledger: UsdLedger | None = None`, `principal_id: str | None = None`, `clock:
  Callable[[], datetime] = (default a UTC now)`, `per_user_monthly_usd: Decimal | None = None` + an
  internal `_monthly_total: Decimal`. Make `record_turn` **async**: compute the (priced) cost as
  today; if the monthly dim is configured + cost is not None, `await ledger.add(principal_id,
  self._month(), cost)` and store the returned total in `_monthly_total` — wrapped FAIL-OPEN (an
  exception → set a `_ledger_unavailable` flag, do NOT accumulate/raise). `_month()` = the clock's
  `YYYY-MM`. `exceeded()` gains a monthly arm (`per_user_monthly_usd is not None and _monthly_total >
  per_user_monthly_usd`). When the monthly dim is unset, `record_turn` awaits nothing new (the 055
  path, byte-identical). Import `UsdLedger` from `loopplane.ledger` (foundational). Keep
  `start_run`/`spent`/`unpriced` as-is.

## Phase 2: Loop await (P1)

- [x] T002 In `src/loopplane/loop/loop.py` ~328-329: `await` the now-async `record_turn` —
  `(await self._budget_checker.record_turn(increment.usage)) is None`. No other loop change (the
  enforcement point + `exceeded()` check at ~228 + the `budget-exceeded` termination are unchanged).
  When `budget_checker` is None the path is unchanged.

## Phase 3: Controller + config wiring (P1)

- [x] T003 In `src/loopplane/controller/controller.py`: add `usd_ledger: UsdLedger | None = None` +
  `per_user_monthly_usd: Decimal | None = None` ctor kwargs (mirroring the 055 budget kwargs). In
  `_assemble`, build the `BudgetChecker` monthly dim from `usd_ledger` + `per_user_monthly_usd` +
  the `principal_id` already passed to `_assemble` — and EXTEND the build condition so a checker is
  built when the monthly dim is configured (not only the 055 per-message/session caps). **THREAD
  `principal_id` into the BudgetChecker on BOTH create AND resume** — `resume` currently omits it
  (~270-281); pass the persisted `principal_id` (from the checkpoint/`_Session`) so the monthly cap
  enforces on resumed sessions.
- [x] T004 In `src/loopplane/host/config.py`: add `RuntimeConfig.per_user_monthly_usd` (`Decimal |
  None = None`) + a host-supplied `usd_ledger` field (`UsdLedger | None`); coerce/validate
  (non-negative Decimal) in `from_mapping`/`validate_config`. In `src/loopplane/host/assembly.py`:
  forward `usd_ledger` + `per_user_monthly_usd` to the `RuntimeController` kwargs (mirror the 055
  budget forwarding). Default None → off.

## Phase 4: Tests (P1/P2)

- [x] T005 Update the existing 055 budget tests that call `record_turn` synchronously → `await` (the
  signature is now async). Add monthly-cap tests (offline; a `UsdLedger` [File/in-memory] + a scripted
  model): (a) a monthly cap crossed → terminate `budget-exceeded` after the crossing turn (output
  retained); under the cap → completes; (b) each turn's cost is added to the ledger
  `(principal_id, month)`; (c) default-off byte-identity — no monthly dim → the 055 events/behavior
  unchanged; (d) FAIL-OPEN — a `UsdLedger` whose `add` raises → NOT terminated, a public-safe
  diagnostic; (e) resume enforces — a resumed session + a monthly cap + a principal near the cap →
  terminates `budget-exceeded` (principal_id threaded on resume); (f) the DSN/principal_id never
  echoed. Use benign placeholders.

## Phase 5: Gates

- [x] T006 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-off byte-identity). Confirm: the structural audits
  (`test_no_execution_path_outside_the_gateway` [controller/loop import only foundational, NOT the
  tools layer], `test_public_safety`) + the events serialize/`SCHEMA_VERSION` tests (UNCHANGED — reuse
  `budget-exceeded`, no new reason) + the existing 055 budget suite (now awaited) pass. Do NOT run the
  full pytest concurrently with a verify Workflow (MCP load flake).

## Dependencies

- T001 → T002 (loop awaits the async record_turn) + T003 (controller builds the dim). T001/T003 →
  T005. T004 wires config. All → T006 (gates last).

## Implementation strategy

- Cross-cutting (budget + loop + controller + config + assembly + tests) — a fork MAY do it; then the
  four gates + the structural audits + the events SCHEMA_VERSION/api-reference tests + an adversarial
  verify (default-off byte-identity; the monthly cap terminates budget-exceeded after the crossing
  turn; FAIL-OPEN on a ledger outage; principal_id on create+resume [the gap closed]; reuse of the
  existing reason [no schema bump]; the controller/loop import boundary clean) before commit —
  Workflow if available, else MANUAL (run the full pytest + the workflow at different times). Commit
  only on a clean review / GO; fix + re-verify FRESH otherwise.
- Additive; ADR 0010; the LAST G22 Phase C unit (when Verified, all of G22 is complete).

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-21) — 0 critical, 0 high, 2 low (informational). 100% requirement
coverage (FR-001..FR-007 and SC-001..003 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ **ADR 0010** ↔ data-model ↔ contract ↔ tasks agree (the
optional monthly dimension on `BudgetChecker` [ledger + principal_id + a UTC `YYYY-MM` clock +
`per_user_monthly_usd`]; `record_turn` async [`await ledger.add` → fold into `exceeded()`]; the loop
awaits it; reuse the existing `budget-exceeded` reason; FAIL-OPEN; principal_id on create + resume;
`RuntimeConfig.per_user_monthly_usd` + a host `usd_ledger`; default-off byte-identical). **Additive —
behind ADR 0010 (all forks settled)**: no new `TerminationReason`, no `SCHEMA_VERSION`/content change;
the controller/loop import only `loopplane.budget`/`loopplane.ledger` (foundational, not the tools
layer — the audit holds). No Constitution violation (I/III/IV/V/VI/VII/X). Low notes (informational):
(1) the `record_turn` sync→async change (ADR 0010 D6) requires EVERY caller awaited — the loop
(loop.py:328-329) + the 055 budget tests; verify none is left calling it synchronously (a coroutine
would be silently truthy → the `is None` check breaks). (2) `principal_id` on resume must come from
the PERSISTED checkpoint (the `SessionMetaPayload.principal_id` / `_Session.principal_id`); confirm
resume reads it + threads it (the closed gap) — test a resumed session enforces. **Cleared for
`/speckit-implement`.**
