# Research: Weighted Tenant Turns

Repository evidence: `fairness.py`, `fairness_permits.py`, `fairness_postgres.py`,
086 tests and ADR 0021. One independent read-only research agent checked the design.

## R1 - Share semantics versus caps

Decision: smooth weighted round robin over distinct ready tenants, not requests.
Existing consecutive cap wins; cap 1 forces two contenders to 1:1. Cap-forced
selection bounds score magnitude to one total-weight range so impossible ratios
cannot accumulate unlimited credit. Non-binding-cap cycles preserve exact ratios.
Alternatives: multiply the cap by weight (weakens protection); strict priority
(starves small tenants); weight individual waiters (rewards flooding).

## R2 - Queue visibility and API isolation

Decision: new explicit `WeightedPlatformFairness`, composing the existing public
fairness object's public admission seam. A private local guard retains 072
FIFO/consecutive selection with shielded lease cleanup. Shared weighted acquisition
precedes that local guard; reusing the old turn context would inherit its cancellation
cleanup behavior instead of satisfying the new lifecycle contract.
Legacy `PlatformFairness` remains untouched. Use a fresh holder for every acquisition.
Rationale: local-first hides tenants behind a local slot; 086 Postgres matches a
grant by tenant/holder, so shared holders can alias concurrent calls.
Alternative: modify existing constructor/order for all users (unnecessary regression risk).

## R3 - Shared state and policy coherence

Decision: immutable `WeightedTurnPolicy` includes tenant weights and the two model
start caps. The fairness wrapper verifies these equal its existing local policy.
The durable row stores canonical policy plus queue, permits and scores, all under
one row lock. Separate SQL namespace avoids 086's whole-table save touching 087.
Mismatched configurations raise a safe ValueError and never trigger degradation.
No rolling mix with 086 workers; stop/drain/restart a whole scheduling domain.

## R4 - Cancellation, expiry and unavailable coordination

Decision: every operation prunes expired permits/waiters; pending requests renew
their waiting lease while polling. All state mutation is serialized. Acquisition
uses a stable unique holder, cancellation cleanup is shielded, and granted work
uses heartbeat plus shielded release. Catch unavailability only around acquisition,
never around a yielded model body. Ordinary application exceptions propagate once.
Alternative: reuse 086 hold/degrade wrapper (its catch scope and cleanup semantics
do not establish the stronger new lifecycle properties).

## R5 - Validation honesty

Decision: deterministic queue-level ratio tests plus actual async fairness and
multi-store tests. Offline SQL fixture models commit/rollback and persistence;
it does not establish live Postgres locking/performance. Do not claim live validation.
All other changes remain within this unit; preexisting defects are not batch-remediated.
