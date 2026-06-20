# Contract: USD Budget Enforcement

In-loop USD cap enforcement ([ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md)). Active only
when a `RuntimeConfig` USD cap + a host-supplied `PricingTable` (+ model-id) are configured; default
(no caps) is byte-identical. Reuses 053's `PricingTable.cost`.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `RuntimeConfig.per_message_usd` | `Decimal \| None = None` | Per-run USD cap (off when None). |
| `RuntimeConfig.per_session_usd` | `Decimal \| None = None` | Per-session cumulative USD cap (off when None). |
| `TerminationReason` += `budget-exceeded` | additive Literal member | New run-termination reason (no `SCHEMA_VERSION` bump). |

## Behavior

| Case | Result |
| ---- | ------ |
| No caps configured (default) | Byte-identical to today: no cost accounting, no new events, the runtime + event stream unchanged. |
| Cap + pricing, accumulated cost crosses a cap | The run terminates with `run_terminated("budget-exceeded", turns_completed)` AFTER the crossing turn; that turn's assistant output is retained (not orphaned). |
| Cap + pricing, under the cap | The run completes normally (`natural-completion`). |
| Cap + an UNPRICED model (`cost` None) | Fail-soft: the cap is not enforced for that turn; a `diagnostic("warning","budget",…)` is emitted; the run is not terminated for budget. |
| per-session cap, cumulative across runs | The session's running USD total carries on `_Session`; a later run terminates `budget-exceeded` when it crosses; resets on `resume()` (documented). |
| Events serialized / replayed | `budget-exceeded` round-trips with NO `SCHEMA_VERSION` change; every consumer (CLI render, checkpoint rebuild, web/API, apps/web) handles it. |

## Invariants

- Enforcement lives INSIDE the Agent Loop turn cycle (the only place `TokenUsage` exists); not the
  decide stage. Terminates via the existing contained terminate path (no orphaned output, VII).
- The `budget-exceeded` reason is DISTINCT — never `cancelled` (input-stranding) nor
  `turn-budget-exhausted` (count-based). Additive within `SCHEMA_VERSION = 1` (no bump).
- Default-off (`per_message_usd` / `per_session_usd` None + `budget_checker` None) is byte-identical
  to pre-055 (proven by a test).
- Stop-after-overage (total ≈ cap + one turn; no mid-turn pre-emption). Fail-soft on unpriced.
- Exact `Decimal` money; no new dependency; reuses 053 `PricingTable.cost`. Phase C deferred.
- The loop's import boundary stays clean (pricing is a foundational package, not `loopplane.tools`;
  the no-execution-outside-gateway audit is unaffected).
