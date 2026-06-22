# Contract: Platform Fairness

This contract is internal Python API plus web/API behavior. It intentionally
does not add runtime events, content block types, termination reasons, or
provider request fields.

## Runtime Configuration Contract

`RuntimeConfig` accepts an optional platform fairness policy/collaborator.

Required behavior:

- Absent fairness configuration leaves existing behavior unchanged.
- Invalid numeric policy values fail `validate_config()` with public-safe
  `ConfigError` messages.
- The configured collaborator is forwarded by `assemble()` to
  `RuntimeController` and then to each session's `AgentLoop`.
- Config objects do not contain credentials or private paths.

## Admission Contract

The fairness collaborator provides tenant quota admission for outstanding work.

Required behavior:

- `admit(tenant_id)` succeeds by returning an async context manager or
  reservation when the tenant is below quota.
- `admit(tenant_id)` rejects excess work before it enters the fair scheduler.
- Rejection is public-safe and maps to HTTP 429 in the web/API host.
- Reservation release is exactly-once and occurs on success, failure,
  cancellation, or disconnect cleanup.
- Other tenants are unaffected by one tenant's over-quota state.

## Model-Turn Contract

The fairness collaborator provides a model-turn permit used around
`ModelBoundary.stream_turn`.

Required behavior:

- `model_turn(tenant_id)` waits until the tenant may fairly start a model call.
- A single active tenant starts without fairness-induced delay.
- When multiple tenants are ready, ready tenants rotate fairly and no tenant
  exceeds the configured consecutive-start window while another is waiting.
- Cancellation while waiting removes the queued request and releases any held
  local state.
- Permit release happens when the model stream completes, raises, or is
  cancelled.

## Agent Loop Contract

Required behavior:

- `AgentLoop` checks the fairness model-turn permit after request assembly and
  before `ModelBoundary.stream_turn`.
- If fairness is absent or the run has no tenant identity, `AgentLoop` behaves
  as it does today.
- The loop does not change tool dispatch, event names, event payload schema,
  content block shapes, or termination reasons.

## Web/API Contract

Required behavior:

- `POST /v1/runs`, `POST /v1/runs/events`, and interactive session opening use
  tenant quota admission before work starts when fairness is configured.
- Quota excess returns the existing normalized error envelope with status 429
  and a generic detail such as `capacity exceeded`.
- Existing 409 "run already active" semantics remain for per-host sequential
  conflicts.
- The response must not reveal tenant ids, queue sizes, model ids, prompts,
  paths, raw exceptions, or provider details.

## Deferred Contracts

Not part of 072:

- Distributed fairness.
- Cross-process queues.
- Database-backed reservations.
- Many-writer durable ordering.
- Weighted tenant priorities.
- New runtime event schema or termination reason.
