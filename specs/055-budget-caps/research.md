# Research: USD Budget Caps (In-Loop Enforcement)

The boundary questions are settled by **[ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md)**
(maintainer-approved). Decisions below record the resulting design; no open `NEEDS CLARIFICATION`.

## Decision 1 — Enforce in the Agent Loop turn cycle (ADR 0005 D1)

**Decision**: A per-run accumulator reads each turn's `TurnEnd.usage` (`loop.py` `_stream_model_turn`,
`increment.usage`), converts to USD via `PricingTable.cost`, and the loop checks the running total
against the caps after the turn (next to the turn-budget guard, `loop.py:135-138` / after
`turns_completed += 1`), terminating via `emitter.run_terminated("budget-exceeded",
turns_completed); return` with the crossing turn's output retained.

**Rationale**: USD derives from `TokenUsage`, a post-turn artifact (`TurnEnd.usage`); the
decide-stage decider `(call, descriptor, context, emitter)` never sees usage. The loop is the only
place the data exists. Reuses the existing terminate pattern verbatim.

**Alternatives considered**: a decide-stage decider (rejected — no usage there); a mid-turn
pre-emption (rejected — needs a pre-turn token estimator + blurs the model boundary, IV).

## Decision 2 — `budget-exceeded` TerminationReason; no SCHEMA_VERSION bump (ADR 0005 D2)

**Decision**: Add `"budget-exceeded"` to the closed `TerminationReason` Literal
(`events/envelope.py:194-199`, currently natural-completion / turn-budget-exhausted / cancelled /
unrecoverable-error). Additive within `SCHEMA_VERSION = 1` → **no bump**. Update specs/011
`contracts/runtime-events.md`, add a serialize/round-trip contract test, and audit every consumer
(CLI render, checkpoint rebuild, web/API, apps/web).

**Rationale**: The version IS the schema; the vocabulary grows additively (the 4 reasons were one
closed set). A distinct reason is the honest signal.

**Alternatives considered**: reuse `cancelled` (REJECTED — `checkpoint/rebuild.py` strips a stranded
user input on `cancelled`, silently dropping the user's input); reuse `turn-budget-exhausted`
(rejected — a different, count-based limit; misleads consumers); bump `SCHEMA_VERSION` (rejected —
overkill for an additive enum member).

## Decision 3 — Default-off, additive collaborator (ADR 0005 D6)

**Decision**: `RuntimeConfig.per_message_usd` / `per_session_usd` (`Decimal | None`, default
`None`); an optional `budget_checker` collaborator on `AgentLoop.__init__` (default `None`, the
assembler/hooks/summarizer pattern); per-session spend on the controller's `_Session`; built in
`_assemble`. Unset → the new turn-loop block is skipped → byte-identical.

**Rationale**: No breaking signature change; mirrors the proven default-off-collaborator plumbing.

## Decision 4 — Stop-after-overage + fail-soft (ADR 0005 D3/D4)

**Decision**: The cap terminates AFTER the turn that crossed it (total ≈ cap + one turn). When
`PricingTable.cost` returns `None` (unpriced model), the cap is not enforced for that turn + a
diagnostic is emitted (`emitter.diagnostic("warning", "budget", ...)`); never a crash/guess.

**Rationale**: USD is only post-turn knowable; fail-soft matches 053's pure-metadata stance + keeps
the unpriced surface specified, not hidden.

## Decision 5 — Model-id provenance; per-session reset on resume (ADR 0005 D5/D6)

**Decision**: The host supplies the model-id string (the `ModelBoundary` exposes none) alongside the
`PricingTable`. The per-session USD counter resets on `resume()` (records don't reconstruct
accumulated USD) — documented.

**Rationale**: The loop must not introspect the model id; resume-reset is the simplest honest v1.

## Decision 6 — The checker is a small pure value object

**Decision**: A small accumulator/checker (a running `Decimal` total + a `f(prior, turn_cost,
caps) -> exceeded` test) reusing `PricingTable.cost`. It lives where it does NOT make the loop
import the tools layer (pricing is a foundational package, not `loopplane.tools`) — confirm the
boundary audit stays green at implement.

**Rationale**: Pure + testable; reuse-first; keeps the loop's import boundary clean.

## Out of scope (deferred — ADR 0005 D7)

Phase C: a durable per-user-monthly USD ledger (cross-session atomic increments) — multi-tenant-
shaped, a later unit + ADR sequenced with Tier-4 G18/G19/G20.
