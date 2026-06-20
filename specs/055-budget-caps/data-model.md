# Data Model: USD Budget Caps (In-Loop Enforcement)

Per [ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md). Additive; in-memory per-run/session
state; ONE additive event-vocabulary member. No content-model change, no `SCHEMA_VERSION` bump.

## TerminationReason (modified — additive)

`events/envelope.py` Literal gains one member:

| Member | Notes |
| ------ | ----- |
| `budget-exceeded` | NEW — a run terminated because a USD budget cap was crossed. Additive within `SCHEMA_VERSION = 1` (no bump). Distinct from `turn-budget-exhausted` (count-based) and `cancelled` (never reuse — input-stranding). |

(existing: `natural-completion`, `turn-budget-exhausted`, `cancelled`, `unrecoverable-error`.)

## UsdBudgetCaps (new — on RuntimeConfig)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `per_message_usd` | `Decimal \| None = None` | Per-run (per user message) USD cap; None = off. |
| `per_session_usd` | `Decimal \| None = None` | Per-session cumulative USD cap; None = off. |

Validated in `from_mapping` / `validate_config` (a non-negative Decimal; no secret). Both None
(default) → byte-identical.

## Budget checker (new — the in-loop collaborator)

A small pure object the loop consults per turn. Holds the per-run running USD total + the caps + the
`PricingTable` + the model-id; per-session prior spend is supplied by the controller.

| Member | Type | Notes |
| ------ | ---- | ----- |
| add_turn | `(usage: TokenUsage) -> None \| "unpriced"` | Add this turn's USD (via `PricingTable.cost`); signal unpriced (fail-soft). |
| exceeded | `() -> bool` | Whether per-message OR per-session cap is now crossed. |
| spent | `Decimal` | The run's accumulated USD (for the controller to fold into per-session spend). |

Threaded as an optional `AgentLoop.__init__(budget_checker=None)` collaborator (default None →
skipped → byte-identical). Built in the controller's `_assemble` from the caps + the host-supplied
`PricingTable` + model-id; per-session spend lives on `_Session` (reset on resume).

## Rules (from FRs + ADR 0005)

| Rule | Source |
| ---- | ------ |
| Accumulate per-turn USD via PricingTable.cost inside the loop turn cycle | FR-001, D1 |
| per-message + per-session caps; cross → terminate budget-exceeded (after the turn, output kept) | FR-002, D1 |
| Add budget-exceeded reason; additive, no SCHEMA_VERSION bump; never reuse cancelled | FR-003, D2 |
| Default-off byte-identical (caps None + budget_checker None) | FR-004, D6 |
| Unpriced model (cost None) → fail-soft (skip + diagnostic), never crash/guess | FR-005, D4 |
| Terminate via the existing contained path; per-session counter resets on resume | FR-006, D5 |
| Additive at signatures (optional caps + optional collaborator + session spend) | FR-007 |
| ADR 0005; Phase C (durable per-user ledger) DEFERRED | FR-008, D7 |
