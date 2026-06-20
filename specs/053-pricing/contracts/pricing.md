# Contract: Server-Side Pricing

A standalone `loopplane.pricing` module (NOT a tool, NOT wired into the runtime). Pure metadata a
host/observability layer invokes on demand.

## Public surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `PricingRate` | `(input_rate: Decimal, output_rate: Decimal)` | A model's per-token USD rates. |
| `PricingTable` | host-supplied `{model id: PricingRate}` + `cost(usage, model)` | Immutable value object. |

## Behavior

| Case | Result |
| ---- | ------ |
| `cost(usage, model)` for a priced model | Exact `Decimal` = `usage.input_tokens × input_rate + usage.output_tokens × output_rate`. |
| `cost(usage, unknown_model)` | `None` (a clear "no price"; never a guess, never a crash). |
| zero usage / zero rates | exact `Decimal('0')`. |
| large counts + fractional rates | exact decimal (no float drift). |
| no pricing configured (the module never imported/used) | the runtime is byte-identical to today. |

## Invariants

- **Pure metadata**: pricing enforces nothing, alters no run/loop/turn behavior, adds no budget
  cap, no `TerminationReason`, and no event-schema / content-model change (G22 caps DEFERRED).
- **Standalone**: the module is imported by nobody in the runtime (loop/controller/gateway
  untouched); a host calls `PricingTable.cost(...)`.
- **Host-supplied + offline**: no bundled prices, no network; the unit ships no rates.
- **Exact money**: `decimal.Decimal` throughout (no float).
- **Public-safe (VII)**: the table carries only model ids + numeric rates; the cost is a number.
- **Default-off byte-identical**; reuses `loopplane.model.TokenUsage`; no new dependency; no ADR.
