# Data Model: Notebook Editing (`notebook_edit`)

No content block or event is introduced; the tool reads/writes the `.ipynb` file in place.

## Notebook (the `.ipynb` document)

- A JSON object with at least a `cells` list and top-level `nbformat` / `metadata`.
- Parsed and re-serialized whole; only the `cells` list is mutated, so all other fields are
  preserved (round-trip).
- Must be a dict with a list `cells` to be a valid target; otherwise the edit is rejected.

## Cell

| Field | Type | Notes |
| ----- | ---- | ----- |
| `cell_type` | `"code"` \| `"markdown"` | Required for an inserted cell. |
| `source` | string (or list of strings) | The cell's text. Replace/insert set it. |
| `outputs`, `execution_count`, `metadata` | (code cells) | Preserved on replace; a newly inserted code cell gets empty `outputs` / `null` `execution_count` / empty `metadata` to stay valid. |

## Tool input

| Field | Type | Rules |
| ----- | ---- | ----- |
| `path` | string | Required; resolved within the working scope. |
| `mode` | `"replace"` \| `"insert"` \| `"delete"` | Required. |
| `index` | integer | Required; in `[0, len(cells))` for replace/delete, `[0, len(cells)]` for insert. |
| `source` | string | Required for replace/insert; ignored for delete. |
| `cell_type` | `"code"` \| `"markdown"` | Required for insert; ignored otherwise. |

## Validation / state transitions (from FRs)

| Rule | Source |
| ---- | ------ |
| Path confined to the working scope | FR-001, FR-005 |
| Stale-write guard (read this session, unchanged) | FR-004 |
| Document must be a notebook (dict with `cells` list) | FR-005 |
| Index in range (insert allows `== len`) | FR-002, FR-005 |
| replace/insert/delete mutate only the target cell + ordering | FR-002, FR-003 |
| Other cells/outputs/metadata/nbformat preserved | FR-003 |
| Any failure → normalized error, file unchanged | FR-005 |
| Success → `TextBlock` confirmation; recorded digest refreshed | FR-006 |
