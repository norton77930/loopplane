# Quickstart: Cluster Fair Turn

Written against the design in [plan.md](plan.md) and
[contracts/cluster-fair-turn.md](contracts/cluster-fair-turn.md).
**ADR 0021 is Accepted.** Implement only after tasks/analyze; constructors below are the
target wiring.

## Default behaviour

Construct 072 fairness as today. No cluster view.

```python
from loopplane.fairness import PlatformFairness, PlatformFairnessPolicy

fairness = PlatformFairness(PlatformFairnessPolicy(max_outstanding_per_tenant=2))
```

## Enable cluster turns (in-memory)

Tests and a single process that should keep working if a second worker is added
later **in the same process**. Two `PlatformFairness` objects share **one store**.

```python
from loopplane.fairness import PlatformFairness, PlatformFairnessPolicy

store = InMemoryTurnPermitStore()  # name as shipped after ADR Accepted
left = PlatformFairness(policy, turn_permits=store)
right = PlatformFairness(policy, turn_permits=store)
```

Pass each fairness object into that worker's hosts via
`RuntimeConfig.platform_fairness` as today. Do not add a `create_app` argument.

## Enable cluster turns (Postgres)

Only after ADR 0021 Accepted, and only with `loopplane[postgres]`. Same honesty
bar as 085: DSN never logged; own tables; not an 085 grant table.

## Operator-visible failures

- Cluster permit store down during an already-admitted run: the run **continues**
  on the local 072 scheduler (no new HTTP status, no hang).
- 085 admission rejects are unchanged (409 / 429).

## What this does not do

- It does not move an in-flight run to another worker.
- It does not replace 085 ownership grants.
- It does not add weighted tiers.
- Sticky load-balancing is still a hint, never the fairness mechanism.

## Local validation (after implementation; after ADR Accepted)

```powershell
uv run pytest tests/unit/test_fairness_core.py tests/unit/test_webapi_admission.py -q
```

Expect: collaborator absent → existing 072 tests green; two simulated workers
sharing one store → both ready principals obtain a start; store error → run
still progresses.
