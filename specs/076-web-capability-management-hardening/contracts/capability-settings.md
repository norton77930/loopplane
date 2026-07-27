# Contract: Capability Settings

## Purpose

Define the additive web-facing management contract for durable, owner-scoped capability settings. Existing 075 list and mutation endpoints remain compatible; this contract adds richer detail, scoping, action, durability, and mutation-gate behavior.

## Shared Rules

- Every request is authenticated and evaluated against the requesting principal.
- Owned resources are visible and mutable only by their owner.
- Shared host resources may be visible as read-only metadata.
- Non-owned private resources are omitted from lists and return a non-disclosing public-safe failure for direct access.
- Mutation responses use `CapabilityOperationResult`.
- Browser-originated requests must not contain provider credentials, API keys, secrets, tokens, or MCP authentication tokens.
- When mutation is disabled, list/detail endpoints remain available and mutation endpoints return a disabled public-safe result.
- Mutation and owner runtime activation are explicit, default-off host settings.
- Capability settings status is available from `GET /v1/capabilities/settings` without exposing host configuration internals.

## Capability View Fields

Capability list and detail views may include:

- `id`
- `name`
- `description`
- `status`
- `scope`: `owned` or `shared_read_only`
- `actions`: available actions for the current principal
- `updated_at`
- `problem`: optional public-safe status problem

## Memory Operations

- List memory entries visible to the principal.
- Get owned memory detail or allowed shared detail.
- Create or update owned memory.
- Delete owned memory with explicit confirmation.

Required behavior:

- Owned memory changes persist durably when durable storage is configured.
- Shared host memory cannot be overwritten or deleted through settings.
- Non-owner direct access does not reveal existence.

## Skill Operations

- List visible skills with validity and availability status.
- Get owned skill detail or allowed shared detail.
- Create or update owned skill.
- Import a valid skill definition.
- Delete owned skill with explicit confirmation.

Required behavior:

- Imported or edited valid skills become owner-visible and owner-available for later eligible sessions.
- Invalid skills show a public-safe problem and are not activated.
- Shared host skills are read-only.

## MCP Operations

- List visible MCP configurations.
- Get owned MCP configuration detail or allowed shared metadata.
- Add or update owned MCP configuration.
- Get owned MCP detail or allowed shared metadata.
- Reconnect owned MCP configuration.
- Delete owned MCP configuration with explicit confirmation.

Required behavior:

- Reconnect refreshes public-safe status and owner-visible tools.
- Failed reconnect stores a public-safe failure summary.
- Credential/token fields are rejected or ignored without persistence.
- Browser-managed stdio is refused without executing or persisting command/args.
- HTTP, SSE, and WebSocket endpoints require approval from a host-injected, default-deny endpoint policy.
- Shared host MCP configurations are read-only.

## Workspace Context Operations

- List visible workspace contexts.
- Get owned or allowed context detail.
- Create or update owned context.
- Delete owned context with explicit confirmation.
- Bind an owned session to an owned or allowed context.

Required behavior:

- Binding a context updates session metadata visible before the next turn.
- Non-owner context or session access fails without existence disclosure.

## Schedule Operations

- List owned schedules.
- Get owned schedule detail.
- Create or update owned schedule.
- Schedule writes may include an additive `instruction`; the settings UI requires it.
- Enable or disable owned schedule.
- Run owned schedule immediately.
- Delete owned schedule with explicit confirmation.

Required behavior:

- Disabled schedules cannot run now.
- Instruction-less schedules and hosts without an injected runner cannot run now.
- Enable and disable use additive `POST /schedules/{id}/enable` and `/schedules/{id}/disable` actions.
- Run-now status and failures are public-safe.
- Schedule state persists durably when durable storage is configured.

## Model Default Operations

- Get the principal's model default.
- Set the default to one model from the host catalog.
- Clear or fall back when the chosen model is no longer available.

Required behavior:

- Only host catalog entries can be selected.
- No provider credential fields are accepted or rendered.

## Failure Modes

- `disabled_by_policy`: mutation gate is off.
- `unavailable`: durable storage or target resource unavailable.
- `invalid`: request cannot be accepted.
- `read_only`: resource is shared and cannot be mutated.
- `failed`: reconnect or run-now failed with public-safe details.

All failure messages are public-safe.
