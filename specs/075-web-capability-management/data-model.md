# Data Model: Web Capability Management

## Memory Entry

Represents a user-owned or host-available knowledge item.

**Fields**:

- `id`: stable public identifier.
- `owner_id`: owning principal when mutable; omitted from UI if not needed.
- `name`: display name.
- `kind`: memory, knowledge, note, or host-defined category.
- `description`: short public-safe summary.
- `snippet`: bounded preview for lists.
- `content`: full editable content, returned only when the user opens an owned entry.
- `status`: available, invalid, unavailable, or read-only.
- `updated_at`: last modification timestamp when known.

**Validation rules**:

- Name must be non-empty after trimming.
- List views must use bounded snippets.
- Non-owned mutable content must not be returned.
- Invalid content must preserve a public-safe problem message.

## Skill

Represents a reusable agent capability available to the user.

**Fields**:

- `id`: stable public identifier.
- `name`: display name.
- `description`: bounded public-safe summary.
- `source`: host, user, imported package, or other public-safe source label.
- `status`: available, invalid, unavailable, importing, or read-only.
- `problem`: sanitized problem summary when validation or loading fails.
- `updated_at`: last modification timestamp when known.

**Validation rules**:

- Import payload must identify one skill package or definition.
- Duplicate names must be rejected or resolved deterministically.
- Problem messages must not echo raw local paths or credential-like values.
- Read-only host skills cannot be mutated or deleted.

## MCP Configuration

Represents a managed external capability connection.

**Fields**:

- `id`: stable public identifier.
- `name`: display name.
- `status`: connected, disconnected, reconnecting, invalid, or read-only.
- `tool_count`: number of exposed tools.
- `tools`: bounded tool names/descriptions when available.
- `problem`: sanitized problem summary when connection fails.
- `updated_at`: last modification timestamp when known.

**Validation rules**:

- Name must be non-empty after trimming.
- Connection details must be stored and returned only through safe metadata views.
- Reconnect requests must settle into connected, disconnected, or invalid.
- Non-owned configurations must not be visible or mutable.

## Project/Workspace Context

Represents a working context that can be associated with sessions.

**Fields**:

- `id`: stable public identifier.
- `name`: display name.
- `description`: bounded public-safe summary.
- `workspace_label`: public-safe workspace label.
- `status`: available, unavailable, read-only, or deleted.
- `updated_at`: last modification timestamp when known.

**Relationships**:

- A session may reference at most one active project/workspace context.
- A project/workspace context may be used by many sessions owned by the same principal.

**Validation rules**:

- Context selection must be owner-scoped.
- Deleted or unavailable contexts cannot be selected for new turns.
- Existing sessions bound to a now-unavailable context must display a clear unavailable state.

## Schedule

Represents a user-visible automation definition.

**Fields**:

- `id`: stable public identifier.
- `name`: display name.
- `description`: bounded public-safe summary.
- `trigger`: public-safe trigger description.
- `enabled`: whether the schedule can run automatically.
- `status`: enabled, disabled, running, invalid, failed, or deleted.
- `next_run_at`: next expected run timestamp when known.
- `last_run_at`: last run timestamp when known.
- `problem`: sanitized problem summary when invalid or failed.

**State transitions**:

- Draft or invalid -> enabled after valid save.
- Enabled -> disabled by user action.
- Enabled or disabled -> deleted by user action.
- Enabled -> running when run-now starts.
- Running -> enabled, disabled, invalid, or failed after completion.

**Validation rules**:

- Trigger description must be valid before enabling.
- Run-now must reject unavailable targets with a public-safe reason.
- Delete must be explicit and owner-scoped.

## Model Default

Represents a default model preference chosen from the host-provided catalog.

**Fields**:

- `model_id`: selected host-provided model identifier.
- `label`: display label from the host catalog.
- `status`: available, unavailable, or fallback.
- `updated_at`: last modification timestamp when known.

**Validation rules**:

- Selection must match a current host-provided catalog entry.
- Browser UI must not collect provider credentials.
- Removed models must fall back deterministically or show an unavailable state.

## Capability Operation Result

Represents a mutation outcome shown to the user.

**Fields**:

- `ok`: whether the operation succeeded.
- `resource_id`: affected resource identifier when available and safe.
- `status`: resulting resource status.
- `message`: public-safe user-facing summary.

**Validation rules**:

- Failure messages must be public-safe.
- Non-owner operations return a non-disclosing not-found or denied result according to existing web/API conventions.
- Results must be deterministic enough for UI refresh and tests.
