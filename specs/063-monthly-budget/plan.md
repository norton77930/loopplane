# Implementation Plan: Per-User-Monthly USD Cap

**Branch**: `063-monthly-budget` (main-only autopilot) | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/063-monthly-budget/spec.md`

**Boundary**: settled by **[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md)** (authored
at 062; covers 062+063; all four forks settled — no new ADR, no consult). 063 is the enforcement
half: extend 055's `BudgetChecker` with the optional monthly dimension backed by 062's `UsdLedger`.

## Summary

Add a per-user-monthly USD cap by extending 055's `BudgetChecker` (`budget/__init__.py`) with an
OPTIONAL monthly dimension: a `UsdLedger` (062) + `principal_id` + a `YYYY-MM` month (from an
injectable clock, default `datetime.now(UTC)`) + a `per_user_monthly_usd: Decimal | None` cap.
`record_turn` becomes **async**: when the monthly dim is configured + the turn has a price, it
`await ledger.add(principal_id, month, cost)` and folds the returned monthly total into `exceeded()`.
The loop's `record_turn` call (`loop.py:328-329`) becomes awaited; the cap terminates with the
EXISTING `budget-exceeded` `TerminationReason` after the crossing turn (no new reason, no
`SCHEMA_VERSION` bump). **FAIL-OPEN**: a ledger `add` exception → allow + a public-safe diagnostic
(never crash/deny). Wired in `controller._assemble` from a host-supplied `UsdLedger` + a new
`RuntimeConfig.per_user_monthly_usd` (default `None`) + `principal_id`, threaded on BOTH create AND
resume (closing a fail-open gap). **Default-off byte-identical** (no monthly dim → `record_turn`
awaits nothing new; the 055 path unchanged). The DSN + `principal_id` are public-safe.

## Technical Context

**Language/Version**: Python 3.11+; `datetime`/`decimal`.

**Primary Dependencies**: none new — reuses 055's `BudgetChecker` + the loop enforcement point +
`budget-exceeded`, 062's `loopplane.ledger.UsdLedger`, the controller's `principal_id`.

**Storage**: the 062 `UsdLedger` (host-supplied; atomic per-`(principal_id, month)`).

**Testing**: pytest, offline — a `UsdLedger` (File/in-memory) + a scripted model: a monthly cap
crossed → terminate `budget-exceeded` (after the crossing turn, output retained); default-off
byte-identity (no monthly dim → 055 events unchanged); fail-open (a failing ledger → allow + a
diagnostic); the resume path enforces (principal_id threaded); the 055 tests updated to `await`
`record_turn`.

**Target Platform**: cross-platform library.

**Constraints**: additive; default-off byte-identical; reuse the `budget-exceeded` reason (no
schema bump); fail-open; thread principal_id on create + resume; the controller/loop import only
`loopplane.budget`/`loopplane.ledger` (foundational), never the tools layer; public-safe. ADR 0010.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007 + ADR 0010. ✅
- **III. Bounded cost-safety**: a per-user-monthly cap (durable), opt-in, default-off. ✅
- **IV. Boundary**: extends the 055 in-loop enforcement (already opened by ADR 0005); reads the 062
  ledger; the controller/loop import only foundational packages (the no-tools-layer audit holds). ✅
- **V. Tool Gateway**: N/A — no tool/execution path. ✅
- **VI. Event Bus**: Reuses `budget-exceeded`; NO new `TerminationReason`, NO `SCHEMA_VERSION`
  bump, no content change. ✅
- **VII. Public-safe**: the DSN + `principal_id` are never echoed. ✅
- **X. Testable Evolution**: Additive; default-off byte-identical (runtime); reversible;
  offline-tested. ✅

**Result**: PASS — additive, behind ADR 0010 (all forks settled). The `record_turn` sync→async is an
approved (ADR 0010 D6) signature change to the 055 `BudgetChecker` — the loop call + the 055 tests
become awaited; no new `TerminationReason`/schema bump, no unexpected 001/002 break. Complexity
Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/063-monthly-budget/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/monthly-budget.md
└── checklists/requirements.md
docs/adr/0010-usd-ledger-monthly-budget.md   # the Phase C decision (062+063; already authored)
```

### Source Code (repository root)

```text
src/loopplane/budget/__init__.py        # MODIFIED: BudgetChecker + optional (ledger, principal_id,
                                        #   clock, per_user_monthly_usd); record_turn -> async
                                        #   (await ledger.add; fold the monthly total); exceeded()
                                        #   folds monthly; FAIL-OPEN on a ledger exception
src/loopplane/loop/loop.py              # MODIFIED: await budget_checker.record_turn(...) (328-329)
src/loopplane/controller/controller.py  # MODIFIED: + usd_ledger + per_user_monthly_usd ctor kwargs;
                                        #   _assemble builds the BudgetChecker monthly dim with
                                        #   principal_id; thread principal_id on create AND resume
src/loopplane/host/config.py            # MODIFIED: RuntimeConfig.per_user_monthly_usd (Decimal|None)
                                        #   + from_mapping/validate_config; usd_ledger host field
src/loopplane/host/assembly.py          # MODIFIED: forward usd_ledger + per_user_monthly_usd
tests/<budget monthly tests>            # NEW + MODIFIED (await the 055 record_turn calls)
```

**Structure Decision**: The monthly dimension is OPTIONAL on `BudgetChecker` — when its
`(ledger, principal_id, per_user_monthly_usd)` are unset, `record_turn` does no ledger await (the 055
path, byte-identical at runtime). `record_turn` is declared `async` (the loop awaits it; the 055
tests are updated to `await` — an approved ADR 0010 signature change). `exceeded()` adds a monthly
arm folding the ledger-returned total. The controller builds the monthly dim in `_assemble` (alongside
the 055 caps) from `usd_ledger` + `per_user_monthly_usd` + `principal_id`, and passes `principal_id`
on resume (closing the gap — the persisted `principal_id` is read from the checkpoint). FAIL-OPEN:
the `await ledger.add` is wrapped so an exception → a diagnostic + allow (no accumulation, no
termination). The controller/loop import `loopplane.budget`/`loopplane.ledger` only (foundational).

## Complexity Tracking

> Extends the 055 enforcement seam with a durable monthly dimension behind ADR 0010 (all forks
> settled). The one signature ripple (`record_turn` sync→async) is approved + gated default-off
> (runtime byte-identical); reuses `budget-exceeded` (no schema bump); fail-open; principal_id on
> create+resume. Not a Constitution violation.
