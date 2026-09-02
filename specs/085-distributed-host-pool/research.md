# Phase 0 Research: Distributed Host Pool

All findings below were verified against this working tree on 2026-09-02. Nothing here
is inferred from documentation alone.

## R1 — 061/072 guarantees are process-local

`src/loopplane/webapi/pool.py` `TenantHostPool` stores hosts in a process dict keyed by
`(principal_id, model)` and bounds in-flight with `anyio.Semaphore` keyed by
`principal_id` only. Exceeding the cap **rejects** (`RuntimeError`), it does not block.

`src/loopplane/fairness.py` `PlatformFairness` keeps `_outstanding` in a
`defaultdict` behind an `anyio.Lock`. `admit` raises `PlatformFairnessRejected("capacity
exceeded")`. `model_turn` is the in-process fair scheduler.

Two workers therefore have two independent dictionaries. That is the G20 hole.

**Decision**: 085 adds a cluster-scoped grant in front of those local structures; it
does not replace them (defense in depth) and does not relax `_active`.

## R2 — Mechanism fork (spec FR-020)

| Fork | What it is | Verdict |
| ---- | ---------- | ------- |
| **A** shared admission collaborator + store Protocol | Workers take/release a grant before driving a run | **Chosen** (ADR 0020 D1) |
| **B** sticky load-balancer only | Ops routing so a principal always hits one worker | Rejected as sole mechanism — a mis-route is then a double-run |
| **C** new queue/lock extra (Redis, etc.) | External product | GATE-§E; rejected |

**Alternative considered**: put the grant inside `LoopPlaneHost` / relax `_active`.
Rejected by ADR 0009 D4; the host's per-run state is not concurrency-safe.

## R3 — Where the seam lives

webapi allowed deps (`TARGET` §3): host public surface, commands, events, FastAPI.
`TenantHostPool` already lives in `loopplane.webapi`. `PlatformFairness` lives in
`loopplane.fairness` and is consulted *inside* `RuntimeController.drive` (`admit`) and
`AgentLoop` (`model_turn`). fairness MUST NOT import webapi.

**Decision**: new modules under `loopplane.webapi.admission` (Protocol, in-memory store,
optional Postgres store, `AdmissionRejected`). The router/stream/session drive paths
call it. fairness stays in-process and is unchanged except that cluster outstanding is
reserved *before* `host.run` so a 072 local reject still releases the grant.

A new top-level `loopplane.admission` package was rejected for this unit: only the
web/API host is scaled as multiple workers; Desktop/CLI stay single-process; a new
TARGET block and import-matrix row would be premature.

## R4 — Storage honesty

062/060 already document: Postgres `ON CONFLICT` / row locks are cross-process-atomic;
File/SQLite are single-process-honest. Shipping File/SQLite *admission* backends would
look like a multi-worker fix while remaining process-local — the bug this unit closes.

**Decision**: in-memory default (tests share one object across two simulated workers) +
optional `PostgresAdmissionStore` via existing `loopplane[postgres]`, lazy psycopg,
`anyio.to_thread` (ADR 0008). No File/SQLite admission backend. No new extra. DSN never
echoed.

Take serializes per principal (`SELECT … FOR UPDATE` on a principal lock row, then
count non-expired grants, then insert). Heartbeat updates `expires_at` only for the
matching `(grant_id, holder_id)`.

## R5 — Call sites today

Verified production uses of `host_pool.in_flight`:

- `POST /runs` in `webapi/routers/interaction.py` — **yes**
- `POST /runs/events` → `run_event_stream` — **no**
- interactive `run_session` — **no**

All three map `PlatformFairnessRejected` → 429 `capacity exceeded` and other
`RuntimeError` → 409 `a run is already active`.

**Decision** (ADR 0020 D8): cluster admission wraps **every** run-start path. A helper
context manager is the single chokepoint so a fourth path cannot forget it. Local
`in_flight` stays on `POST /runs` and is added beside the helper on the other two
paths so the process-local cap is not bypassed either — that is 085 wiring, not a
retro-edit of 061's Verified tasks.

## R6 — Fail-closed and HTTP language

A false admit is a double-run. A false reject is availability. Control-plane default
is fail-closed (spec FR-010).

**Decision**: store errors on take → `AdmissionRejected` with a public-safe kind
(`conflict` or `capacity`), never a raw driver message. Mapping: conflict → 409
`a run is already active`; capacity → 429 `capacity exceeded`. Catch
`AdmissionRejected` **before** the broad `RuntimeError` handler.

## R7 — Caps and identity

061 in-flight is per `principal_id` (semaphore key), not per `(principal, model)` host
entry. 072 outstanding is per tenant id (= principal).

**Decision**: grants are per principal. `hold(principal_id, *, in_flight_cap,
outstanding_cap=None, holder_id)` uses the pool's in-flight cap and, when 072 is
configured, `PlatformFairnessPolicy.max_outstanding_per_tenant`. No
`RuntimeConfig` field.

## R8 — Liveness

Agent runs can last longer than a short TTL. A TTL with no heartbeat pins a live run
into expiry (double-run with a still-alive holder). A TTL with no expiry pins a dead
worker forever.

**Decision**: grant TTL + heartbeat from the admit context manager (refresh at a
fraction of TTL). Release on `finally`. Expiry of a grant the holder no longer
heartbeats allows a take. A heartbeat for a grant the store no longer holds is a
no-op (the run should then fail closed on the next refresh if we require a live
grant — implementation keeps the run going only while heartbeat succeeds; if the
grant was stolen after expiry, heartbeat fails and the worker stops admitting
*further* work for that principal on that grant; an already-running model turn is
not aborted mid-token — stop after the current `host.run` returns. Research note:
do **not** kill an in-flight Gateway call; the fencing is at admit/heartbeat, not
inside the Gateway.)

**Clarified for implement**: heartbeat failure mid-run does not invoke the Gateway
or cancel the tool; the context manager's exit still attempts release. A second
worker that took over after expiry may run concurrently with a *zombie* first run
that has not yet returned — this is the remaining fencing window. Mitigate with a
TTL long enough for a turn plus heartbeat period shorter than TTL/3. Document in
quickstart; do not add a new event or cancellation reason (VI).

## R9 — Tests without a live cluster

**Decision**: two `AdmissionCoordinator` users (simulated workers) sharing one
`InMemoryAdmissionStore`. Postgres tests follow the 060/062 stub pattern (`pg_stub`
or the existing contract suite style), not a required live server for the default
gate.

## R10 — No new dependency

`anyio` is already a base dep. `psycopg` is already the `postgres` extra. Nothing
else.

**Decision**: FR-014 holds. Any new library is a GATE-§E stop.
