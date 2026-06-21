# Data Model: Pre-Turn Cost Guard

## RuntimeConfig.pre_turn_max_output_tokens

| Field | Type | Rules |
| ----- | ---- | ----- |
| `pre_turn_max_output_tokens` | `int | None` | `None` disables the pre-turn guard. Non-negative integer when set; `0` is valid and estimates input cost only. |

This is a host-owned estimate for cost prediction only. It does not set provider generation limits.

## PreTurnCostEstimate

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `input_tokens` | `int` | Estimated assembled request tokens. |
| `max_output_tokens` | `int` | Configured worst expected output tokens. |
| `estimated_usd` | `Decimal` | `input_tokens * input_rate + max_output_tokens * output_rate`. |

The estimate is computed without mutation. Missing price or missing token estimate yields no
estimate, and the guard fails open.

## RemainingBudgetView

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `per_message_remaining` | `Decimal | None` | `per_message_usd - current_message_spent`, when configured. |
| `per_session_remaining` | `Decimal | None` | `per_session_usd - current_session_spent`, when configured. |

Only locally known per-message and per-session caps participate in 068. Durable monthly prediction
is out of scope.

## PreTurnBudgetDecision

| Decision | Meaning |
| -------- | ------- |
| `allow` | The estimate is within all known caps, or the guard is incomplete/disabled. |
| `refuse` | The estimate is greater than at least one known remaining cap. |

`refuse` maps to `budget-exceeded`. The decision does not reserve spend; post-turn accounting remains
authoritative after an allowed model call.

## State Transitions

```text
guard disabled/incomplete -> allow -> model call -> post-turn BudgetChecker.record_turn
guard complete + estimate <= remaining caps -> allow -> model call -> post-turn BudgetChecker.record_turn
guard complete + estimate > any remaining cap -> refuse -> run_terminated("budget-exceeded")
```

Equality is allowed, matching 055's strict greater-than cap crossing rule.
