# Contract: File-Edit Undo Tool

One Gateway tool (`undo_file`) on the `InternalToolAdapter`, plus a pre-write snapshot side-effect
on the existing mutating file tools. Registered + active only when
`InternalToolAdapter(max_file_snapshots > 0)` (default 0 → none; byte-identical).

## Tool

| Tool | Input | Result |
| ---- | ----- | ------ |
| `undo_file` | `path: str` | Restores the file to its most recent snapshot; confirms (or reports nothing to undo). |

- `undo_file` is `read_only=False`, `concurrency_safe=False`.

## Snapshot side-effect (existing tools, when enabled)

| Tool | Side-effect |
| ---- | ----------- |
| `write_file` / `edit_file` / `notebook_edit` | Before overwriting an EXISTING file, push its prior raw bytes onto the per-(session,path) snapshot stack (bounded; oldest dropped at the cap). A brand-new file takes no snapshot. |

## Behavior

| Case | Result |
| ---- | ------ |
| Modify a file (enabled), then `undo_file` | The file's content is restored to the exact pre-modification bytes; the stale-write guard is re-synced (a following edit is not rejected as stale). |
| `undo_file` twice on a twice-modified file | Walks back one step per call (most-recent-first). |
| `undo_file` with no snapshot left | A clear "nothing to undo for <path>" TextBlock (not a crash). |
| `undo_file` on an out-of-scope / unknown / never-snapshotted path | A normalized `ErrorOutput` (VALIDATION); no crash, no escape. |
| Binary / non-UTF-8 file | Restored faithfully (raw bytes). |
| Snapshot count exceeds `max_file_snapshots` | Oldest snapshot dropped (bounded memory). |
| Feature disabled (`max_file_snapshots = 0`) | No `undo_file` in `describe()`; the mutating tools take no snapshot; byte-identical. |

## Invariants

- Reachable only through the Tool Gateway (V); the snapshot is a side-effect inside the existing
  Gateway-owned handlers.
- Working-scope-confined (reuses `_resolve`); raw-bytes faithful (FR-006).
- No event-schema / `SCHEMA_VERSION` / content-model change (VI); no new dependency; no ADR.
- Default-off (`max_file_snapshots = 0`) is byte-identical to pre-054 (proven by a test).
- Public-safe (VII): normalized errors echo only the caller-supplied path, no internal absolutes.
