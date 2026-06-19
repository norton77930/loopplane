# Quickstart: Validating File-Tool Parity

This guide proves the three new tools work end-to-end through the Internal Tool
Adapter. All scenarios are offline and deterministic.

## Prerequisites

- A dev install of the repo (`pip install -e ".[dev]"`), Python 3.12+.
- No API key, no network — these are baseline file tools.

## Automated validation (primary)

Run the unit gate for the new tools plus the existing tool tests to confirm
no regression:

```powershell
python -m pytest tests/unit/test_internal_file_tools.py tests/unit/test_rules_and_tools.py -q
```

Then the full quality gates:

```powershell
ruff format --check .; ruff check .; mypy .; python -m pytest -q
```

**Expected**: all green; `search_files` tests unchanged and passing.

## What the tests assert (mapping to acceptance scenarios)

- **`edit_file`** (US1): after a `read_file`, a unique `old_string` is replaced
  and the read-digest refreshed (US1-1); editing an unread/changed file is a
  stale-write `VALIDATION` error with no change (US1-2); missing / non-unique /
  identical `old_string` is a `VALIDATION` error with no change (US1-3).
- **`glob_files`** (US2): a pattern returns exactly the matching scope-relative
  files (US2-1); a non-matching pattern returns an empty/"no files" result, not
  an error (US2-2); an out-of-scope base path is rejected.
- **`grep`** (US3): `content`/`files_with_matches`/`count` modes each satisfy
  their contract (US3-1/2); an invalid regex is a `VALIDATION` error, not a
  crash (US3-3).
- **Confinement** (all): an absolute path or `..` escape is rejected for all
  three tools.

## Manual smoke (optional)

Construct an `InternalToolAdapter`, drive it through a `RunContext` with a
temp `working_scope`, and invoke each tool — see `contracts/tools.md` for the
exact input/output contract and `data-model.md` for the input schemas.

## Rollback

The feature is additive. To roll back, remove the three descriptors and their
handlers from `src/loopplane/tools/internal.py` and delete the new test module;
the baseline tool set (`read_file`, `write_file`, `search_files`, `run_command`,
`ask_user`, `memory_write`) and the gateway are untouched (Constitution X).
