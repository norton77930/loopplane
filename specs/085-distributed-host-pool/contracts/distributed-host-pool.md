# Contract: Distributed Host Pool

Internal Python serving-layer API plus existing web/API HTTP behavior. No new
routes, no new event types, no content-block types, no termination reasons, no
schema bump.

## Construction contract

`create_app` accepts an optional `admission` collaborator.

Required behavior:

- Absent `admission` leaves existing pool / fairness / single-host behavior
  unchanged (byte-identical).
- Present `admission` is asked **before** `host.run` / `run_event_stream` drive /
  `run_session` drive on every run-start path.
- The collaborator is not a `RuntimeConfig` field.
- Config and constructors do not log a DSN, holder id, or grant id.

## Admit contract

`AdmissionCoordinator.hold(principal_id, *, in_flight_cap, outstanding_cap=None)`
returns an async context manager.

Required behavior:

- Success: exactly one cluster grant is held for the duration of the `async with`.
- Same principal, in-flight cap exhausted across the worker group: reject with
  `AdmissionRejected(kind="conflict")` → HTTP 409 `a run is already active`.
- Same principal, outstanding cap exhausted (when `outstanding_cap` is set):
  reject with `AdmissionRejected(kind="capacity")` → HTTP 429 `capacity exceeded`.
- Different principals: concurrent holds succeed.
- Store error / unreachable / missing extra on take: same reject as capacity or
  conflict using the public-safe phrases; **no** uncoordinated fallback.
- Exit (success, failure, cancellation): release exactly once.
- Heartbeat runs while held; a holder whose grant has expired cannot refresh it
  back into existence.

## Pool and fairness contract

- `TenantHostPool.in_flight` remains the process-local reject-not-block semaphore.
- `PlatformFairness.admit` / `model_turn` remain in-process.
- Cluster grants are strictly tighter or equal; they never loosen a local cap.
- `_active` on a host is unchanged.

## HTTP contract (existing phrases only)

| Situation | Status | `detail` |
| --------- | ------ | -------- |
| Cluster in-flight / ownership conflict | 409 | `a run is already active` |
| Cluster outstanding overage | 429 | `capacity exceeded` |
| Local 072 overage (unchanged) | 429 | `capacity exceeded` |
| Local host `_active` (unchanged) | 409 | `a run is already active` |

SSE error frames on `POST /runs/events` use the same phrases. No new `event:`
names.

## Store contract

- In-memory: two coordinators sharing one store enforce the same caps as two
  workers.
- Postgres: concurrent takes across processes yield exactly one winner; a
  release cannot be lost to a stale write.
- `repr` / `str` of stores and grants never include a DSN or token-shaped value.

## Out of contract

New REST resources, Event Bus fields, Gateway SPI changes, File/SQLite admission
backends, cluster-wide turn interleaving, run migration.
