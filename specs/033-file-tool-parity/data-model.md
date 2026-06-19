# Phase 1 Data Model: File-Tool Parity

This feature introduces no new persisted entities. It adds three tool
descriptors + handlers to the Internal Tool Adapter and **reuses** the adapter's
existing in-memory session state. The "model" here is the tool input/output
shapes and the reused state.

## Reused state (unchanged)

- **Session read-digest map** — `InternalToolAdapter._reads: dict[tuple[str, str], str]`
  keyed by `(session_id, resolved_path)` → sha256 of the content at last read.
  Written by `read_file`/`write_file`; **`edit_file` reads and refreshes it**.
- **Working scope** — `RunContext.working_scope`; `_resolve(context, raw)`
  rejects any path resolving outside it. All three new tools call `_resolve`.

## New tool descriptors (`ToolDescriptor`)

| Tool | `read_only` | `concurrency_safe` | Inputs (required) |
|------|-------------|--------------------|-------------------|
| `edit_file` | `False` | (default) | `path`, `old_string`, `new_string` |
| `glob_files` | `True` | `True` | `pattern` (opt: `path`) |
| `grep` | `True` | `True` | `pattern` (opt: `path`, `output_mode`) |

### `edit_file` input schema

- `path` (string, required) — file to edit, resolved within the working scope.
- `old_string` (string, required) — text to replace; must occur exactly once.
- `new_string` (string, required) — replacement text; must differ from `old_string`.

### `glob_files` input schema

- `pattern` (string, required) — glob pattern (e.g. `**/*.py`), evaluated
  relative to the base path.
- `path` (string, optional, default scope root) — base directory.

### `grep` input schema

- `pattern` (string, required) — regular expression.
- `path` (string, optional, default scope root) — base directory.
- `output_mode` (enum, optional, default `content`) — one of
  `content` | `files_with_matches` | `count`.

## Output shapes (`AdapterOutput` — unchanged union)

- **Success** → `TextBlock(text=...)`:
  - `edit_file`: a short confirmation (e.g. characters changed / region replaced).
  - `glob_files`: newline-joined scope-relative POSIX paths, or an explicit
    "no files match" message when empty.
  - `grep`: per `output_mode` — `relpath:line: text` lines / distinct relative
    paths / `relpath: N` matching-line counts; an explicit "no matches" message when empty.
- **Validation failure** → `ErrorOutput(category=ErrorCategory.VALIDATION, message=...)`:
  path escapes scope; `old_string` missing / non-unique / identical to
  `new_string`; target unread or changed since read (stale-write); invalid regex;
  invalid `output_mode`.
- **I/O failure** → `ErrorOutput(message=...)` (no `VALIDATION` category), mirroring
  `_write_file`/`_read_file` OS-error handling.

## Validation rules (from requirements)

- FR-002/003/006: `edit_file` uniqueness + identical-string + stale-write checks;
  `grep` regex compilation — all surface as `VALIDATION` errors with no mutation.
- FR-007: every path resolved through `_resolve`; escapes rejected.
- FR-008: `read_only`/`concurrency_safe` flags exactly as the table above.
- FR-011: undecodable files skipped during traversal; documented result cap.
