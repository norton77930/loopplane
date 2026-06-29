# Contract: Capability Management

## Purpose

Define the additive web-facing management contract for memory entries, skills, and MCP configurations.

## Scope

This contract covers:

- memory list/get/write/delete;
- skill list/get/write/import/delete;
- MCP configuration list/upsert/delete/reconnect;
- public-safe operation results;
- principal scoping and non-disclosure behavior.

It does not cover tool execution, plan mode, permission mode, budget controls, desktop cowork UI, or browser-side provider credential entry.

## Resource Rules

- Every mutable resource is scoped to the authenticated principal unless explicitly host-shared as read-only.
- Non-owned resources are not visible and cannot be mutated.
- Host-shared read-only resources may be listed but cannot be updated or deleted.
- List views return bounded metadata and snippets.
- Full editable content is returned only for owned resources opened intentionally.
- Failure messages are public-safe and must not echo raw local paths, private host details, stack traces, or credential-like values.

## Memory Operations

### List Memory

Request: authenticated list with optional query.

Response: ordered memory summaries:

- `id`
- `name`
- `kind`
- `description`
- `snippet`
- `status`
- `updated_at`

### Get Memory

Request: authenticated get by memory id.

Response: memory detail for owned or readable entries:

- summary fields from list;
- `content` only when allowed;
- `problem` when invalid or unavailable.

### Write Memory

Request: create or update a memory entry.

Required input:

- `name`
- `kind`
- `content`

Response: `CapabilityOperationResult` plus refreshed summary.

### Delete Memory

Request: delete by memory id with explicit confirmation.

Response: `CapabilityOperationResult`.

## Skill Operations

### List Skills

Response: ordered skill summaries:

- `id`
- `name`
- `description`
- `source`
- `status`
- `problem`
- `updated_at`

### Get Skill

Response: skill detail for owned, imported, or host-readable skills.

### Write Skill

Request: create or update a user-managed skill definition.

Response: operation result plus refreshed summary.

### Import Skill

Request: import one skill package or definition.

Response: operation result plus imported skill summary or a public-safe validation failure.

### Delete Skill

Request: delete by skill id with explicit confirmation.

Response: operation result. Read-only host skills cannot be deleted.

## MCP Operations

### List MCP Configurations

Response: ordered MCP summaries:

- `id`
- `name`
- `status`
- `tool_count`
- `tools`
- `problem`
- `updated_at`

### Upsert MCP Configuration

Request: create or update one MCP configuration using public-safe fields accepted by the host.

Response: operation result plus refreshed summary.

### Delete MCP Configuration

Request: delete by MCP configuration id with explicit confirmation.

Response: operation result.

### Reconnect MCP Configuration

Request: reconnect by MCP configuration id.

Response: operation result with final or pending status.

## Compatibility Requirements

- Existing read-only inspection endpoints remain available.
- Existing 074 chat/session behavior remains available.
- Type artifacts are updated only additively if new web-facing shapes are generated.
- Older clients that ignore new fields continue to work.
