# Data Model: Web Capability Delivery Remediation

## Managed MCP Endpoint

A structurally safe endpoint for one owner-managed network MCP configuration.

### Fields

- `transport`: `http`, `sse`, or `websocket`
- `endpoint`: non-empty network URL
- `principal_id`: owner used by the host approval policy
- `configuration_id`: owner-scoped stable identifier

### Validation

- HTTP/SSE schemes: `http` or `https`
- WebSocket schemes: `ws` or `wss`
- Host is required
- Userinfo, query, and fragment are forbidden
- Browser-managed stdio is forbidden
- Invalid port syntax and transport/scheme mismatch are forbidden
- Structural validity never substitutes for host endpoint-policy approval

### State transitions

```text
new/update -> disconnected -> reconnecting -> connected
                                      |-> failed
invalid endpoint/policy -> invalid
update/delete/failure while active -> adapter retired
```

Stored legacy records may be read for safe listing or deletion, but cannot connect if they fail current structural validation.

## Scoped Adapter Lifecycle

The Gateway-owned runtime entry for one `(principal_id, adapter_id)` pair.

### States

- `active`: visible to new owner-scoped resolution
- `retired_with_leases`: invisible to new resolution; one or more invocations may finish
- `retired_ready`: invisible and no remaining leases
- `closed`: shutdown completed exactly once

### Transitions

- Successful reconnect replaces the current active entry and retires the previous entry.
- Successful update/delete and every terminal reconnect failure remove the active entry and retire it.
- Lease release moves a retired entry to closed when the final invocation ends.
- Operations for one principal never mutate another principal's lifecycle state.

## Allowed Workspace Context

A host-owned, read-only context projection visible to one principal.

### Safe fields

- `id`
- `name`
- `description`
- `workspace_label`
- `updated_at`

### Forced projection fields

- `scope = shared_read_only`
- `status = read_only`
- `actions = (open)` when mutation is disabled
- `actions = (open, bind)` when mutation is enabled
- `owner_id = null`
- `problem = null`

Provider-supplied scope, actions, owner identity, status, and problem fields are ignored.

### Collision rules

- Duplicate provider IDs are invalid and excluded.
- Provider IDs colliding with owned IDs are invalid and excluded from all operations.
- Invalid or unauthorized IDs follow the same not-found behavior as unknown IDs.
- Provider failure removes only the allowed contribution; owned durable contexts remain available.

## Shared Capability Detail Projection

A bounded read-only projection for host-provided resources.

### Memory

- Allow only `id`, `name`, `kind`, `description`, `snippet`, `status`, `updated_at`, `scope`, `actions`, and a public-safe `problem` value.
- `snippet` is the first at most 160 Unicode code points of the shared body, with no hidden suffix or nested metadata copied into the projection.
- The shape-preserving `content` field is the empty string and is not displayed.

### Skill

- Allow only `id`, `name`, `description`, `source`, `status`, `updated_at`, `scope`, `actions`, and a public-safe `problem` value.
- The shape-preserving `instructions` field is the empty string and is not displayed.

### MCP

- Allow only `id`, `name`, `transport`, safe `status`, `tool_count`, safe `tools`, `updated_at`, `scope`, `actions`, and a public-safe `problem` value.
- URL, authentication material, owner identity, private paths, nested provider metadata, and raw connection errors are absent.

### Workspace Context

- Include only the safe allowed-context fields and action projection above; no nested provider metadata is copied.

## Delivery Ownership Bucket

A review-only classification for every changed file or hunk.

- `076`: capability hardening baseline
- `080`: presentation/accessibility baseline
- `081`: remediation implementation, tests, artifacts, and sync docs
- `local_unknown`: `.superpowers/**` and any change without approved ownership

Only the first three may enter a reviewed delivery set; `local_unknown` must remain unstaged.

## Verification Evidence

Fresh evidence attached to 081 completion:

- command or manual scenario
- timestamp/run context
- literal pass/fail/skip result
- isolated rerun, if applicable
- public-safety outcome
- rollback note

Historical 076/080 counts are context only and cannot populate 081 completion evidence.
