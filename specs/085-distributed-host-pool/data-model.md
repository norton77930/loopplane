# Phase 1 Data Model: Distributed Host Pool

Rules that govern every entity:

1. **A grant is a lease, not a session record.** It is never a checkpoint row, never
   an event payload, never content.
2. **HTTP and logs carry no grant internals.** Principal ids are already known to the
   authenticated caller; holder ids, grant ids, and store locations do not leave the
   serving layer.

## Configuration (host-supplied, not RuntimeConfig)

### `create_app(..., admission: AdmissionCoordinator | None = None)`

| Field | Default | Notes |
| ----- | ------- | ----- |
| `admission` | `None` | Absent → today's in-process 061/072 path (byte-identical). |

The coordinator is constructed by the embedder with a store, a holder id, and the
caps that must match the pool / fairness policy they already configured.

## Runtime seams (new — `loopplane.webapi.admission`)

### `AdmissionStore` (Protocol)

| Member | Shape | Responsibility |
| ------ | ----- | -------------- |
| `take(principal_id, holder_id, *, in_flight_cap, outstanding_cap, ttl)` | async → `AdmissionGrant` or raise `AdmissionRejected` | Atomically count non-expired grants for the principal; insert if under caps. Fail-closed on store errors. |
| `heartbeat(grant_id, holder_id, *, ttl)` | async → bool | Refresh expiry iff this holder still owns the grant. `False` means the grant is gone (expired or released). |
| `release(grant_id, holder_id)` | async | Idempotent. Succeeds when the grant is already absent. |

### `AdmissionCoordinator`

Wraps a store plus `holder_id` (opaque, generated once per worker). Caps are arguments
to `hold(principal_id, *, in_flight_cap, outstanding_cap=None)` — they are not
constructor policy. `hold` is an async context manager: take → heartbeat nursery →
release in `finally`. `bound_run` reads in-flight from `TenantHostPool.per_principal_in_flight`
and outstanding from the chosen host's fairness object. Local `in_flight` on
streaming/session applies only when admission is set (D8); `admission=None` keeps
the 061 wrap (`POST /runs` only).

### `AdmissionGrant`

| Field | Purpose |
| ----- | ------- |
| `grant_id` | Opaque id, single-use after release |
| `principal_id` | Existing authenticated principal |
| `holder_id` | Opaque worker identity (not a hostname) |
| `expires_at` | Absolute expiry; heartbeats move it forward |
| `reserves_outstanding` | Counts toward cluster outstanding cap when 072 is configured. In-flight count is the number of live grants. |

### `AdmissionRejected`

Raised on a failed take. `kind` is `conflict` (in-flight / ownership) or `capacity`
(outstanding-work). `str` / HTTP detail are the existing public-safe phrases only.

### `InMemoryAdmissionStore`

Process-lifetime maps + `anyio.Lock` per principal. Single-process-honest. Two
simulated workers share **one instance**.

### `PostgresAdmissionStore`

Optional. Requires `loopplane[postgres]`. Tables (names illustrative; exact SQL in
implementation):

- `admission_principals(principal_id TEXT PRIMARY KEY)` — row lock target
- `admission_grants(grant_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, holder_id TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, reserves_outstanding BOOLEAN NOT NULL)`

Take: insert principal row if needed → `SELECT … FOR UPDATE` → delete/ignore expired
→ count → insert grant or reject. DSN held, never logged.

## Local structures (unchanged)

| Entity | Change |
| ------ | ------ |
| `TenantHostPool` | Unchanged protocol. `in_flight` still the process-local semaphore. |
| `PlatformFairness` | Unchanged. Local outstanding + local `model_turn`. |
| `LoopPlaneHost._active` | Unchanged. |

## State transitions (per principal grant)

```text
absent --take (under cap)--> held
held --heartbeat--> held (expiry moved)
held --release--> absent
held --ttl elapsed without heartbeat--> expired (= absent for the next take)
take over cap --reject--> absent (caller sees AdmissionRejected)
take on store failure --reject--> absent (fail-closed)
```

Exactly one holder succeeds a concurrent take (US6). A stale heartbeat after release
returns false and does not resurrect the grant.
