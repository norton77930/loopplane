# Data Model: Cluster Fair Turn

Ephemeral turn permits. Not session records, not 085 ownership grants, not events.

## `TurnPermit`

| Field | Purpose |
| ----- | ------- |
| `permit_id` | Opaque id, single-use after release |
| `principal_id` | Existing authenticated principal |
| `holder_id` | Opaque worker identity |
| `expires_at` | Absolute expiry; heartbeats move it forward |

Counts toward cluster `max_active_model_calls`. Fair next-start selection uses live
permits plus a last-started principal, matching 072 `max_consecutive_starts`.

## `TurnPermitStore` (Protocol)

| Method | Shape | Notes |
| ------ | ----- | ----- |
| `take(principal_id, holder_id, *, active_cap, consecutive_cap, ttl)` | async | Grants one permit or waits/rejects per ADR (plan default: **wait** up to a bound then degrade — not a new HTTP status). Failures other than "not fair yet" degrade (D5). |
| `heartbeat(permit_id, holder_id, *, ttl)` | async → bool | `False` if missing, wrong holder, or expired. |
| `release(permit_id, holder_id)` | async | Idempotent. |

Exact wait-vs-reject at take time is an implementation detail inside `model_turn`
(already a blocking wait in 072). No new public exception is required if waiting
is internal.

## `PlatformFairness` constructor

Additive optional collaborator:

```text
PlatformFairness(policy, *, turn_permits: TurnPermitStore | None = None)
```

`None` → byte-identical 072. Present → local `model_turn` then cluster take around
the granted turn; store errors degrade to local-only.

Caps are read from `PlatformFairnessPolicy` (`max_active_model_calls`,
`max_consecutive_starts`), not duplicated on the store.

## `InMemoryTurnPermitStore`

Process-lifetime maps + lock. Single-process-honest. Two simulated workers /
two `PlatformFairness` objects share **one instance**.

## `PostgresTurnPermitStore` (optional)

Same extra and thread-bridge as 085/060. Own tables. DSN never echoed. Schema
created once at construct, not on every heartbeat.

## State transitions

```text
absent --take--> held --heartbeat--> held
held --release--> absent
held --ttl expiry--> absent
take error --> degrade (no permit; local 072 still holds)
```
