# Data Model: Agent Task List (`todo_write`)

The feature introduces two small in-memory shapes. Neither is a content block nor an event;
both are internal to the Internal Tool Adapter (no event-schema or content-model change).

## TodoItem

A single tracked unit of work.

| Field | Type | Rules |
| ----- | ---- | ----- |
| `content` | string | Required; non-empty after trimming. Short human-readable description. |
| `status` | enum | Required; one of `pending`, `in_progress`, `completed`. Any other value is rejected. |

- Order is positional (the item's index in the list); there is no separate id field in v1.
- No timestamps, owners, or priorities in v1 (out of scope).

## TodoList

The ordered collection for one run.

- **Identity**: keyed by `session_id` (from `RunContext`) inside the adapter's
  `self._todos: dict[str, list[TodoItem]]`.
- **Cardinality**: 0..N items, ordered; bounded by `MAX_TODO_ITEMS = 100`.
- **Lifecycle / state transitions**:
  - *absent → set*: first `todo_write` establishes the list.
  - *set → replaced*: each subsequent `todo_write` replaces the whole list (no merge).
  - *set → cleared*: a `todo_write` with an empty `todos` array clears the list.
  - On a rejected (invalid) write, the prior list is **unchanged**.
- **Isolation**: lists are per `session_id`; one session's list never affects another's.
- **Persistence**: in-memory for the run; not persisted beyond the existing checkpoint
  mechanism (out of scope).

## Validation summary (from FRs)

| Rule | Source |
| ---- | ------ |
| Each item has non-empty `content` | FR-001, FR-006 |
| `status` ∈ {pending, in_progress, completed} | FR-001, FR-006 |
| Replace-whole-list on every call | FR-002 |
| Empty list clears | FR-007 |
| ≤ `MAX_TODO_ITEMS` (100); else reject, prior list unchanged | FR-008 |
| Invalid/malformed → normalized error, prior list unchanged | FR-006 |
| List retained per run, readable by later calls | FR-003 |
| Result returns the recorded list | FR-004 |
