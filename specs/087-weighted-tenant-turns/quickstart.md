# Quickstart: Validate Weighted Tenant Turns

After implementation, construct a `WeightedTurnPolicy` with tenant weights 3 and 1,
active cap 1 and consecutive cap 3. Share a `WeightedInMemoryTurnPermitStore` between
two `WeightedPlatformFairness` objects with matching `PlatformFairnessPolicy` caps.
Use the existing host `platform_fairness` seam. No new web argument is needed.

```python
from loopplane.fairness import PlatformFairnessPolicy
from loopplane.fairness_weighted import (
    WeightedInMemoryTurnPermitStore, WeightedPlatformFairness, WeightedTurnPolicy,
)

weights = WeightedTurnPolicy({"alice": 3, "bob": 1}, active_cap=1, consecutive_cap=3)
store = WeightedInMemoryTurnPermitStore(weights)
fairness = WeightedPlatformFairness(
    PlatformFairnessPolicy(max_outstanding_per_tenant=4,
                           max_active_model_calls=1, max_consecutive_starts=3),
    turn_permits=store,
)
```

Supply `fairness` to `RuntimeConfig(platform_fairness=fairness, ...)` alongside
your existing host configuration. The safety caps on both policies must match.

Run from the repository root:

```powershell
pytest tests/unit/test_weighted_tenant_turns.py tests/unit/test_weighted_tenant_postgres.py -q
pytest tests/unit/test_platform_fairness.py tests/unit/test_cluster_fair_turn.py tests/unit/test_webapi_admission.py -q
```

Expect exact complete-cycle shares under continuous queued demand and non-binding
caps; setting consecutive cap 1 must instead force two contenders to alternate.
Single-tenant demand must use available capacity without reserving idle credit.

For durable deployments use the existing postgres extra and the weighted Postgres
store from the contract. All workers must share configuration and coordination DB.
Memory stores in separate processes do not coordinate. The offline test result is
not proof of a live database deployment; live locking/load checks remain separate.

Rollback: drain the group and restore original `PlatformFairness` construction;
leave unused weighted state intact. No checkpoint or old permit migration is required.
