# Quickstart / Validation: Agent Task List (`todo_write`)

How to validate unit 044 end-to-end. See [contracts/todo_write-tool.md](contracts/todo_write-tool.md)
and [data-model.md](data-model.md) for details.

## Prerequisites

- The repo's dev environment (editable install): `pip install -e .[dev]` (already set up).
- No new dependency is required.

## Run the unit tests

```powershell
pytest tests/unit/test_todo_tool.py -q
```

Expected: all `todo_write` cases pass.

## Run the full suite (regression / additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new `todo_write` tests (plus any existing
internal-descriptor-set assertion updated to include `todo_write`). No existing behavior
changes.

## Validation scenarios (mirrors the acceptance scenarios)

1. **Set + return** — invoke `todo_write` with two items (`pending`); the result lists both
   in order, and a follow-up read of the session list shows them. (FR-001, FR-004)
2. **Replace** — invoke again with a different single item; the stored list is exactly that
   one item (no residue). (FR-002)
3. **Update status** — resubmit with an item moved to `in_progress` / `completed`; the new
   status is retained. (FR-001)
4. **Clear** — invoke with `todos: []`; the list becomes empty. (FR-007)
5. **Invalid status** — submit `status: "blocked"`; a `VALIDATION` error is returned and the
   prior list is unchanged. (FR-006)
6. **Missing field** — submit an item without `content`; a `VALIDATION` error; prior list
   unchanged. (FR-006)
7. **Oversized** — submit 101 items; a `VALIDATION` error; prior list unchanged. (FR-008)
8. **Per-session isolation** — two different `session_id`s keep independent lists. (FR-003)
9. **Descriptor present** — `InternalToolAdapter().describe()` includes a `todo_write`
   descriptor with `read_only=False`. (FR-011)

## Manual gate checks (autopilot validation, board §10)

```powershell
git diff --check
pytest
```

Plus the public-safety scan (no private paths / secrets in the diff).
