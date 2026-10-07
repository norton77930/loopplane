# Implementation Evidence: Worker Drain Handoff

Date: 2026-10-08. Status: Implemented. Not published.

## Authorization

The maintainer asked to run the full suite on `087-weighted-tenant-turns`, then
plan and implement the next Spec Kit stage in the same session. Gap C4's first
remaining P1 item is live run migration. This unit takes the between-run drain
slice. Mid-turn migration stays deferred. No 085, 086, or 087 spec was rewritten.

## Analyze

Requirements FR-001..FR-010 map to tasks T003..T005. No clarification markers.
The plan adds no dependency, route, phrase, event, or checkpoint field. The
shared store does not learn the flag, so one worker's drain cannot refuse a peer.

## RED

`tests/unit/test_webapi_admission.py -k drain` failed with
`AttributeError: 'AdmissionCoordinator' object has no attribute 'begin_drain'`
on all three new tests.

## GREEN

`uv run pytest -q --tb=line tests/unit/test_webapi_admission.py`: **29 passed**.
Ruff format left the two Python files unchanged. Ruff check passed.
`git diff --check` is recorded with the commit.

The agent-context PowerShell script could not parse its YAML fallback and
skipped. The managed plan path in `AGENTS.md` was set to this unit's plan, and
`CLAUDE.md` was mirrored in the same change.

## Full suite before this unit

On `1a9f464` plus the uncommitted safety fixes, `uv run pytest -q --tb=line --timeout=180`:
**2 failed, 2403 passed, 33 skipped**. Failures: the validator fixture matched
the assigned-secret scan, and board unit 087 had no changelog entry. Both are
fixed in `d49b27f` and cherry-picked onto `086-cluster-fair-turn` and
`087-weighted-tenant-turns`. The two contract tests and the fixture then passed.

An earlier default-timeout run was killed while `test_committed_files_are_public_safe`
was still reading the tree. The completed run above used `--timeout=180`.

## Full suite for this unit

`uv run pytest -q --tb=line --timeout=180`: **2408 passed, 33 skipped**, 1 existing
Starlette warning, 663.84 seconds. The per-test timeout was raised from the
repository default of 60 seconds for this run so the public-safety scan could
finish on this machine. Mypy and a repository-wide Ruff check were not run.
The unit stays Implemented until those gates and a review are recorded.
