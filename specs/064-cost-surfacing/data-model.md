# Data Model: Cost Surfacing

Additive read-only. No event/content/checkpoint change. P1 (no ADR).

## Read accessors (modified — additive, read-only)

| Surface | Signature | Notes |
| ------- | --------- | ----- |
| `BudgetChecker.session_spent` | `@property -> Decimal` | the per-session accumulated USD (exposes the existing `_session_spent`); read-only. |
| `AgentLoop.current_session_cost` | `() -> Decimal \| None` | the checker's `session_spent`, or `None` when no `BudgetChecker` was built (no cap configured). |
| `RuntimeController.session_cost` | `(session_id: str) -> Decimal \| None` | reads `_Session.loop.current_session_cost()`; `KeyError` on unknown session (webapi maps ownership/404 first). |
| `RuntimeController.monthly_spend` | `(principal_id: str) -> Decimal \| None` | `None` when no `usd_ledger`; else `usd_ledger.get(principal_id, <UTC YYYY-MM>)`. |
| `LoopPlaneHost.session_cost` / `.monthly_spend` | passthroughs | mirror `history_snapshot` delegation. |

## Web/API read views (new)

| View | Shape |
| ---- | ----- |
| `SessionCostView` | `{ session_id: str, usd_spent: str \| null }` (Decimal-as-string; null = not tracked) |
| `MonthlyCostView` | `{ principal_id: str, month: str ("YYYY-MM"), usd_spent: str \| null }` |

## Endpoints (new, read-only, owner-scoped)

| Route | Owner check | Returns |
| ----- | ----------- | ------- |
| `GET /sessions/{session_id}/cost` | `_owned_or_404` | `SessionCostView` (the owner's session accumulated USD; null when not tracked) |
| `GET /cost/monthly` | caller's own `principal.id` only | `MonthlyCostView` (the caller's current-month USD; null when no ledger) |

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| session-cost endpoint, owner-only, 404 on non-owner/unknown | FR-001 |
| monthly endpoint = caller's own principal only, UTC YYYY-MM per 063 | FR-002 |
| minimal read accessor so per-session spend is queryable; no run-path change | FR-003 |
| default-off honest: no budget → session null; no ledger → monthly null; no crash | FR-004 |
| no loop/event/content/checkpoint/schema/reason/dependency change; read-only; no ADR | FR-005 |
| public-safe: only caller's own id + exact Decimal string; no DSN/secret/path | FR-006 |
