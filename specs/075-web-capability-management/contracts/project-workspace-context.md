# Contract: Project And Workspace Context

## Purpose

Define the additive contract for managing project/workspace contexts and binding a session to an available context.

## Scope

This contract covers:

- listing available project/workspace contexts;
- creating or updating user-owned contexts;
- removing contexts;
- selecting a context for a session;
- displaying unavailable context state.

It does not cover desktop multi-pane collaboration, local backup/restore, or remote-control execution.

## Context Summary

A project/workspace summary includes:

- `id`
- `name`
- `description`
- `workspace_label`
- `status`
- `updated_at`

Status values:

- `available`
- `unavailable`
- `read_only`
- `deleted`

## Operations

### List Contexts

Request: authenticated list.

Response: contexts visible to the current principal, including host-provided read-only contexts when available.

### Get Context

Request: authenticated get by context id.

Response: context detail when owned or readable.

### Upsert Context

Request: create or update a context.

Required input:

- `name`
- public-safe workspace label or selector accepted by the host;
- optional description.

Response: public-safe operation result plus refreshed context summary.

### Delete Context

Request: delete by context id with explicit confirmation.

Response: public-safe operation result. Host read-only contexts cannot be deleted.

### Bind Session Context

Request: bind one owned session to one available context.

Response: session context view:

- `session_id`
- `context_id`
- `name`
- `workspace_label`
- `status`

## Non-Disclosure Rules

- Non-owned sessions return the same not-found behavior as existing session endpoints.
- Non-owned contexts are not visible and cannot be selected.
- If a context disappears after binding, the session view reports `unavailable` without leaking who owns it or where it moved.

## Compatibility Requirements

- Sessions without a context continue to work.
- Draft sessions can choose a context before first send, but session creation remains governed by 074 behavior.
- Existing REST/SSE and live chat flows must not require a context.
