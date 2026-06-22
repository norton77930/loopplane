# Research: Platform Fairness

## Decision 1: Shared In-Process Fairness Collaborator

**Decision**: Implement a host-supplied in-process fairness collaborator that is
shared by the hosts created for tenants in the same process.

**Rationale**: Unit 061 intentionally kept per-tenant hosts isolated and
sequential. Fairness must coordinate across those hosts without relaxing
`LoopPlaneHost._active`, so a shared object above the tenant host pool is the
smallest boundary-preserving design.

**Alternatives considered**:

- Relax host `_active`: rejected because the host/session internals are not
  designed for concurrent runs on one host.
- Web route-only scheduling: rejected because model-call fairness must apply to
  model turns, including later turns in an interactive session.
- External queue or database scheduler: rejected because 072 is explicitly
  in-process only.

## Decision 2: Split Admission Quota From Model-Call Scheduling

**Decision**: Expose separate concepts for tenant admission quota and fair
model-turn permits.

**Rationale**: Quota excess should be rejected before work starts so web/API
callers receive a public-safe bounded response such as HTTP 429. Model-call
fairness should wait for a fair turn, not terminate an already-running session
with a new reason.

**Alternatives considered**:

- Reject inside the Agent Loop when a model turn is over quota: rejected because
  it would require mapping a quota refusal onto existing termination reasons in
  a misleading way or adding a new reason, both outside scope.
- Count only currently running model calls: rejected because FR-004 requires an
  outstanding-work quota broader than the existing in-flight run cap.

## Decision 3: Tenant Identity Is The Existing Principal Id

**Decision**: Use the authenticated principal id already threaded through the
web/API host, checkpoint metadata, and `_Session.principal_id`.

**Rationale**: Unit 022 established `Principal` as the tenant identity. Creating
a new tenant identity would add a second ownership model and risk mismatched
authorization.

**Alternatives considered**:

- Model-specific identity: rejected because the spec requires fairness scoped to
  the tenant, not the selected model.
- Session id: rejected because one tenant can hold many sessions and quota must
  apply across them.

## Decision 4: Deterministic Fair Scheduling Window

**Decision**: Use a deterministic in-process fair queue that rotates across
ready tenants and enforces a configurable consecutive-start window when another
tenant is waiting.

**Rationale**: This is easy to test offline, avoids starvation, and is enough to
close the P2 in-process G20 slice without introducing a weighted scheduler or a
new dependency.

**Alternatives considered**:

- Strict global FIFO: rejected because one tenant's burst can sit ahead of all
  later tenants.
- Weighted fair queuing: deferred because no weights or tier policy are in
  scope for 072.

## Decision 5: Public-Safe Failures Only

**Decision**: Quota and scheduler errors expose generic public-safe messages,
with no tenant ids, prompts, model ids, paths, amounts, raw exceptions, or
provider details.

**Rationale**: Fairness is on a shared multi-tenant path. Error detail can leak
tenant existence or deployment internals if it includes raw identities or state.

**Alternatives considered**:

- Detailed operator diagnostics in public responses: rejected by Constitution
  VII. Operator-only observability can be specified later if needed.

## Decision 6: ADR 0013 Materialized In This Plan Phase

**Decision**: Add `docs/adr/0013-platform-fairness.md`.

**Rationale**: The roadmap board marks ADR 0013 as pre-settled, but the file was
absent. Implementation needs a stable boundary document before tasks.

**Alternatives considered**:

- Proceed with only the spec: rejected because the board explicitly references
  ADR 0013 and the feature touches runtime boundary ownership.
