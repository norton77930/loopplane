# Quickstart / Validation: Server-Side Pricing

See [contracts/pricing.md](contracts/pricing.md), [data-model.md](data-model.md), and
[research.md](research.md). The smallest, last Tier-3 unit — a standalone pure module, additive,
no ADR, no enforcement (G22 caps deferred).

## Run the unit tests

```powershell
pytest tests/unit/test_pricing.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new pricing tests. Pricing is unwired, so the
runtime is byte-identical to today.

## Validation scenarios (mirror the acceptance scenarios)

1. **Priced cost** — a `PricingTable` with model M's rates; `cost(TokenUsage(input, output), M)` =
   `input×input_rate + output×output_rate` exactly. (FR-002, SC-001)
2. **Large counts + fractional rates** — exact `Decimal`, no float drift. (FR-002, SC-001)
3. **Unknown model** — `cost(usage, "unknown")` is `None`. (FR-003, SC-002)
4. **Zero** — zero usage or zero rates → `Decimal('0')`. (edge, SC-002)
5. **Host-supplied / no bundled prices** — the module ships no rates; a host constructs the table.
   (FR-001/005, SC-004)
6. **Immutability** — `PricingTable` / `PricingRate` are immutable value objects. (data-model)
7. **No enforcement / no contract change** — assert no new `TerminationReason`, no event-schema
   change, and that pricing is not imported by the loop/controller. (FR-004, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the api-reference bijection (`test_api_reference.py`) with the new `loopplane.pricing` exports.
