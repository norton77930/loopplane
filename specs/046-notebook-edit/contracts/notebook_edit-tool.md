# Tool Contract: `notebook_edit`

A baseline Internal Tool Adapter tool, reachable only through the Tool Gateway, confined to
the run's working scope.

## Descriptor

- **name**: `notebook_edit`
- **description**: "Edit a Jupyter notebook (.ipynb) cell within the working scope: replace a
  cell's source, insert a new code/markdown cell, or delete a cell, selected by index. The
  notebook must have been read this session and be unchanged since."
- **read_only**: `false` (mutates a file)
- **concurrency_safe**: `false`

## Input schema

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "mode": { "type": "string", "enum": ["replace", "insert", "delete"] },
    "index": { "type": "integer", "minimum": 0 },
    "source": { "type": "string" },
    "cell_type": { "type": "string", "enum": ["code", "markdown"] }
  },
  "required": ["path", "mode", "index"],
  "additionalProperties": false
}
```

## Behavior

| Case | Result |
| ---- | ------ |
| `replace` a valid in-range cell (read this session, unchanged) | Set `cells[index].source`; preserve everything else; write; `TextBlock` confirmation. |
| `insert` at `index` in `[0, len]` with `cell_type` + `source` | Insert a minimal valid cell; shift later cells; write; confirm. |
| `delete` a valid in-range cell | Remove `cells[index]`; write; confirm. |
| Path outside the working scope | `ErrorOutput(VALIDATION)`; file unchanged. |
| Not read this session / changed since read | `ErrorOutput(VALIDATION)` (stale-write guard); file unchanged. |
| Not a notebook (no `cells` list) / malformed JSON | `ErrorOutput(VALIDATION)`; file unchanged. |
| `index` out of range (for the mode) | `ErrorOutput(VALIDATION)`; file unchanged. |
| `replace`/`insert` missing `source`, or `insert` missing `cell_type` | `ErrorOutput(VALIDATION)`; file unchanged. |

## Invariants

- Reachable only via the Tool Gateway (V); governed by existing policy / plan-mode / hooks.
- Round-trips the parsed `.ipynb`; preserves all non-targeted cells, outputs, metadata, and
  top-level `nbformat`/`metadata`; the file remains a valid notebook.
- No event-schema / `SCHEMA_VERSION` / content-model change (VI); no new dependency (stdlib
  `json`).
- Every failure leaves the file unchanged (fail-closed), mirroring `edit_file`.
