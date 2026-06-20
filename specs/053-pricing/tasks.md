# Tasks: Server-Side Pricing

**Feature**: 053-pricing | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive — one new standalone module `src/loopplane/pricing.py` + an api-reference
section + tests. Pure metadata, NOT wired into the runtime → byte-identical when unused. No
enforcement (G22 caps deferred); no event-schema/content-model change; no new dependency (stdlib
`decimal`); no ADR.

**Tests**: requested (TDD-friendly).

## Phase 1: The pricing module (P1) 🎯 MVP

- [x] T001 Create `src/loopplane/pricing.py`: a frozen `PricingRate` dataclass (`input_rate:
  Decimal`, `output_rate: Decimal`); a frozen/immutable `PricingTable` wrapping a host-supplied
  `Mapping[str, PricingRate]` with `cost(self, usage: TokenUsage, model: str) -> Decimal | None`
  returning `None` for an unknown model, else `usage.input_tokens * rate.input_rate +
  usage.output_tokens * rate.output_rate` (exact `Decimal`). Reuse `loopplane.model.TokenUsage`.
  Declare `__all__ = ["PricingRate", "PricingTable"]`. Pure: no I/O, no network, no bundled prices,
  no import of loop/controller/gateway; no enforcement.

## Phase 2: Export + docs (P2)

- [x] T002 Add a `loopplane.pricing` section to `docs/api-reference.md` listing `PricingRate` +
  `PricingTable` with one-line descriptions, so the unit-014 api-reference bijection
  (`tests/contract/test_api_reference.py`) stays exact. (If the bijection test enumerates packages
  via a fixed list/discovery, ensure `loopplane.pricing` is covered.)

## Phase 3: Tests (P3)

- [x] T003 Write `tests/unit/test_pricing.py` (offline): (a) priced cost equals `input×input_rate +
  output×output_rate` exactly; (b) large counts + fractional per-token rates → exact `Decimal` (no
  float drift — assert the exact expected `Decimal`); (c) unknown model → `None`; (d) zero usage or
  zero rates → `Decimal('0')`; (e) immutability (PricingRate/PricingTable are frozen — mutating
  raises); (f) public-safety / pure-metadata — the module exposes only value objects + a cost
  function (no tool, no side effect); (g) reuse — a real `TokenUsage` instance is priced.

## Phase 4: Polish & Cross-Cutting

- [x] T004 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof; pricing is unwired so the runtime is byte-identical).
  ALSO confirm the structural audits stay green: `test_no_execution_path_outside_the_gateway`,
  `test_public_safety`, and the api-reference bijection (`test_api_reference.py`).

## Dependencies

- T001 → T002, T003. T001/T002 → T004 (gates last).

## Implementation strategy

- Tiny + single-module — an INLINE implement (no fork). ULTRACODE: run the four gates + the
  structural audits + an adversarial review (default-off byte-identity / pure-metadata-no-
  enforcement / exact-Decimal money / unknown→None / public-safety / not-wired-into-the-loop)
  before committing; prefer an adversarial Workflow, else do the review MANUALLY (the API session
  limit). Commit only on a clean review.
- All additive; pure metadata; no enforcement; no ADR.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 2 low (informational). 100%
requirement coverage (FR-001..FR-007 and SC-001..004 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ research ↔ data-model ↔ contract ↔ tasks agree (a
standalone `loopplane.pricing` module — `PricingRate` + `PricingTable` + a pure `cost(usage,
model) -> Decimal | None`; reuse `TokenUsage`; exact Decimal; unknown → None; host-supplied / no
prices / no network; pure metadata, NOT wired into the runtime). **Boundary review: additive** — no
enforcement (G22 caps explicitly deferred per FR-004), no event-schema / `SCHEMA_VERSION` /
content-model change, no new `TerminationReason`, no loop/controller wiring, no ADR; default-off
byte-identical. No Constitution violation (III/IV/V/VI/X). Low notes are informational: (1) cached/
reasoning-token rates are a deferred additive extension (v1 prices input + output per FR-002);
(2) confirm the api-reference bijection test enumerates the new `loopplane.pricing` package (add
the section so it stays exact). **Cleared for `/speckit-implement`.**
