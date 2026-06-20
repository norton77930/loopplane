# Data Model: Server-Side Pricing

Additive; a standalone value-object module. No new content block / event / RunContext field; no
wiring into the loop/controller.

## PricingRate (new value object)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `input_rate` | `Decimal` | USD per input token. |
| `output_rate` | `Decimal` | USD per output token. |

- Immutable; exact decimals. (cached/reasoning rates are a deferred additive extension.)

## PricingTable (new value object)

| Member | Type | Notes |
| ------ | ---- | ----- |
| rates | `Mapping[str, PricingRate]` | Host-supplied `model id → PricingRate`; immutable. |

Method: `cost(usage: TokenUsage, model: str) -> Decimal | None` — `None` when `model` has no entry;
else `usage.input_tokens * rate.input_rate + usage.output_tokens * rate.output_rate` (exact
`Decimal`).

## Reuse

- `loopplane.model.TokenUsage` (`input_tokens: int`, `output_tokens: int`; also `cached_tokens` /
  `reasoning_tokens`, not priced in v1).

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| Host-supplied PricingTable; no bundled prices / network | FR-001, FR-005 |
| Pure cost = input×input_rate + output×output_rate, exact Decimal | FR-002 |
| Unknown model → None (no guess, no crash) | FR-003 |
| Pure metadata: no enforcement, no loop/turn/event/content change, no termination cause | FR-004 |
| Default-off / additive: byte-identical when unused (the module is unwired) | FR-005 |
| Public-safe: model ids + numeric rates only | FR-006 |
| Reuse TokenUsage; stdlib decimal; no new dependency; no ADR | FR-007 |
