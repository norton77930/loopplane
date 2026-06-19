# Data Model: Web Session Management (030)

Additive over existing types — no new persisted record kind.

## Existing types (reused)

### `SessionMetaPayload` (`src/loopplane/checkpoint/records.py`) — unchanged shape

| Field | Type | Notes |
|-------|------|-------|
| `created_at` | aware datetime | set at creation |
| `label` | `str \| None` | **the session title** — now **updatable** by appending a fresh meta record |
| `principal_id` | `str \| None` | owner (unit 022) |

**Rule change**: listing/rebuild take the **last** `SessionMetaRecord` (was: first), so the latest
title wins. `rebuild_session` already applies last-wins on resume.

### `SessionSummary` (`src/loopplane/checkpoint/base.py`) — unchanged

`{ session_id, label, created_at, last_active_at, principal_id }` — already carries the timestamps
the view will now expose.

## New / changed types

### `CheckpointStore` Protocol additions (`checkpoint/base.py`)

| Method | Signature | Semantics |
|--------|-----------|-----------|
| `set_title` | `async set_title(session_id: str, title: str) -> None` | append a fresh session-meta carrying `label=title`; latest wins |
| `delete_session` | `delete_session(session_id: str) -> None` | durable removal; **idempotent** on an unknown id |

Implemented in both `FileCheckpointStore` and `SqliteCheckpointStore`.

### `RuntimeController` / `LoopPlaneHost` additions

`set_session_title(session_id, title)` and `delete_session(session_id)` — delegate to the store
(raise `RuntimeError` without a configured store, mirroring `resume`); the controller also updates a
loaded `_Session.label` and pops a live session on delete.

### `RenameRequest` (`webapi/models.py`) — new

| Field | Type | Validation |
|-------|------|------------|
| `title` | `str` | `min_length=1` (rejects empty/whitespace-only after trim) |

### `SessionSummaryView` (`webapi/models.py`) — extended

`{ session_id, label }` → `{ session_id, label, last_active_at, created_at }` (+ matching
`_SummaryLike` Protocol). Still metadata-only (ids + label + timestamps; **no content** — FR-016).

## State transitions

- **Title**: `none` → `set(title)` → `set(title')` … (last write wins, in listing and on resume).
- **Session**: `exists` → `delete()` → `absent` (terminal; durable across reload/restart).
- **Ownership**: every operation is owner-scoped; a non-owner sees `not found` (no transition).
