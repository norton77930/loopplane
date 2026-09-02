# Quickstart: Distributed Host Pool

Written against the design in [plan.md](plan.md) and
[contracts/](contracts/distributed-host-pool.md). ADR 0020 is Accepted.

## Default behavior

Do not pass `admission`. One process, one pool (or one shared host), today's 061/072
behavior.

```python
from loopplane.webapi import create_app, TenantHostPool

app = create_app(host=host, host_pool=pool)  # admission omitted
```

## Enable cross-process admission (in-memory)

Use this for tests and for a single worker that should keep working if a second
worker is added later **in the same process** (the in-memory store is not
cross-process). Two workers in one test share **one store**.

```python
from loopplane.webapi.admission import (
    AdmissionCoordinator,
    InMemoryAdmissionStore,
)

store = InMemoryAdmissionStore()
admission = AdmissionCoordinator(store)  # holder_id generated
app = create_app(host=host, host_pool=pool, admission=admission)
```

## Enable cross-process admission (Postgres)

Multi-worker production. Same DSN as other `loopplane[postgres]` stores is fine;
admission uses its own tables. The DSN is never logged.

```python
from loopplane.webapi.admission import (
    AdmissionCoordinator,
    PostgresAdmissionStore,
)

store = PostgresAdmissionStore(conninfo)  # requires loopplane[postgres]
admission = AdmissionCoordinator(store)
app = create_app(host=host, host_pool=pool, admission=admission)
```

If 072 fairness is also configured on the host, cluster outstanding-work uses
`max_outstanding_per_tenant` from that object. The fair *turn* scheduler stays
local to each worker. Do not copy the number onto the coordinator.

## Operator-visible failures

- Second overlapping run for the same principal on another worker: **409**
  `a run is already active`.
- Outstanding-work quota already full across the group: **429** `capacity exceeded`.
- Admission store down: new runs **409/429** with those same phrases (fail-closed),
  not a silent uncoordinated start.

## What this does not do

- It does not move an in-flight run to another worker.
- It does not make 072's turn scheduler cluster-wide.
- It does not make File/SQLite a multi-worker store.
- Sticky load-balancing is still a useful hint, never the enforcement.

## Local validation (after implementation)

```powershell
uv run pytest tests/unit/test_webapi_admission.py tests/unit/test_tenant_host_pool.py -q
```

Expect two simulated workers sharing one in-memory store: same-principal second
admit rejected; two principals concurrent; default `admission=None` path unchanged.
