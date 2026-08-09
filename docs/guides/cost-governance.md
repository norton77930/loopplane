# Cost governance

**Covered units:** 040, 041, 042, 053, 055, 062, 063, 064, 068.

How LoopPlane keeps token spend visible, bounded, and cheap. This guide is navigational:
[`../capabilities.md`](../capabilities.md) and [`../api-reference.md`](../api-reference.md)
are the authorities — where they disagree with this page, they win.

The arc has three layers, and you can adopt them independently:

1. **Spend less** — prompt caching and history compaction (040–042).
2. **Know what it costs** — a pricing table and queryable spend (053, 064).
3. **Refuse to overspend** — USD caps, a durable ledger, and a pre-turn guard
   (055, 062, 063, 068).

Budget enforcement, pricing, ledger wiring, and earlier compaction thresholds are opt-in.
One deliberate exception is Anthropic prompt caching: `AnthropicConfig.prompt_caching`
defaults to `True`; setting it to `False` restores the pre-caching request shape. The
runtime ships **no prices**: rates are host-supplied, because only the host knows its
contract.

## Spend less

### Prompt caching (040)

For Anthropic, cache breakpoints are placed on the stable prefix of the request, so the
unchanging part of a conversation is not re-billed at full rate every turn. It is a
provider-level optimization inside the adapter — no change to the loop or the event
stream.

### Auto-compaction (041, 042)

The context assembler already compacted history when it had to. Unit 041 made that
proactive and configurable through `RuntimeConfig.auto_compact_threshold`: a fraction of
the context window at which history is compacted before the model complains. `None` (the
default) keeps the original behavior byte-identical.

Unit 042 adds an optional `RuntimeConfig.compaction_summarizer` — a second, cheaper
`ModelBoundary` used only to summarize during compaction. It is a **fail-safe overlay**:
if the summarizer errors, compaction falls back to the deterministic path. Unset means no
behavior change at all.

## Know what it costs

### Pricing (053)

`loopplane.pricing` is a pure function of usage and rates: `PricingTable` maps a model id
to a `PricingRate` (exact `Decimal` input/output rates), and `cost()` returns the exact USD
cost — or `None` for a model with no price. It never guesses and never raises. Supply it
through `RuntimeConfig.pricing_table` (with `model_id` naming the model in use).

### Queryable spend (064)

Once pricing is wired, accumulated spend is readable rather than merely enforced:

- `GET /v1/sessions/{id}/cost` — this session's USD.
- `GET /v1/cost/monthly` — this principal's month-to-date USD.
- Host-side passthroughs `session_cost` and `monthly_spend` for embedders.

Both routes are owner-scoped and read-only: a caller sees only their own spend.

## Refuse to overspend

### Per-message and per-session caps (055)

`UsdBudgetCaps` carries `per_message_usd` and `per_session_usd` (each `None` = that
dimension is off). When a cap is exceeded the run terminates with the existing
`budget-exceeded` reason — no new event or record schema was introduced (ADR 0005).

### The durable USD ledger (062)

Enforcing a *monthly* cap requires memory across sessions and processes. `loopplane.ledger`
provides a `UsdLedger` keyed by `(principal, month)` with three backends —
`FileUsdLedger`, `SqliteUsdLedger`, `PostgresUsdLedger`. The Postgres backend is the only
cross-process-atomic option (it uses an atomic upsert-returning); pick it when more than
one worker records spend (ADR 0010).

The ledger is deliberately **separate from checkpointing**: it is an atomic counter, not
session state.

### Per-user monthly caps (063)

`per_user_monthly_usd` plus a `usd_ledger` folds the ledger total into the same enforcement
path, reusing the `budget-exceeded` reason. It **fails open**: if the ledger is
unavailable, the run proceeds rather than being blocked by an infrastructure outage. Decide
whether that trade-off is right for you before relying on it as a hard financial control.

### The pre-turn guard (068)

Caps above stop a run *after* an expensive turn. The pre-turn guard estimates the cost of a
turn *before* the model call — request tokens plus a configurable output bound
(`RuntimeConfig.pre_turn_max_output_tokens`) — and refuses a turn that would likely exceed
a cap. Default-off and fail-open, reusing the same `budget-exceeded` reason (ADR 0014,
extending ADR 0005).

## What the browser sees

Cost is enforced in the runtime, never in the client. The web surface exposes exact
session/monthly USD to the owner and, for posture, an **enum-only** snapshot
(`BudgetPostureSnapshot`: `within` / `near` / `exceeded` / `disabled` / `unknown`). Raw
caps and rates never reach the browser. See [Web UI product](web-ui-product.md).

## A worked configuration

```text
pricing_table       -> your rates, keyed by model id      (053)
model_id            -> the model you are billing against  (053)
per_message_usd     -> a small per-turn ceiling           (055)
per_session_usd     -> a session ceiling                  (055)
usd_ledger          -> Sqlite locally, Postgres for many workers (062)
per_user_monthly_usd-> the monthly ceiling per principal  (063)
pre_turn_max_output_tokens -> your worst-case output size (068)
auto_compact_threshold     -> e.g. compact before the window fills (041)
```

Leave any line out and that dimension is simply off.

## Limits worth knowing

- There is **no metering or invoicing layer** — spend is queryable, not billable
  ([`../capabilities.md`](../capabilities.md#scope-boundaries-out-of-scope--deferred)).
- Costs are only as good as the rates you supply; an unpriced model yields `None`, and
  posture reports `unpriced` rather than pretending.
- Monthly enforcement is per **principal**, so it depends on authenticated principals —
  see [Platform & deployment](platform-and-deployment.md).

## Where to go next

- [Platform & deployment](platform-and-deployment.md) — principals, pooling, and quotas.
- [Agent tools & permissions](agent-tools-and-permissions.md) — the decide stage that
  budget policies participate in.
- [`../api-reference.md`](../api-reference.md) — the exact public names and signatures.
