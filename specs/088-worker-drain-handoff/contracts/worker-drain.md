# Contract: Worker Drain Handoff

The coordinator methods are in-process. There is no new HTTP route.

## `begin_drain()` / `end_drain()`

- `begin_drain` makes later `hold` calls on this coordinator refuse.
- `end_drain` restores acceptance.
- Neither method talks to the store and neither returns grant data.
- `repr` and `str` stay `AdmissionCoordinator()`.

## `hold` while draining

- If the coordinator is draining at the start of `hold`, raise
  `AdmissionRejected("capacity")` and do not call `take`.
- The public mapping remains HTTP 429 and `capacity exceeded` for callers that
  already map admission kinds. No new phrase.
- A `hold` that passed the check keeps its current body, heartbeat, and release
  behavior even if `begin_drain` runs while the body is inside the context.

## Peers

- Another coordinator on the same store, left in the accepting state, uses the
  unchanged take rules.
- It receives the existing conflict while the draining worker's grant is live.
- It receives a grant after that grant is released.
