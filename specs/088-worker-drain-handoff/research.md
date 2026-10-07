# Research: Worker Drain Handoff

## Decision: per-coordinator flag, not a store record

**Rationale**: Drain means this process is leaving. The grant store is shared so
that peers can take over. Putting drain in the store would stop every worker.
**Alternatives considered**: a cluster-wide drain row (rejects the peers that
should take over); a new HTTP route (outward contract, refused by §E).

## Decision: refuse before `take`

**Rationale**: A grant created and then rejected would look like a held run and
block the peer. The check happens in the coordinator, before `store.take`.
**Alternatives considered**: reject inside the store (cannot see which worker is
draining); cancel the heartbeat of an in-flight hold (cuts off the active run,
which FR-003 forbids).

## Decision: reuse the capacity rejection

**Rationale**: `AdmissionRejected` has two public kinds. Conflict means a run is
already active, which is false when the worker is empty and only draining.
Capacity already means this admission path will not take the work. No third
kind is added, so the public phrase set stays closed.
**Alternatives considered**: a new `draining` kind and phrase (outward contract);
reuse conflict (tells the caller a run exists when it does not).

## Decision: mid-turn migration stays deferred

**Rationale**: Moving the in-progress turn needs a new termination reason or a
checkpoint schema change. Both are §E gates. The gap's "live run migration"
item is larger than one safe slice. This unit is the between-run handoff only.
**Alternatives considered**: set `context.cancellation` from admission (ends the
run as `cancelled` and still does not move the turn).
