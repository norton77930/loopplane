# Feature Specification: Weighted Tenant Turns

**Feature Branch**: Existing `086-cluster-fair-turn`; no branch operation requested.
**Created**: 2026-09-07
**Status**: Draft
**Input**: Maintainer approved starting 087 tenant-weighted scheduling through Spec Kit.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Allocate model starts by weight (Priority: P1)

Operators assign relative weights to tenants sharing model capacity. Queuing more
requests must not multiply a tenant's entitlement.

**Why this priority**: Delivers the weighted-tier portion of G20.
**Independent Test**: Continuously queue weights 3:1 with consecutive limit 3;
observe 300:100 starts over 100 cycles, across one and multiple workers.

**Acceptance Scenarios**:

1. **Given** continuous demand at weights 3:1, **when** capacity is freed repeatedly,
   **then** starts follow those shares while configured safety limits permit them.
2. **Given** equal weights and ten times more queued requests from one tenant,
   **when** both remain ready, **then** shares remain equal, with FIFO per tenant.
3. **Given** one ready tenant, **when** capacity is available, **then** it proceeds
   without waiting or banking credit for absent tenants.

### User Story 2 - Preserve protection and existing deployments (Priority: P1)

Weighting must not bypass admission, outstanding-work, active-call or consecutive limits.

**Why this priority**: Prioritization must preserve resource protection.
**Independent Test**: Run 072/085/086 regressions unchanged and assert caps with weights.

**Acceptance Scenarios**:

1. **Given** no weighted opt-in, **when** work runs, **then** defaults, scheduling
   and errors remain unchanged.
2. **Given** weights 3:1 and consecutive limit 1, **when** both remain ready,
   **then** they alternate: the hard cap takes precedence over proportional shares.
3. **Given** active capacity 2, **when** requests wait, **then** two may overlap
   and a third waits until capacity is released.
4. **Given** an active principal, **when** another worker submits a second run,
   **then** existing admission rejection still applies regardless of weight.

### User Story 3 - Recover and prevent starvation (Priority: P1)

Cancellation and coordination failure must not wedge sessions or exclude small tenants.

**Why this priority**: Scheduling must survive partial failure.
**Independent Test**: Cancel queued/granted work, expire leases and inject outages;
remaining work progresses within bounded test deadlines.

**Acceptance Scenarios**:

1. **Given** ready weights 1:100 with non-binding consecutive cap, **when** 101
   opportunities pass, **then** the smaller tenant starts at least once.
2. **Given** queued or granted work is cancelled, **when** cleanup finishes,
   **then** its waiter/permit cannot prevent another start.
3. **Given** coordination cannot confirm a permit, **when** admitted work proceeds,
   **then** existing local fairness applies; cluster caps and shares are not guaranteed.
4. **Given** a tenant leaves and returns, **when** ready again, **then** it has no
   banked credit from inactivity.

### User Story 4 - Keep configuration operator-owned (Priority: P2)

Users cannot set weights through prompts or requests, or inspect other tenants' policies.

**Why this priority**: Prevents policy drift and disclosure.
**Independent Test**: Invalid/mismatched configurations fail before scheduling;
representations omit tenant maps and connection details.

**Acceptance Scenarios**:

1. **Given** integer weights 1..100, **when** configured, **then** they are accepted;
   unlisted tenants receive unit weight within the new opt-in mode.
2. **Given** boolean, zero, negative, fractional or over-limit weights, **when**
   configured, **then** validation fails with a value-independent message.
3. **Given** workers share a weighted domain, **when** weights or safety caps differ,
   **then** configuration fails rather than following whichever worker polls next.

### Edge Cases

- Concurrent same-tenant requests need distinct acquisition identities.
- Local queues must not hide ready tenants from shared selection.
- Shares count starts, not duration, tokens or cost; no time SLA is promised.
- Expired/cancelled waiters and grants must be reclaimed.
- Model-body errors propagate once without replay; full-cap polling consumes no credit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Weighting MUST be opt-in with old defaults/paths unchanged (US2).
- **FR-002**: Weights MUST apply per tenant, independent of backlog/worker count (US1).
- **FR-003**: Stable continuously ready tenants MUST receive proportional starts
  over complete cycles when safety limits do not bind (US1).
- **FR-004**: Active-call/consecutive limits MUST stay hard; document precedence (US2).
- **FR-005**: Scheduling MUST be work-conserving, FIFO per tenant, without idle credit (US1/3).
- **FR-006**: Positive weights MUST prevent starvation with stable readiness (US3).
- **FR-007**: Operator weights MUST be immutable integers 1..100, excluding booleans;
  unlisted tenants have unit weight in weighted mode (US4).
- **FR-008**: Shared-domain weight/cap mismatch MUST fail explicitly, without
  silently degrading to an unintended policy (US4).
- **FR-009**: All registered waiting tenants MUST be visible to shared selection,
  including several queued on one worker (US1).
- **FR-010**: Cancellation/expiry MUST reclaim work; acquisitions have distinct IDs (US3).
- **FR-011**: Coordination unavailability MUST degrade to existing local fairness;
  application errors propagate once without retry (US3).
- **FR-012**: 061/085 admission, ownership, outstanding-work and `_active` stay unchanged (US2).
- **FR-013**: No new dependencies/extras, Gateway stages, event/checkpoint schemas,
  HTTP resources, UI, pricing rules or existing default changes are permitted.
- **FR-014**: Errors/events/representations MUST omit tenant/weight maps,
  holder/permit identities and connection details (US4).
- **FR-015**: Validation MUST cover shares, defaults, multiple workers, cancellation,
  outages and offline durable contracts; report live database/load validation separately.

### Key Entities

- **Weight policy**: immutable operator-owned relative weights.
- **Scheduling domain**: workers sharing consistent weights and capacity.
- **Ready tenant**: tenant with registered eligible requests.
- **Request/permit**: ephemeral work/permission for one call, not session state or admission.
- **Scheduling balance**: transient entitlement discarded on departure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Stable 3:1 demand produces 300:100 starts over 100 full cycles with
  non-binding limits, across one and multiple workers.
- **SC-002**: Weight 1 gets service within 101 starts against weight 100;
  queue flooding does not increase entitlement.
- **SC-003**: All grants respect active/consecutive caps; two contenders alternate at cap 1.
- **SC-004**: Cancel/expiry/outage tests finish within deadlines without duplicate execution.
- **SC-005**: Existing scheduling/admission regressions pass unchanged; dependencies unchanged.

## Assumptions

- Maintainer authorized 087 via Spec Kit on 2026-09-07.
- Weight is start entitlement, not subscription, quota, execution time or strict priority.
- Integer bounds and unknown-tenant unit weight are new opt-in design assumptions.
- Configuration is static; live reconfiguration/migration, billing, Docker and
  remote execution are excluded.
- In-memory coordination is single-process only; durable multi-worker support uses
  the existing Postgres extra. No File/SQLite backend is added.
- Readiness means coordinator registration; unsubmitted work has no entitlement.
