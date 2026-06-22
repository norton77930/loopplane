# Feature Specification: Platform Fairness

**Feature Branch**: `072-platform-fairness`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "072-platform-fairness (P2, gap G20 in-process
slice): add per-tenant quota beyond in-flight counts and in-process fair
model-call scheduling above the previously verified tenant host pool. The
distributed and cross-process fairness story remains deferred. ADR 0013 is
pre-settled by the roadmap board and must be materialized or reconciled during
planning."

## Boundary Note

Unit 061 gave each principal an isolated host so different tenants can run at
the same time, while each tenant's own host remains sequential. This unit closes
the next in-process fairness slice: when multiple tenants contend for model-call
capacity, one noisy tenant should not monopolize the platform, and operators
should be able to bound how much outstanding work one tenant can hold.

This unit does **not** add distributed coordination, cross-process fairness,
database-backed queues, or many-writer durability. It also does not change tool
authorization, runtime event vocabulary, content blocks, termination reasons, or
schema version. The roadmap board records ADR 0013 as the settled boundary
direction for this unit; if that ADR artifact is still absent at plan time, the
plan must materialize or reconcile that decision before implementation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fair Progress Across Active Tenants (Priority: P1)

A host operator enables platform fairness for a multi-tenant deployment. When
one tenant submits a burst of work while another tenant also has pending work,
the quieter tenant still makes timely progress instead of waiting behind the
entire burst.

**Why this priority**: Anti-noisy-neighbor scheduling is the primary value of
this unit. Unit 061 removed cross-tenant host serialization, but it did not
govern fair access to shared model-call capacity.

**Independent Test**: Can be tested offline by creating two tenants with queued
model-call work and constrained shared capacity, then asserting that both tenants
receive progress in a fair order and no tenant starves while it has pending work.

**Acceptance Scenarios**:

1. **Given** two tenants each have queued model-call work and shared capacity is
   constrained, **When** fairness is enabled, **Then** both tenants make progress
   before either tenant can monopolize all available turns.
2. **Given** one tenant has a much larger backlog than another tenant, **When**
   the smaller tenant has pending work, **Then** the smaller tenant's work starts
   within the configured fairness window.
3. **Given** only one tenant has pending work, **When** fairness is enabled,
   **Then** that tenant can use available capacity without artificial delay.

---

### User Story 2 - Bound One Tenant's Outstanding Work (Priority: P1)

A host operator configures per-tenant quotas beyond the existing in-flight run
cap. When a tenant exceeds its allowed outstanding work, excess work is rejected
or held out of the fair scheduler instead of consuming unbounded local resources.

**Why this priority**: Fair scheduling alone does not prevent a tenant from
filling local queues. Operators need a bounded per-tenant quota so bursty tenants
cannot exhaust memory or crowd out future work.

**Independent Test**: Can be tested offline by configuring a small tenant quota,
submitting work beyond that quota for one tenant, and verifying that the excess
is bounded while other tenants remain unaffected.

**Acceptance Scenarios**:

1. **Given** a tenant has reached its outstanding-work quota, **When** it submits
   additional work, **Then** the excess is rejected with a public-safe bounded
   response and does not enter the fair scheduler.
2. **Given** a tenant's work completes, fails, or is cancelled, **When** the
   tenant submits new work, **Then** the released quota can be reused.
3. **Given** tenant A is over quota, **When** tenant B submits work within quota,
   **Then** tenant B is unaffected by tenant A's overage.

---

### User Story 3 - Preserve Default Behavior And Boundaries (Priority: P1)

Existing deployments that do not configure platform fairness keep the current
tenant host pool behavior exactly. The feature is opt-in and stays above the
host/runtime boundaries already established by earlier units.

**Why this priority**: Fairness is operationally useful, but it must not change
single-tenant deployments, existing host semantics, tool authorization, or event
contracts unless explicitly configured.

**Independent Test**: Can be tested by running the existing tenant host pool and
web/API suites with fairness disabled and verifying expected outputs do not
change.

**Acceptance Scenarios**:

1. **Given** platform fairness is not configured, **When** tenants run through
   the web/API host, **Then** behavior matches the current tenant host pool
   behavior.
2. **Given** fairness is configured, **When** work is scheduled, **Then** the
   existing per-tenant host isolation and per-host sequential invariant remain
   intact.
3. **Given** fairness decisions occur, **When** runtime events are emitted,
   **Then** existing event types, content shapes, termination reasons, and schema
   version remain unchanged.

---

### User Story 4 - Fail Safely Under Scheduler Pressure (Priority: P2)

A host operator can rely on fairness controls to fail safely when capacity is
exhausted, inputs are malformed, or queued work is cancelled. Failures do not
leak private details and do not leave stale quota reservations.

**Why this priority**: Fairness controls sit on a shared serving path. They must
be predictable and recover cleanly when work is rejected, cancelled, or fails.

**Independent Test**: Can be tested by simulating quota rejection, cancellation,
and scheduler item failure, then verifying public-safe responses and released
reservations.

**Acceptance Scenarios**:

1. **Given** queued work is cancelled before it starts, **When** the scheduler
   observes the cancellation, **Then** quota reservations are released and later
   work can proceed.
2. **Given** a scheduled item fails, **When** the failure is reported, **Then**
   the response remains public-safe and later work for other tenants continues.

### Edge Cases

- Fairness enabled with a single active tenant: no artificial delay or deadlock.
- Tenant quota configured as zero or negative: rejected as invalid configuration.
- Tenant quota reached by queued work rather than running work: excess remains
  bounded.
- Work cancellation, client disconnect, or run failure: quota reservations are
  released exactly once.
- One tenant continuously submits work while another submits occasional work:
  the occasional tenant is not starved while within quota.
- Multiple model selections for the same tenant: fairness remains scoped to the
  tenant, not to a model-specific identity.
- Missing authenticated principal: existing default-deny authentication behavior
  applies before any fairness decision.
- Fairness disabled: existing behavior and tests remain unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an opt-in in-process fairness control for
  multi-tenant model-call work above the previously verified tenant host pool.
- **FR-002**: The fairness control MUST be default-off; without configuration,
  existing tenant host pool and single-host behavior MUST remain unchanged.
- **FR-003**: When fairness is enabled and multiple tenants have pending work,
  the system MUST schedule work so no tenant can starve another tenant that is
  within quota and has pending work.
- **FR-004**: The system MUST support a configurable per-tenant quota for
  outstanding work that is broader than the existing in-flight run cap.
- **FR-005**: When a tenant exceeds its configured quota, the system MUST bound
  the excess and return a public-safe response without admitting the excess work
  into the fair scheduler.
- **FR-006**: Quota reservations MUST be released when work completes, fails, or
  is cancelled, so a tenant is not permanently blocked by stale reservations.
- **FR-007**: Fairness MUST preserve the existing per-tenant host isolation and
  each host's sequential execution invariant.
- **FR-008**: Fairness decisions MUST NOT change tool resolution,
  authorization, execution, runtime event vocabulary, content block shapes,
  termination reasons, or schema version.
- **FR-009**: Scheduler and quota failures MUST be fail-safe and public-safe:
  they MUST NOT expose private paths, credentials, internal host names, raw
  exceptions, or other tenant data.
- **FR-010**: The feature MUST remain in-process only. Distributed fairness,
  cross-process coordination, external queues, and many-writer durability are
  out of scope for this unit.
- **FR-011**: The feature MUST include deterministic offline tests for fair
  progress, quota rejection and release, tenant isolation, default-unchanged
  behavior, cancellation/failure cleanup, and public-safety.

### Key Entities

- **Tenant**: The authenticated principal whose work is isolated, quota-bound,
  and scheduled fairly against other tenants.
- **Outstanding Work**: A tenant's accepted work that is queued, running, or
  otherwise reserving local capacity until completion, failure, or cancellation.
- **Fairness Policy**: The host-selected rules that determine when fairness is
  enabled, how tenants are ordered, and how much shared capacity is available.
- **Tenant Quota**: The operator-selected per-tenant bound for outstanding work
  admitted into the fairness layer.
- **Fair Scheduler State**: The in-process state needed to order pending tenant
  work and release reservations safely.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of covered two-tenant contention scenarios, both tenants
  make progress while each has pending work; no tenant receives more than the
  configured fairness window of consecutive starts when another tenant is ready.
- **SC-002**: In 100% of covered burst scenarios, a tenant with a smaller backlog
  starts work within one fairness scheduling cycle while it is within quota.
- **SC-003**: In 100% of covered quota scenarios, excess tenant work is bounded
  and does not enter scheduling; quota capacity is reusable after completion,
  failure, or cancellation.
- **SC-004**: With fairness disabled, existing tenant-host-pool and web/API
  behavior remains unchanged in all covered regression tests.
- **SC-005**: Public-safety scans over changed artifacts find no credentials,
  private paths, internal network details, raw backend errors, or other tenant
  data leakage.

## Assumptions

- Unit 061's per-principal host pool remains the isolation boundary for
  concurrent tenants; 072 adds an in-process fairness layer above it rather than
  relaxing host internals.
- ADR 0013 is pre-settled by the roadmap board as an in-process slice; the plan
  step must create or reconcile the ADR artifact if it is absent.
- Tenant identity is the authenticated principal id already used by the web/API
  host. Principal ids are opaque and public-safe.
- The per-tenant quota in this unit is a local outstanding-work bound, not a
  billing cap and not a distributed resource entitlement.
- Distributed fairness, cross-process queues, remote execution, many-writer
  durability, and global platform quota enforcement are deferred to a later
  direction.
