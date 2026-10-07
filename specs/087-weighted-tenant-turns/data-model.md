# Data Model: Weighted Tenant Turns

- `WeightedTurnPolicy(weights, *, active_cap, consecutive_cap)`: frozen copied mapping
  of nonempty tenant strings to integer 1..100 weights; caps are positive integers
  excluding booleans. Unknown tenants use 1. Safe repr hides map contents.
- `WeightedTurnPermitStore`: existing take/heartbeat/release shapes plus read-only
  policy property. `take` rejects caps inconsistent with its bound policy.
- Request: unique request/holder id, tenant, waiting-lease expiry, permit TTL.
- Permit: existing public `TurnPermit` with unique identity and absolute expiry.
- State: FIFO request sequence, live permits, ready-tenant integer scores,
  last-started tenant and consecutive count. No idle tenant credit is retained.
- Durable row: fixed key, canonical policy text, serialized state text. Dedicated
  weighted table; no 086, admission, session or checkpoint table is rewritten.

Transitions: register -> pending -> granted -> released/expired. Cancellation removes
both pending request and any grant owned by its unique holder. Repeated polling
returns that acquisition's existing live grant, never another call's grant. Only
grants mutate score/last-start counters. Heartbeats extend live leases, never revive.

Every durable operation loads, mutates and saves while holding the same row lock,
including heartbeat, so a stale snapshot cannot erase a concurrent renewal.
