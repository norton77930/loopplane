# Contract: Cost Surfacing

Read-only web/API endpoints exposing computed USD (053/055/062). Additive; owner-scoped; default-off
honest; public-safe. No event/content/schema/reason/dependency change. P1 (no ADR).

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `GET /sessions/{session_id}/cost` | → `SessionCostView{session_id, usd_spent: str\|null}` | owner-only (`_owned_or_404`); null = not tracked. |
| `GET /cost/monthly` | → `MonthlyCostView{principal_id, month, usd_spent: str\|null}` | caller's OWN principal only; null = no ledger. |
| `BudgetChecker.session_spent` | read property → `Decimal` | exposes the per-session total. |
| `AgentLoop.current_session_cost()` | → `Decimal\|None` | None when no checker. |
| `RuntimeController.session_cost` / `monthly_spend` + host passthroughs | read-only | delegate like `history_snapshot`. |

## Behavior

| Case | Result |
| ---- | ------ |
| Owner GETs a budget-tracked session's cost | `usd_spent` = the accumulated USD (exact Decimal string). |
| Non-owner / unknown session GETs cost | 404 (no existence/cost leak), via `_owned_or_404`. |
| Session with no cap/budget configured | `usd_spent: null` ("not tracked") — no checker exists. |
| Principal GETs `/cost/monthly` with a ledger | `usd_spent` = `usd_ledger.get(principal, UTC YYYY-MM)`. |
| `/cost/monthly` with no `usd_ledger` | `usd_spent: null` ("not tracked"). |
| Any principal reading monthly | ONLY its own `principal.id` — never another's. |

## Invariants

- **Read-only**: no mutation of budget/ledger state; the loop run path is unchanged.
- **Default-off byte-identical**: no pricing/budget → session `null`; no `usd_ledger` → monthly
  `null`; the rest of the runtime is unchanged (no checker is forced into existence).
- **Owner-scoped / no leak**: session cost via `_owned_or_404`; monthly via the caller's own id;
  404 reveals nothing.
- **No schema change**: no event/content/checkpoint change; no new `TerminationReason`; `SCHEMA_VERSION`
  stays 1; no new dependency; no ADR.
- **Public-safe**: responses carry only the caller's own `principal_id` + an exact `Decimal`
  (string-encoded); never a DSN/secret/another-principal's data/internal path.
- **Out of scope**: the `/cost` slash COMMAND (065); per-run/historical breakdowns; streaming/push;
  billing; cross-principal admin; mutation; CLI cost view (065).
