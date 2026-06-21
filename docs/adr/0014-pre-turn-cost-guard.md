# ADR 0014: Pre-turn predictive cost guard

- **Status**: Accepted (2026-06-22)
- **Deciders**: LoopPlane maintainer (pre-settled on the roadmap board); spec 068
  (`pre-turn-cost-guard`).
- **Supersedes / superseded by**: Extends ADR 0005. Does not supersede ADR 0005 or ADR 0010.
- **Related**: Constitution **IV** (Agent Loop model-call boundary), **VI** (reuses the existing
  `budget-exceeded` event vocabulary), **VII** (public-safe diagnostics), **X** (default-off,
  testable, reversible). Builds on **053** pricing and **055** USD budget enforcement.

## Context

ADR 0005 intentionally enforced USD caps after each model turn because actual token usage is known
only when the model emits `TurnEnd.usage`. That is honest, but it means one expensive turn can exceed
a cap before the post-turn checker can stop the run. The roadmap board pre-settled a narrow
extension: add a pre-turn predictive estimate before the model call, fail open when the estimate is
incomplete, and reuse the existing `budget-exceeded` reason.

## Decision

- **D1 - Check after request assembly and before the model call.** The Agent Loop already creates a
  `ModelRequest` before calling `stream_turn`. The guard evaluates that request after assembly and
  before provider invocation.
- **D2 - Use a host-configured maximum output estimate.** Output usage is unknowable pre-call. The
  host supplies `pre_turn_max_output_tokens`; `None` disables the pre-turn guard.
- **D3 - Price the estimate through the existing PricingTable.** The estimate is modeled as
  `TokenUsage(input_tokens=<request estimate>, output_tokens=<configured max output>)` and priced
  with the existing host-supplied model id and `PricingTable`. Unknown price means fail-open.
- **D4 - Refuse only when a known local cap would be exceeded.** The pre-turn check compares the
  estimate against per-message and per-session remaining caps known inside `BudgetChecker`. Durable
  monthly predictive enforcement is deferred because it would require a ledger read/reservation
  policy beyond this unit.
- **D5 - Fail open on incomplete inputs.** Missing pricing, model id, max-output estimate, active
  cap, or usable request-token estimate allows the model call. A generic diagnostic may be emitted,
  but it must not include prompt text, private paths, raw prices, cap amounts, principals, tokens, or
  secrets.
- **D6 - Reuse `budget-exceeded`; no schema bump.** A pre-turn refusal is a budget stop, not a
  cancellation. It terminates with the existing `budget-exceeded` reason and does not change
  `SCHEMA_VERSION`.
- **D7 - No spend reservation.** The pre-turn decision is non-mutating. Actual spend is still
  recorded only after allowed model calls through the existing post-turn checker.

## Consequences

- Predictable single-turn overages can be stopped before incurring model cost when enough local
  information is available.
- Default behavior remains byte-identical; the feature is inactive unless the host opts in.
- A configured but incomplete guard never denies availability based on a guess.
- The existing post-turn checker remains authoritative and catches actual overages after allowed
  model calls.
- Durable monthly predictive enforcement remains a future design problem because reservation,
  rollback, and cross-process consistency are outside this unit.
