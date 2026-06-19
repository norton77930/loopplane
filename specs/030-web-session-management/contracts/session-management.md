# Contract: Session Management (030)

Additive to the unit-011 `/v1` web/API surface. Auth required (bearer, unit 022/023). All
per-session routes are **owner-scoped**: a non-owner or unknown id returns **404** with the fixed
`{"detail": "..."}` envelope — never revealing existence or ownership.

## HTTP

### `GET /v1/sessions` — extended response

Each item changes from `{ session_id, label }` to:

```json
{ "session_id": "string", "label": "string|null", "last_active_at": "ISO-8601", "created_at": "ISO-8601" }
```

Filtered to the caller's `principal_id` (unchanged). The pinned field-set assertions in
`tests/contract/test_webapi_boundary.py` and `tests/integration/test_webapi_us4.py` are updated to
the new set as part of this unit.

### `PATCH /v1/sessions/{session_id}` — rename (new)

- **Body**: `RenameRequest` `{ "title": "string" }` (`min_length=1`; empty/whitespace → **422**).
- **Auth + ownership**: non-owner / unknown id → **404**.
- **Success**: **200** `{ "resolved": true }`. The title persists durably (survives reload + restart)
  and the next `GET /v1/sessions` reflects it.

### `DELETE /v1/sessions/{session_id}` — delete (new)

- **Auth + ownership**: non-owner / unknown id → **404**.
- **Behaviour**: cancels a live in-memory session for that id (if any), then removes the durable
  records.
- **Success**: **200** `{ "resolved": true }`. The session no longer appears in `GET /v1/sessions`
  and does not return after a restart.

## Internal interface (`CheckpointStore`)

```text
async set_title(session_id: str, title: str) -> None
    # append a fresh session-meta with label=title; latest wins in list_sessions + on resume.

delete_session(session_id: str) -> None
    # durable removal; idempotent on an unknown id.
    # FileCheckpointStore: remove the session directory.
    # SqliteCheckpointStore: DELETE FROM records WHERE session_id = ?.
```

Reached only as **webapi → host → controller → store** (boundary test stays green).

## Frontend client (`apps/web/src/api/client.ts`)

```text
renameSession(id: string, title: string): Promise<void>   // PATCH /v1/sessions/{id}
deleteSession(id: string): Promise<void>                   // DELETE /v1/sessions/{id}
```

`SessionSummary` type → `{ session_id, label, last_active_at, created_at }`.
