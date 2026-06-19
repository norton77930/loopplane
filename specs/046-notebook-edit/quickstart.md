# Quickstart / Validation: Notebook Editing (`notebook_edit`)

See [contracts/notebook_edit-tool.md](contracts/notebook_edit-tool.md) and
[data-model.md](data-model.md).

## Run the unit tests

```powershell
pytest tests/unit/test_notebook_edit.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new notebook-edit tests. No existing behavior
changes.

## Validation scenarios (mirror the acceptance scenarios)

1. **Replace** — read a 2-cell `.ipynb`, replace cell 0's source; only cell 0 changed; cell 1
   (incl. its outputs/metadata) and `nbformat` preserved; file still a valid notebook. (FR-002/003)
2. **Insert** — insert a markdown cell at index 1; it appears at 1, later cells shift; valid. (FR-002)
3. **Insert at end** — insert at `index == len(cells)` appends. (edge case)
4. **Delete** — delete cell 1; remaining cells preserved in order. (FR-002)
5. **Stale-write guard** — edit without a prior `read_file`, or after the file changed since the
   read → `VALIDATION` error, file unchanged. (FR-004)
6. **Out-of-range index** → `VALIDATION` error, file unchanged. (FR-005)
7. **Not a notebook / malformed JSON** → `VALIDATION` error, file unchanged. (FR-005)
8. **Path outside the working scope** → `VALIDATION` error, nothing written. (FR-001/005)
9. **Descriptor** — `describe()` includes `notebook_edit` with `read_only=False`. (governance)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the public-safety scan (no private paths / secrets in the diff).
