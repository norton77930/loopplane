# Contract: Pre-Turn Cost Guard

The pre-turn guard is an optional runtime budget behavior layered on 055.

## Configuration

| Input | Required for pre-turn denial | Default |
| ----- | ---------------------------- | ------- |
| `RuntimeConfig.per_message_usd` or `per_session_usd` | Yes, at least one known cap | `None` |
| `RuntimeConfig.pricing_table` | Yes | `None` |
| `RuntimeConfig.model_id` | Yes | `None` |
| `RuntimeConfig.pre_turn_max_output_tokens` | Yes | `None` |
| Assembled request input-token estimate | Yes | computed locally; unavailable means fail-open |

## Behavior

| Scenario | Expected outcome |
| -------- | ---------------- |
| Guard unset | No estimate, no denial, no new events; existing behavior unchanged. |
| Estimate complete and `estimated_usd > remaining per-message cap` | Terminate before model call with `budget-exceeded`. |
| Estimate complete and `estimated_usd > remaining per-session cap` | Terminate before model call with `budget-exceeded`. |
| Estimate complete and exactly equal to remaining cap | Allow model call; post-turn checker remains authoritative. |
| Pricing/model/max-output/token estimate missing | Fail open; allow model call. |
| Unpriced model | Fail open; allow model call; optional diagnostic must be generic/public-safe. |
| Allowed model call later crosses actual cap | Existing post-turn 055 behavior terminates `budget-exceeded`. |

## Event Contract

- Uses the existing `budget-exceeded` `TerminationReason`.
- Does not add a new runtime event.
- Does not change `SCHEMA_VERSION`.
- Must not reuse `cancelled`.
- A refusal occurs before assistant output for that turn; the user input remains part of history and
  checkpoint/replay semantics stay consistent with a budget stop.

## Public-Safety Contract

Diagnostics, if emitted, must be generic. They must not include prompt text, private paths,
credentials, raw prices, cap amounts, or principal identifiers.
