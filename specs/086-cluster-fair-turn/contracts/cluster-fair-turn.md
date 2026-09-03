# Contract: Cluster Fair Turn

Internal Python fairness collaborator. No new HTTP routes, event types,
content-block types, termination reasons, or schema bump. No `create_app`
signature change.

## Construction contract

`PlatformFairness(policy, *, turn_permits=None)`.

Required behaviour:

- Absent `turn_permits` leaves 072/085 / single-host behaviour unchanged
  (byte-identical).
- Present `turn_permits` is asked from `model_turn` after the local 072 grant.
- Not a `RuntimeConfig` field of its own; the fairness object is still supplied
  as `RuntimeConfig.platform_fairness`.
- Constructors do not log a DSN, holder id, or permit id.

## Permit contract

`TurnPermitStore.take / heartbeat / release` as in [data-model.md](../data-model.md).

Required behaviour:

- Success: exactly one cluster permit is held for the duration of the model turn.
- Two ready principals, consecutive-start cap 1: a burst of starts yields both
  principals at least one start.
- Only one principal ready: successive starts succeed (no wait for an absent peer).
- Store error / unreachable / missing extra on take: **degrade** to local 072;
  do not hang; do not fail the run solely because the cluster view is down.
- Exit (success, failure, cancellation): release exactly once.
- 085 admission scenarios unchanged: a second in-flight run at cap is still
  rejected.

## HTTP contract

None new. Turn waiting is internal to `model_turn`. Existing 409/429 phrases
remain 085/072 mappings.

## Public names

If a Postgres helper is exported, it is additive under the fairness or webapi
package and listed in `docs/api-reference.md` in the same change. The
`PlatformFairnessGate` Protocol (`admit` / `model_turn`) is unchanged.
