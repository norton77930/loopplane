# Data Model: Platform Fairness

## Tenant

- **Identity**: Existing authenticated principal id.
- **Stored in**: Existing session/checkpoint metadata and `RunContext` for
  runtime use.
- **Validation**: Missing identity follows existing authentication/default-deny
  behavior in the web/API host. Non-web hosts may omit tenant identity; fairness
  stays inert unless both fairness and tenant identity are present.

## Fairness Policy

- **Fields**:
  - `enabled`: derived from presence of a configured fairness gate/policy.
  - `max_outstanding_per_tenant`: positive integer tenant quota.
  - `max_consecutive_starts`: positive integer fairness window.
  - `max_active_model_calls`: positive integer shared in-process capacity.
- **Invariants**:
  - No field may be zero or negative when configured.
  - `None`/absent fairness is default-off and preserves current behavior.
  - Policy carries no secrets.

## Outstanding Work Reservation

- **Fields**:
  - `tenant_id`: opaque principal id held only in memory.
  - `released`: internal flag to guarantee exactly-once release.
- **Lifecycle**:
  1. Created before work is admitted.
  2. Counts against the tenant quota while queued, running, or waiting for a
     fair model turn.
  3. Released when work completes, fails, disconnects, or is cancelled.
- **Invariants**:
  - Release is idempotent.
  - A rejected reservation never enters the fair scheduler.

## Model-Turn Permit

- **Fields**:
  - `tenant_id`: opaque principal id.
  - `queue_position`: internal scheduler state, never exposed publicly.
  - `released`: internal flag for exactly-once active-capacity release.
- **Lifecycle**:
  1. Requested by `AgentLoop` after request assembly and before
     `ModelBoundary.stream_turn`.
  2. Waits until shared capacity and fairness order permit the tenant to start.
  3. Releases when the model stream ends, fails, or cancellation exits the turn.
- **Invariants**:
  - Cancellation while queued removes the request and releases reservations.
  - A single active tenant is not delayed artificially.
  - When another tenant is ready, no tenant can exceed the configured
    consecutive-start window.

## Fair Scheduler State

- **Fields**:
  - per-tenant outstanding counts
  - per-tenant pending model-turn queues
  - active model-call count
  - last-start tenant and consecutive-start count
- **Storage**: Process memory only.
- **Invariants**:
  - State is protected by an async-safe lock/condition.
  - State is rebuilt empty on process restart.
  - No prompt, content block, token, secret, path, or raw provider error is
    stored.
