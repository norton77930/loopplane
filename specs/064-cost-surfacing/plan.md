# Implementation Plan: Cost Surfacing

**Branch**: `064-cost-surfacing` (main-only autopilot) | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/064-cost-surfacing/spec.md`

**Boundary**: P1 (review-backlog batch 064–072, 1/9). Additive read-only webapi surface; **no ADR**.

## Summary

Surface the USD cost that 053/055/062 already compute but never expose. Add **read-only** accessors
threaded from the existing per-session `BudgetChecker` + the host-supplied `UsdLedger`, and two
owner-scoped web/API GET endpoints: a session's accumulated USD, and the calling principal's
current-month USD. Additive + read-only — no loop / Event Bus / content / checkpoint change, no new
`TerminationReason`, no `SCHEMA_VERSION` bump, no new dependency. Default-off honest: no
pricing/budget → session cost `null` ("not tracked"); no `usd_ledger` → monthly `null`. Reuses the
webapi auth/ownership pattern; public-safe (only the caller's own data; exact `Decimal` as string).

## Technical Context

**Language/Version**: Python 3.11+; FastAPI (the existing `loopplane[web]` extra); `decimal.Decimal`.

**Primary Dependencies**: none new — reuses webapi (`require`/`_require`/`_owned_or_404`), 055
`BudgetChecker`, 062 `UsdLedger`, the host/controller seam.

**Storage**: none new (reads the in-memory `BudgetChecker` total + the host's `UsdLedger`).

**Testing**: pytest, offline (the in-process app + the existing test auth + a budget-configured
session + an in-memory/File ledger): owner reads session cost; non-owner → 404; no-budget → null;
principal reads its own monthly spend; no-ledger → null; never another principal's; exact Decimal
string; public-safe.

**Target Platform**: cross-platform library + web host.

**Constraints**: additive; read-only (no mutation); default-off byte-identical; owner-scoped (reuse
the 404 pattern); public-safe; no schema/reason/dependency change; no ADR.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-006. ✅
- **III. Cost transparency**: surfaces spend so a host/UI can act before a hard `budget-exceeded`
  stop. ✅
- **IV. Boundary**: a webapi read surface delegating through the host → controller (the established
  seam, like `history_snapshot`); the read accessor on `BudgetChecker`/`AgentLoop` is additive +
  read-only; the loop run path is unchanged. ✅
- **V. Tool Gateway**: N/A — no tool/execution path. ✅
- **VI. Event Bus**: NO event/`SCHEMA_VERSION`/`TerminationReason`/content change. ✅
- **VII. Public-safe**: only the caller's own principal id + an exact Decimal (string); no
  DSN/secret/another-principal data/internal path. ✅
- **X. Testable Evolution**: Additive; default-off byte-identical (no budget/ledger → null);
  read-only; reversible; offline-tested. ✅

**Result**: PASS — additive read-only surfacing within the established host/ownership boundary; no
ADR. Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/064-cost-surfacing/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/cost-surfacing.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/budget/__init__.py        # MODIFIED: + BudgetChecker.session_spent read property
                                        #   (returns the per-session total; additive, read-only)
src/loopplane/loop/loop.py              # MODIFIED: + AgentLoop.current_session_cost() -> Decimal|None
                                        #   (the checker's session_spent, or None when no checker)
src/loopplane/controller/controller.py  # MODIFIED: + session_cost(session_id) -> Decimal|None
                                        #   (reads _Session.loop.current_session_cost()) +
                                        #   monthly_spend(principal_id) -> Decimal|None (None when no
                                        #   usd_ledger; else usd_ledger.get(principal_id, _utc_month))
src/loopplane/host/host.py              # MODIFIED: + session_cost / monthly_spend passthroughs
src/loopplane/webapi/app.py             # MODIFIED: + GET /sessions/{id}/cost (owner-scoped) +
                                        #   GET /cost/monthly (caller's own principal)
src/loopplane/webapi/models.py          # MODIFIED: + SessionCostView + MonthlyCostView
tests/<cost surfacing tests>            # NEW
```

**Structure Decision**: A thin read-only accessor chain, each layer additive:
`BudgetChecker.session_spent` (the existing private `_session_spent` exposed read-only) →
`AgentLoop.current_session_cost()` (returns it, or `None` when no checker was built — i.e. no cap
configured) → `RuntimeController.session_cost(session_id)` + `monthly_spend(principal_id)` →
`LoopPlaneHost` passthroughs (mirroring `history_snapshot`) → two webapi GET routes reusing the
ownership pattern (`_owned_or_404` for the session route; the caller's own `principal.id` for the
monthly route — a principal can read ONLY its own). The month is the UTC `YYYY-MM` derivation
consistent with 063 (`datetime.now(UTC).strftime("%Y-%m")`). The cost is reported only when a
`BudgetChecker` exists (a cap/monthly-dim configured) — building a checker when none exists today
would NOT be byte-identical (it would compute + could emit the unpriced diagnostic), so "not tracked"
(`null`) is the honest default-off answer, not a forced checker. Responses string-encode the exact
`Decimal`. Host-pool note: the cost routes mirror the existing inspection routes' `host` usage (any
host-pool inspection-routing nuance is pre-existing, out of 064's scope).

## Complexity Tracking

> A read-only surfacing layer over existing computed cost (055 spend + 062 ledger). Additive,
> default-off byte-identical, owner-scoped, public-safe; no schema/reason/dependency/ADR. Not a
> Constitution violation.
