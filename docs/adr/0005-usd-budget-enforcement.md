# ADR 0005: USD budget caps & in-loop cost enforcement

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (approved at the G22 design boundary review); spec 055
  (budget-caps).
- **Supersedes / superseded by**: none. Fifth ADR in the repository (after 0001–0004).
- **Related**: Constitution **III** (a bounded, opt-in cost-safety primitive), **IV** (Runtime
  Boundary Clarity — a new *enforcement point inside the Agent Loop turn cycle*, recorded here),
  **VI** (the Event Bus vocabulary grows by one `TerminationReason` member — additive within the
  schema version), **X** (additive, default-off, byte-identical when unconfigured; reversible).
  Builds on **053** (which shipped `loopplane.pricing` as pure, deliberately-unwired metadata).

## Context

053 shipped `loopplane.pricing.PricingTable.cost(usage, model) -> Decimal | None` as pure metadata,
**not wired** into the runtime. G22 Phase B is to enforce **USD budget caps** (per-message /
per-session). The enforcement point is constrained by where the data lives: USD cost derives from
`TokenUsage`, which exists **only post-turn** on the `TurnEnd` increment (`loop.py` turn cycle,
`increment.usage`). The decide-stage governance decider's signature is `(call, descriptor, context,
emitter)` — it runs **pre-tool** and never sees usage, so the existing 009 budget policy (which
weights tool-call counts, not USD) cannot host G22. USD enforcement must therefore live **inside the
Agent Loop turn cycle**. This crosses two Constitution-protected boundaries (the Agent Loop, IV; the
Event Bus `TerminationReason` vocabulary, VI), so it is ADR-gated.

## Decision

- **D1 — Enforce in the Agent Loop turn cycle, not the decide stage.** A per-run cost accumulator
  reads each turn's `TurnEnd.usage`, converts it to USD via the (host-supplied) `PricingTable.cost`,
  and checks the running total against the caps. The check slots into the `while True` turn loop
  next to the existing turn-budget guard (`loop.py` ~135–138 / after `turns_completed += 1`),
  terminating via the same `emitter.run_terminated(reason, turns_completed); return` pattern, after
  retaining the just-finished turn's output (the FR "never orphan output" discipline).
- **D2 — Add a distinct `budget-exceeded` `TerminationReason`; NO `SCHEMA_VERSION` bump.** The
  closed `TerminationReason` Literal (`events/envelope.py:194`) grows by one member —
  **additive within `SCHEMA_VERSION = 1`** (the version is the schema; the vocabulary grows
  additively, as the original members were one closed set). It MUST NOT reuse an existing reason —
  especially not `cancelled` (the checkpoint rebuild path strips a stranded user input on
  `cancelled` runs, so a budget stop reusing it would **silently drop the user's input**), nor
  `turn-budget-exhausted` (a different, count-based limit). The change requires: the Literal edit,
  the runtime-events contract doc (specs/011) update, a serialize/round-trip contract test, and an
  audit of every `TerminationReason` consumer (CLI render, checkpoint rebuild, web/API, apps/web).
- **D3 — Stop-after-overage semantic.** Because USD is knowable only post-turn, a cap terminates
  **after** the turn that crossed it; total spend is bounded to ≈ cap + one turn. It cannot
  pre-empt a single expensive turn (that would need a pre-turn token estimator the loop lacks and
  would blur the model boundary, IV). The spec/contract states this explicitly.
- **D4 — Fail-soft on unpriced models.** When `PricingTable.cost` returns `None` (the model has no
  price), the cap is **not enforced for that turn** and a diagnostic is emitted — never a crash,
  never a guessed/zero price (mirroring 053's pure-metadata stance). The residual "an unpriced
  model silently disables the cap" surface is specified + tested, not hidden.
- **D5 — Model-id provenance.** The `ModelBoundary` Protocol exposes no model id, but
  `PricingTable.cost` needs one; the **host supplies the model-id string** (alongside the
  `PricingTable` it already supplies) — the loop is not given a way to introspect the model.
- **D6 — Default-off, byte-identical.** Caps are optional `RuntimeConfig` fields
  (`per_message_usd` / `per_session_usd`, `Decimal | None`, default `None`); the loop gets an
  **optional `budget_checker` collaborator** (default `None`, the established assembler/hooks/
  summarizer optional-collaborator pattern). Unset → the new turn-loop block is skipped → the
  runtime + the event stream are byte-identical to pre-055. Per-session spend lives on the
  controller's session state; it **resets on resume** (documented — records do not reconstruct
  accumulated USD).
- **D7 — Phase C deferred.** A durable per-user-monthly USD ledger (cross-session atomic
  increments) is multi-tenant-shaped and **deferred to a later unit + ADR**, sequenced with the
  Tier-4 identity (G18) + durable-storage (G19) + isolation (G20) foundation.

## Consequences

- **Enables G22 Phase B**: opt-in USD caps that actually bound spend, reusing 053's cost function;
  contained, public-safe, default-off.
- **A new in-loop enforcement point (IV)** + an **additive event-vocabulary growth (VI, no
  `SCHEMA_VERSION` bump)**, both recorded here. Additive + reversible (default-off → revert by
  removing the caps + the `budget_checker` + the new reason). No new dependency.
- **Honest semantics**: stop-after-overage (not pre-emption) + fail-soft on unpriced models, both
  specified + tested rather than implied.
- **Deferred (documented follow-ups)**: G22 Phase C (durable per-user ledger); pre-turn cost
  estimation / mid-turn pre-emption. Out of scope unless a future unit + ADR revisits them.
