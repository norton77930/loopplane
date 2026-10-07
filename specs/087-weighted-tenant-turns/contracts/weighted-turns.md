# Library Contract: Weighted Tenant Turns

New imports live in `loopplane.fairness_weighted`:

- `WeightedTurnPolicy(weights, *, active_cap, consecutive_cap)`
- `WeightedTurnPermitStore`: `policy`, and 086-compatible `take`, `heartbeat`, `release`.
- `WeightedInMemoryTurnPermitStore(policy, *, clock=None)`
- `WeightedPlatformFairness(policy, *, turn_permits)` where policy is the existing
  `PlatformFairnessPolicy` and the collaborator implements the weighted protocol.

`loopplane.fairness_weighted_postgres` exports
`WeightedPostgresTurnPermitStore(conninfo, *, policy)`. Construction creates/checks
the dedicated coordination row, with safe configuration mismatch errors. Missing
psycopg produces an install hint for the existing postgres extra. No new dependency.

Fairness keeps public `admit`, `model_turn`, `max_outstanding_per_tenant` shapes.
It passes existing active/consecutive caps, which must equal store policy values.
No `create_app` argument is added; supply the object through existing
`RuntimeConfig.platform_fairness`. Original defaults and constructors are unchanged.

`take` waits while capacity is busy, returns one distinct permit, or raises typed
`TurnPermitUnavailable`. Invalid/mismatched configuration raises ValueError and is
not an outage. Heartbeat returns false for missing/wrong-holder/expired permits;
release is idempotent. Cancellation cleanup is shielded and removes only that request.

Shares apply only to registered ready tenants with non-binding consecutive limits.
Admission and active-call bounds remain hard. Outage fallback preserves local
protection but loses cluster/weighted guarantees. The model body is yielded once.

Activation: stop/drain the group; configure identical policy and weighted stores
for all workers; restart. Legacy and weighted SQL state are isolated domains and
must not be mixed as though sharing one cap. Static-policy replacement is a separate
operator lifecycle task; this feature does not silently rewrite existing policy.
