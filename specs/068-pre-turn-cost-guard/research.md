# Research: Pre-Turn Cost Guard

## Decision: Reuse the existing BudgetChecker as the guard owner

**Rationale**: The checker already owns caps, pricing, model id, and per-message/per-session spend.
A pre-turn decision needs exactly that state plus an estimated next-turn cost. Keeping the decision
there avoids a second budget authority and keeps the loop limited to "ask checker, then terminate or
continue."

**Alternatives considered**:
- New standalone guard object in the loop: rejected because it would duplicate cap/pricing/spend
  state or require exposing too much checker internals.
- Governance decider stage: rejected because this is not a tool-call decision and it must run before
  the model call, not before Tool Gateway execution.

## Decision: Estimate request input tokens from the assembled ModelRequest

**Rationale**: The feature is explicitly "at assemble time". The existing prompt assembler already
has a deterministic local request-size estimate used for capacity checks. Extracting/reusing that
heuristic for a public helper keeps the estimate provider-free and offline.

**Alternatives considered**:
- Provider-native token counters: rejected for v1 because they add dependencies, provider
  branching, and possible network or SDK coupling.
- Counting only the new user prompt: rejected because tools, history, summaries, and output schema
  are part of the actual model request.

## Decision: Require a host-configured max-output estimate

**Rationale**: Output tokens are unknowable before the call. A host-owned scalar is explicit,
default-off, and reversible. It does not alter provider generation limits or infer provider behavior.

**Alternatives considered**:
- Reuse provider adapter max-output configuration automatically: rejected because not every model
  config exposes it through the core runtime and it may mean "limit" rather than "budget estimate".
- Guess a default output token count: rejected because it would violate fail-open/no-guessed-price
  semantics.

## Decision: Refuse only when a known in-memory cap would be exceeded

**Rationale**: Per-message and per-session remaining spend is locally known inside `BudgetChecker`.
The durable per-user-monthly cap would require a fresh ledger read or reservation before the model
call; that expands 063 and is outside this unit. Monthly prediction therefore fails open unless a
future unit adds a reservation/read contract.

**Alternatives considered**:
- Pre-read the monthly ledger before every model call: rejected because it changes durable ledger
  behavior and introduces an availability/consistency policy not specified for 068.
- Reserve estimated monthly spend before the call: rejected because rollback/refund semantics are a
  separate ledger design.

## Decision: Strict greater-than cap comparison

**Rationale**: 055 treats a cap as crossed when spend is greater than the cap. Reusing that rule
keeps equality allowed and avoids a semantic fork between pre-turn and post-turn checks.

**Alternatives considered**:
- Greater-than-or-equal refusal: rejected because it would be stricter than 055 and could refuse a
  turn whose estimated cost exactly matches remaining budget.

## Decision: Reuse budget-exceeded and keep the event schema unchanged

**Rationale**: Consumers already understand `budget-exceeded` from 055. A pre-turn budget refusal is
the same user-visible budget outcome; adding another reason would create unnecessary consumer work.

**Alternatives considered**:
- New `pre-turn-budget-exceeded` reason: rejected because it expands the event vocabulary without
  user value and contradicts the board.
- Reuse `cancelled`: rejected because cancellation has checkpoint/input-stranding semantics that do
  not represent a budget denial.
