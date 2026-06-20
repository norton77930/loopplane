# Research: Server-Side Pricing

Additive, no open `NEEDS CLARIFICATION`. Decisions below.

## Decision 1 — A standalone pure module (no wiring, no enforcement)

**Decision**: `loopplane.pricing` is a standalone module with value objects + a pure cost
function. It is **not** imported by the loop/controller/gateway; a host/observability layer calls
it on demand. → byte-identical when unused (Constitution X), and G22 enforcement is structurally
out of scope.

**Rationale**: Phase A is metadata-only; keeping it unwired guarantees no run-behavior change and
no accidental drift into enforcement.

**Alternatives considered**: wiring cost into the loop/turn (rejected — that is G22 Phase B,
deferred, ADR-gated); a tool (rejected — pricing is host/reporting metadata, not an agent action).

## Decision 2 — Exact decimal money (no float drift)

**Decision**: `PricingRate` rates + the computed cost use `decimal.Decimal`. Cost = `input_tokens ×
input_rate + output_tokens × output_rate`.

**Rationale**: Money must be exact; float would drift on fractional per-token rates × large counts.
`decimal` is stdlib (no new dependency).

## Decision 3 — Per-token rates; host-supplied; unknown → None

**Decision**: Rates are **per-token** USD (documented; a host converts from per-million if needed).
The `PricingTable` is constructed from host-supplied data (the unit ships NO prices, makes NO
network call). `cost` for a model with no table entry returns `None` (a clear "no price"), never a
guess.

**Rationale**: Prices vary per host/contract + change often; the runtime must not embed or fetch
them. `None` (not 0) makes "unpriced" unambiguous.

**Alternatives considered**: per-million-token rates (a presentation choice — per-token is the
canonical unit; documented); a bundled default price list (rejected — staleness + public-safety +
offline).

## Decision 4 — Scope: input + output only (cached/reasoning deferred)

**Decision**: v1 prices `input_tokens` + `output_tokens` (per FR-002). `TokenUsage` also has
`cached_tokens` / `reasoning_tokens`; pricing those (often at different rates) is a documented
follow-up, out of v1 scope.

**Rationale**: Matches the spec; keeps the value object minimal. Extending `PricingRate` with
optional `cached_rate`/`reasoning_rate` later is additive.

## Decision 5 — Public surface + reuse

**Decision**: Export `PricingRate` + `PricingTable` from `loopplane.pricing.__all__`; document them
in `docs/api-reference.md` (the unit-014 bijection). Reuse `loopplane.model.TokenUsage` (fields
`input_tokens`/`output_tokens`).

**Rationale**: The host needs the value objects to build a table + compute cost; the api-reference
bijection must stay exact. No new dependency.
