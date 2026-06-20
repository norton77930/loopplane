# Quickstart / Validation: File-Edit Undo

See [contracts/undo-tool.md](contracts/undo-tool.md), [data-model.md](data-model.md), and
[research.md](research.md). The lightest Tier-3 unit — per-session adapter state (the 044/033
pattern), gated by the `InternalToolAdapter(max_file_snapshots=…)` ctor param.

## Run the unit tests

```powershell
pytest tests/unit/test_file_undo.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new file-undo tests. With `max_file_snapshots = 0`
(the default), behavior is byte-identical (no snapshot, no `undo_file` tool).

## Validation scenarios (mirror the acceptance scenarios)

1. **Undo a write** — enable (`max_file_snapshots=5`); write a file, overwrite it, `undo_file` →
   the file holds the first content. (FR-001/002, SC-001)
2. **Multi-step walk-back** — modify twice, `undo_file` twice → walks back step-by-step;
   a third `undo_file` → "nothing to undo". (FR-002)
3. **Stale-write-guard re-sync** — after `undo_file`, an `edit_file` on the restored file is
   accepted (not rejected as stale). (FR-003, SC-002)
4. **Binary faithful** — snapshot + undo a non-UTF-8 / binary file → restored byte-for-byte.
   (FR-006, SC-001)
5. **Cap** — exceed `max_file_snapshots` → oldest dropped; the most recent remain undoable.
   (FR-004, SC-003)
6. **Out-of-scope / unknown** — `undo_file` on a `..`/absolute escape or a never-modified path →
   a normalized error (no crash, no escape). (FR-005, SC-002)
7. **Default-off byte-identical** — `max_file_snapshots = 0` → `describe()` has no `undo_file`;
   the mutating tools take no snapshot. (FR-007, SC-004)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`).
