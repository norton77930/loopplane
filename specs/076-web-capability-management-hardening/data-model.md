# Data Model: Web Capability Management Hardening

## Capability Scope

Represents whether a capability is mutable by the current principal.

- `owner_id`: principal that owns a mutable resource, or absent for shared host resources.
- `visibility`: owned, shared_read_only, or unavailable.
- `actions`: public-safe list of actions currently available to the requesting user.

Validation rules:

- Non-owned private resources are omitted rather than marked unavailable.
- Shared host resources may be listed only when their metadata is public-safe.
- Mutation actions are absent when the mutation gate is disabled.

## Capability Settings State

Durable per-principal settings record containing the mutable capability resources owned by that principal.

- `principal_id`: owner identity.
- `memory`: owned memory summaries and content.
- `skills`: owned skill definitions and validation state.
- `mcp`: owned MCP configuration records and latest public-safe connection status.
- `contexts`: owned workspace context records.
- `schedules`: owned schedule records.
- `model_default`: optional selected model from the host catalog.
- `updated_at`: last settings update timestamp.
- Durable document location: `StorageConfig.root/capabilities/v1/<principal-hash>.json`.
- `schema_version`: private capability-store schema version, initially `1`.

Validation rules:

- Records must be stored without provider credentials, MCP auth tokens, API keys, private paths, or raw stack traces.
- Resource identifiers are stable within a principal scope.
- Durable write failures produce public-safe operation failures.
- Writes use same-directory atomic replacement and a process-local lock keyed by the resolved document path.

## Memory Entry

User-owned agent memory available to the owner in later eligible sessions.

- `id`, `name`, `kind`, `description`, `snippet`, `content`, `status`, `updated_at`.
- `scope`: owned or shared_read_only.

Validation rules:

- Owned entries require non-empty name and content.
- Shared entries expose metadata only unless already readable by host policy.
- Owned entries cannot overwrite shared host entries.

## Skill

User-owned or shared host-provided agent skill.

- `id`, `name`, `description`, `instructions`, `source`, `status`, `problem`, `updated_at`.
- `scope`: owned or shared_read_only.

Validation rules:

- Imported or edited skills require a valid name, description, and instructions.
- Invalid skills persist a public-safe problem and are not activated for runtime use.
- Non-owner sessions cannot see or execute owned skills.

## MCP Configuration

User-owned or shared host-provided MCP capability connection.

- `id`, `name`, `transport`, `public_endpoint_label`, `status`, `tool_count`, `tools`, `problem`, `updated_at`.
- Editable connection fields needed for reconnect, excluding credentials/tokens.
- `scope`: owned or shared_read_only.

Validation rules:

- Stdio configurations require command metadata; network transports require a public-safe endpoint label or URL accepted by host policy.
- Browser requests cannot include credential/token fields.
- Browser-managed transports are HTTP, SSE, and WebSocket only; stdio command/args are neither executed nor persisted.
- Network endpoints must be accepted by the host-injected endpoint policy before save or reconnect; absence of a policy is deny.
- Reconnect stores only public-safe failure summaries.
- Shared MCP configurations cannot be edited or deleted by users.

## Workspace Context

User-owned workspace/project context that can be bound to owned sessions.

- `id`, `name`, `description`, `workspace_label`, `status`, `updated_at`.
- `scope`: owned or allowed shared read-only.

Validation rules:

- Name and workspace label are required.
- Only owner-visible contexts can be bound to owner-visible sessions.
- Binding a deleted or non-owned context fails without existence disclosure.

## Session Context Binding

Association between a session and a workspace context.

- `session_id`, `context_id`, `name`, `workspace_label`, `status`.

Validation rules:

- A session may have at most one active context.
- Binding requires the requesting principal to own the session.
- Session summaries expose only the bound context metadata allowed for that principal.

## Schedule

User-owned saved schedule configuration.

- `id`, `name`, `description`, `trigger`, `instruction`, `enabled`, `status`, `next_run_at`, `last_run_at`, `problem`, `updated_at`.

Validation rules:

- Name and trigger are required.
- Disabled schedules cannot run now.
- Instruction-less schedules and hosts without an injected runner cannot run now.
- Run-now dispatches once through the host runner; periodic trigger execution remains outside this settings store.
- Run-now failures are public-safe and do not expose internal scheduler details.
- Schedules are scoped to their owner.

## Model Default

User-owned default model preference selected from the host catalog.

- `model_id`, `label`, `status`, `updated_at`.

Validation rules:

- The selected model must exist in the host catalog at selection time.
- If the selected model later disappears, the default reports fallback/unavailable without exposing provider details.
- Browser UI renders catalog choices only and never credential fields.

## Capability Operation Result

Public-safe result returned by mutation, reconnect, bind, run-now, enable/disable, or default-selection operations.

- `ok`: whether the requested operation succeeded.
- `resource_id`: public-safe resource identifier when safe to disclose.
- `status`: available, connected, disconnected, deleted, disabled, enabled, failed, fallback, invalid, read_only, running, unavailable, or disabled_by_policy.
- `message`: public-safe user-facing summary.

Validation rules:

- Non-owner failures do not reveal existence.
- Messages never include raw paths, stack traces, credentials, tokens, private hostnames, or private implementation names.
