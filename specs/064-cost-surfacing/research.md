# Research: Cost Surfacing

P1 (no ADR). Additive read-only surfacing. No open `NEEDS CLARIFICATION`.

## Decision 1 — Expose `_session_spent` read-only, do NOT force a checker

**Decision**: Add `BudgetChecker.session_spent` (a read property over the existing `_session_spent`).
Surface cost ONLY when a `BudgetChecker` exists (a per-message/session/monthly cap configured); when
none exists the session-cost endpoint reports `null` ("not tracked").

**Rationale**: The per-session total already accumulates on the checker (055). Building a checker when
no cap is configured (just to track cost) would NOT be byte-identical — `record_turn` would run,
compute cost, and could emit the unpriced diagnostic. The honest default-off answer is `null`, not a
behaviour change.

**Alternatives**: always build a checker when pricing+model are set (rejected — not byte-identical);
a separate cost accumulator (rejected — duplicates 055, more surface).

## Decision 2 — A read accessor chain through the existing host seam

**Decision**: `BudgetChecker.session_spent` → `AgentLoop.current_session_cost() -> Decimal | None` →
`RuntimeController.session_cost(session_id)` + `monthly_spend(principal_id)` → `LoopPlaneHost`
passthroughs → webapi GET routes. Mirrors how `history_snapshot`/`set_session_title` already delegate
host → controller → `_Session`.

**Rationale**: Reuse the proven read-delegation seam; no new architecture. `_Session` already holds
`loop: AgentLoop`, so the checker is reachable; the controller already holds `usd_ledger`.

**Alternatives**: reach into `entry.session.loop._budget_checker` from webapi (rejected — crosses the
boundary into private state; the host seam is the contract).

## Decision 3 — Monthly spend via `UsdLedger.get`, UTC `YYYY-MM` consistent with 063

**Decision**: `monthly_spend(principal_id)` returns `None` when no `usd_ledger`; else
`usd_ledger.get(principal_id, datetime.now(UTC).strftime("%Y-%m"))` — the same month derivation as
063's `BudgetChecker`. `get` is sync (062), read-only, unseen → `Decimal(0)`.

**Rationale**: Single source of truth (the durable ledger); consistent month boundary with the cap
enforcement; read-only.

## Decision 4 — Owner-scoping + public-safety

**Decision**: The session-cost route uses `_owned_or_404` (live OR durable owner); the monthly route
reads ONLY `principal.id` (a principal can never read another's spend). Responses carry only the
caller's own id + an exact `Decimal` (string-encoded). No DSN/secret/internal path.

**Rationale**: Reuse the established 404-no-leak ownership pattern; money is exact Decimal, never
float; never cross-principal.

## Out of scope

The `/cost` slash COMMAND (065); per-run/historical breakdowns; cost streaming/push; billing;
cross-principal admin views; mutation; CLI cost view (065). Any host-pool inspection-routing nuance
is pre-existing (the cost routes mirror the existing inspection routes' `host` usage).
