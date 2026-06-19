# Contracts: File-Tool Parity (Internal Tool Adapter)

The "interface" this unit exposes is three new model-facing tools, surfaced
through the Tool Gateway as `ToolDescriptor`s and invoked via
`InternalToolAdapter.invoke(name, call_input, context)`. All paths are confined
to `context.working_scope` via `_resolve`. All errors are returned as
`ErrorOutput` (never raised across the gateway boundary).

## `edit_file`

**Description**: Replace a uniquely-occurring `old_string` with `new_string` in
an existing in-scope text file. Requires the file to have been read this session
and unchanged since (stale-write guard).

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string"},
    "old_string": {"type": "string"},
    "new_string": {"type": "string"}
  },
  "required": ["path", "old_string", "new_string"],
  "additionalProperties": false
}
```

**Behaviour contract**

| Condition | Result |
|-----------|--------|
| `old_string` occurs exactly once, file read this session & unchanged | replace it; refresh read-digest; `TextBlock` confirmation |
| `path` resolves outside scope | `ErrorOutput(VALIDATION)` |
| file not read this session / changed since read | `ErrorOutput(VALIDATION)` (stale-write) |
| `old_string` absent | `ErrorOutput(VALIDATION)` |
| `old_string` occurs > once | `ErrorOutput(VALIDATION)` |
| `old_string == new_string` | `ErrorOutput(VALIDATION)` |
| file does not exist / OS error | `ErrorOutput` (no VALIDATION category) |

**Flags**: `read_only=False`.

## `glob_files`

**Description**: List in-scope files matching a glob pattern; returns
scope-relative POSIX paths (files only).

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "pattern": {"type": "string"},
    "path": {"type": "string"}
  },
  "required": ["pattern"],
  "additionalProperties": false
}
```

**Behaviour contract**

| Condition | Result |
|-----------|--------|
| matches found | `TextBlock` with newline-joined relative paths (capped) |
| no matches | `TextBlock` with an explicit "no files match" message |
| `path` resolves outside scope | `ErrorOutput(VALIDATION)` |
| base path not a directory | `ErrorOutput` |

**Flags**: `read_only=True`, `concurrency_safe=True`.

## `grep`

**Description**: Regex content search within scope, with selectable output mode.

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "pattern": {"type": "string"},
    "path": {"type": "string"},
    "output_mode": {"type": "string", "enum": ["content", "files_with_matches", "count"]}
  },
  "required": ["pattern"],
  "additionalProperties": false
}
```

**Behaviour contract**

| Condition | Result |
|-----------|--------|
| matches, `content` (default) | `TextBlock` of `relpath:line: text` (capped) |
| matches, `files_with_matches` | `TextBlock` of distinct relative paths |
| matches, `count` | `TextBlock` of `relpath: N` (N = matching lines) per file |
| no matches | `TextBlock` with an explicit "no matches" message |
| invalid regex | `ErrorOutput(VALIDATION)` |
| invalid `output_mode` | `ErrorOutput(VALIDATION)` |
| `path` resolves outside scope | `ErrorOutput(VALIDATION)` |
| undecodable file encountered | skipped silently during traversal |

**Flags**: `read_only=True`, `concurrency_safe=True`.

## Invariants (all three)

- Reachable **only** through the Tool Gateway (Constitution V); no bypass path.
- Every path passes through `_resolve`; absolute/`..` escapes rejected.
- `search_files` and every other tool/contract is **unchanged** (back-compat).
- Output union remains `TextBlock | ImageBlock | ErrorOutput` (unchanged).
