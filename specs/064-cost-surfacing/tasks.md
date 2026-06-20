# Tasks: Cost Surfacing

**Feature**: 064-cost-surfacing | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive read-only surfacing of computed USD (053/055/062) — a thin accessor chain + two
owner-scoped webapi GET endpoints. No ADR. Default-off honest; read-only; no loop/event/content/
schema/reason/dependency change. P1 (batch 064–072, 1/9).

**Tests**: requested.

## Phase 1: Read accessors (P1) 🎯

- [ ] T001 In `src/loopplane/budget/__init__.py`: add `BudgetChecker.session_spent` — a read-only
  `@property -> Decimal` returning the existing `_session_spent` (the per-session accumulated USD).
  Additive; no behaviour change (read-only).
- [ ] T002 In `src/loopplane/loop/loop.py`: add `AgentLoop.current_session_cost(self) -> Decimal |
  None` — returns `self._budget_checker.session_spent` when a checker exists, else `None`. Read-only;
  no run-path change. (Loop may import `loopplane.budget` — foundational; keep the literal
  "loopplane.tools" out.)
- [ ] T003 In `src/loopplane/controller/controller.py`: add `session_cost(self, session_id: str) ->
  Decimal | None` (reads `self._sessions[session_id].loop.current_session_cost()`; `KeyError` on
  unknown) + `monthly_spend(self, principal_id: str) -> Decimal | None` (`None` when
  `self._usd_ledger is None`; else `self._usd_ledger.get(principal_id, datetime.now(UTC).strftime(
  "%Y-%m"))` — the UTC YYYY-MM derivation consistent with 063). Read-only; both additive.

## Phase 2: Host passthrough (P1)

- [ ] T004 In `src/loopplane/host/host.py`: add `LoopPlaneHost.session_cost(session_id) ->
  Decimal | None` + `monthly_spend(principal_id) -> Decimal | None` passthroughs to the controller,
  mirroring the existing `history_snapshot` / `set_session_title` delegation. Additive, read-only.

## Phase 3: Web/API endpoints (P1)

- [ ] T005 In `src/loopplane/webapi/models.py`: add `SessionCostView { session_id: str, usd_spent:
  str | None }` + `MonthlyCostView { principal_id: str, month: str, usd_spent: str | None }` (the
  Decimal string-encoded; `None` = not tracked). A small `from_*` helper that stringifies the Decimal.
- [ ] T006 In `src/loopplane/webapi/app.py`: add `GET /sessions/{session_id}/cost` (owner-scoped via
  `_owned_or_404`; `host.session_cost(session_id)` → `SessionCostView`; unknown/non-owner → 404) +
  `GET /cost/monthly` (`host.monthly_spend(principal.id)` → `MonthlyCostView` for the caller's OWN
  principal only; `month` = UTC YYYY-MM). Mirror the existing inspection routes' `host` usage. No
  mutation.

## Phase 4: Tests (P1)

- [ ] T007 Add `tests/<unit>/test_cost_surfacing.py` (offline; the in-process app + the test auth + a
  budget-configured session + an in-memory/File `UsdLedger`): (a) owner GETs a budget-tracked
  session's cost → the exact accumulated USD (Decimal string); (b) non-owner / unknown → 404;
  (c) no-budget session → `usd_spent: null`; (d) a principal GETs `/cost/monthly` with a seeded
  ledger → its own current-month total; never another principal's; (e) no `usd_ledger` →
  `usd_spent: null`; (f) public-safety — the responses carry only the caller's own id + a Decimal
  string (no DSN/secret/other-principal). Plus a unit test for `BudgetChecker.session_spent` +
  `AgentLoop.current_session_cost()` (None when no checker). Use benign placeholders.

## Phase 5: Gates

- [ ] T008 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-off byte-identity). Confirm: structural audits
  (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the events
  serialize/`SCHEMA_VERSION` tests (UNCHANGED — no event change) + the existing webapi suite pass; if
  any new public name is exported, update `docs/api-reference.md` (bijection). Do NOT run the full
  pytest concurrently with a verify Workflow (MCP load flake).

## Dependencies

- T001 → T002 → T003 → T004 → T006 (the accessor chain bottom-up); T005 (models) before T006; T007
  after T006; T008 last.

## Implementation strategy

- A thin read-only accessor chain + two webapi routes. May be done inline or via a fork; then the four
  gates + the structural audits + the events SCHEMA_VERSION/api-reference tests + an adversarial verify
  (default-off byte-identity [no checker → null, no ledger → null, no forced checker]; read-only [no
  budget/ledger mutation]; owner-scoping / no cross-principal leak; public-safety; no schema/reason/
  dependency change) before commit — Workflow if available, else MANUAL. Commit only on a clean
  review / GO; fix + re-verify FRESH otherwise.
- Additive; P1; no ADR.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
