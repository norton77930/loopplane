# Data Model: Worker Drain Handoff

## Worker drain

- Lives on one `AdmissionCoordinator` instance.
- States: accepting (initial), draining.
- Transitions: `begin_drain` accepting → draining; `end_drain` draining → accepting.
- Repeating either transition leaves the flag as named.
- Not serialized, not stored, not shared across coordinators.

## Grant

Unchanged. `AdmissionGrant` fields, expiry, heartbeat, and holder fencing stay
as unit 085 defined them. Drain does not add a field.

## Invariants

- Draining and accepting are properties of the worker, not of the principal.
- A coordinator in the draining state creates no grant.
- A grant that was created before drain still heartbeats and releases.
- Two coordinators never hold live grants for the same principal. That rule
  stays in the store and is not reimplemented here.
