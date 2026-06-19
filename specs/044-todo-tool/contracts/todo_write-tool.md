# Tool Contract: `todo_write`

A baseline Internal Tool Adapter tool, reachable only through the Tool Gateway.

## Descriptor

- **name**: `todo_write`
- **description**: "Record the agent's task list for this run. Replaces the current list
  with the provided items; each item has a short `content` and a `status` of `pending`,
  `in_progress`, or `completed`. Submit an empty list to clear it."
- **read_only**: `false` (mutates per-run state)
- **concurrency_safe**: `false` (mutates shared per-session state)
- **network**: not set (no network)

## Input schema

```json
{
  "type": "object",
  "properties": {
    "todos": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "content": { "type": "string" },
          "status": { "type": "string", "enum": ["pending", "in_progress", "completed"] }
        },
        "required": ["content", "status"],
        "additionalProperties": false
      }
    }
  },
  "required": ["todos"],
  "additionalProperties": false
}
```

## Behavior

| Case | Result |
| ---- | ------ |
| Valid non-empty `todos` | Replace the session list; yield a `TextBlock` summarizing the recorded list (each item: status + content). |
| Empty `todos` (`[]`) | Clear the session list; yield a `TextBlock` noting the list is now empty. |
| `status` not in the enum | `ErrorOutput(category=VALIDATION)`; prior list unchanged. |
| Item missing `content`/`status`, or wrong shape | `ErrorOutput(category=VALIDATION)`; prior list unchanged. |
| `content` empty/blank | `ErrorOutput(category=VALIDATION)`; prior list unchanged. |
| More than 100 items | `ErrorOutput(category=VALIDATION)`; prior list unchanged. |

## Result format (success)

A single `TextBlock`, for example:

```text
Recorded 3 todos:
[in_progress] Read the existing adapter pattern
[pending] Add the todo_write handler
[pending] Write unit tests
```

(Exact wording is an implementation detail; the contract is: the result lists each item's
status and content, in order, and reflects exactly the stored list.)

## Invariants

- Reachable only via the Tool Gateway (Constitution V); governed by existing permission /
  plan-mode / hook layers like any tool.
- No event-schema, `SCHEMA_VERSION`, or content-model change (Constitution VI): the result
  is an ordinary `TextBlock`; failures are ordinary `ErrorOutput`.
- Errors never mutate the stored list.
- Per-session isolation: keyed by `session_id`.
