---
description: "Task list for File-Tool Parity (spec 033)"
---

# Tasks: File-Tool Parity for the Baseline Tool Set

**Input**: Design documents from `/specs/033-file-tool-parity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tools.md

**Tests**: REQUIRED (Constitution X). Write tests FIRST and confirm they FAIL
before implementing each tool.

**Organization**: Grouped by user story (US1 `edit_file` P1, US2 `glob_files`
P2, US3 `grep` P3). All source edits land in the single module
`src/loopplane/tools/internal.py`, so the three stories' *implementation* tasks
are sequential (same file); their *test* authoring is logically independent.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Single project: `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test harness for the new tools.

- [ ] T001 Create `tests/unit/test_internal_file_tools.py` with shared fixtures (a temp `working_scope`, an `InternalToolAdapter`, a `RunContext`, and a helper that drains `invoke()` async-iterator output into a list), mirroring the construction style of `tests/unit/test_rules_and_tools.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire the three tools into the adapter registry so tests can target them.

**⚠️ CRITICAL**: Must complete before any user-story implementation.

- [ ] T002 In `src/loopplane/tools/internal.py`, add `edit_file`, `glob_files`, and `grep` `ToolDescriptor` entries to `_DESCRIPTORS` (with the input schemas and `read_only`/`concurrency_safe` flags from `data-model.md`) and register `_edit_file`/`_glob_files`/`_grep` handler names in the `invoke()` handler map (stub bodies for now). Leave `search_files` untouched.

**Checkpoint**: Tools resolve through the gateway; TDD can begin.

---

## Phase 3: User Story 1 - Surgically edit an existing file (Priority: P1) 🎯 MVP

**Goal**: `edit_file` performs a unique-match replacement gated by the existing stale-write guard.

**Independent Test**: Read a file, `edit_file` a unique `old_string`, assert the region changed and the read-digest refreshed; assert each guard failure makes no change.

### Tests for User Story 1 ⚠️ (write first, must FAIL)

- [ ] T003 [US1] In `tests/unit/test_internal_file_tools.py`, add failing tests for `edit_file`: (a) success — unique replace + read-digest refreshed; (b) unread target → VALIDATION, no change; (c) stale target (changed since read) → VALIDATION, no change; (d) `old_string` missing → VALIDATION; (e) `old_string` non-unique → VALIDATION; (f) `old_string == new_string` → VALIDATION; (g) absolute/`..` path escape → VALIDATION; (h) non-existent file → `ErrorOutput`.

### Implementation for User Story 1

- [ ] T004 [US1] Implement `_edit_file` in `src/loopplane/tools/internal.py`, reusing `_resolve`, `_digest`, the `self._reads` map, and the exact stale-write checks from `_write_file`; replace the unique occurrence, refresh the recorded digest on success, and return a `TextBlock` confirmation. Mirror `_write_file`'s OS-error handling.
- [ ] T005 [US1] Run `python -m pytest tests/unit/test_internal_file_tools.py -k edit_file -q` and confirm all US1 tests pass.

**Checkpoint**: `edit_file` fully functional and independently tested.

---

## Phase 4: User Story 2 - Discover files by pattern (Priority: P2)

**Goal**: `glob_files` returns in-scope, scope-relative file paths matching a glob.

**Independent Test**: Seed a tree, glob a pattern, assert exact matching relative paths; non-match → empty; escape → rejected.

### Tests for User Story 2 ⚠️ (write first, must FAIL)

- [ ] T006 [US2] Add failing tests for `glob_files`: matches return scope-relative POSIX paths (files only, directories excluded); non-matching pattern returns an explicit empty result (not an error); out-of-scope base path → VALIDATION; result cap honored.

### Implementation for User Story 2

- [ ] T007 [US2] Implement `_glob_files` in `src/loopplane/tools/internal.py`: `_resolve` the optional base path, match with `pathlib`/`fnmatch` within scope, return scope-relative POSIX file paths (capped, mirroring `_SEARCH_MATCH_LIMIT`), explicit message when empty.
- [ ] T008 [US2] Run `python -m pytest tests/unit/test_internal_file_tools.py -k glob -q` and confirm US2 tests pass.

**Checkpoint**: `edit_file` + `glob_files` both independently functional.

---

## Phase 5: User Story 3 - Regex content search with output modes (Priority: P3)

**Goal**: `grep` does regex search with `content`/`files_with_matches`/`count` modes.

**Independent Test**: Seed files, grep in each mode, assert per-mode contract; invalid regex → VALIDATION (no crash).

### Tests for User Story 3 ⚠️ (write first, must FAIL)

- [ ] T009 [US3] Add failing tests for `grep`: `content` mode → `relpath:line: text`; `files_with_matches` → distinct relative paths; `count` → `relpath: N`; default mode is `content`; invalid regex → VALIDATION; invalid `output_mode` → VALIDATION; out-of-scope base path → VALIDATION; undecodable file skipped; result cap honored.

### Implementation for User Story 3

- [ ] T010 [US3] Implement `_grep` in `src/loopplane/tools/internal.py`: `_resolve` base, compile regex (`re.error` → VALIDATION), walk files (skip undecodable like `_search_files`), produce output per `output_mode` (capped), explicit message when empty.
- [ ] T011 [US3] Run `python -m pytest tests/unit/test_internal_file_tools.py -k grep -q` and confirm US3 tests pass.

**Checkpoint**: All three tools independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T012 Regression: run `python -m pytest tests/unit/test_rules_and_tools.py -q` and confirm `search_files` and all existing adapter behaviour are unchanged.
- [ ] T013 Quality gates: `ruff format --check .`, `ruff check .`, `mypy .`, `python -m pytest -q` — all green.
- [ ] T014 Run the `quickstart.md` validation commands and confirm expected outcomes.
- [ ] T015 [P] Update `CHANGELOG.md` with the three new baseline tools (additive, no dependency change).

---

## Dependencies & Execution Order

- **T001 (Setup)** → **T002 (Foundational, blocks all stories)** → stories.
- Within each story: tests (T003/T006/T009) FAIL first → implementation → verify.
- **Stories are sequential** here because all implementation edits the same file (`internal.py`); US1 → US2 → US3.
- **Polish (T012–T015)** after all three stories.

## Parallel Opportunities

- Limited: a single source file serializes implementation. T015 (CHANGELOG) is `[P]` (different file). Test authoring per story is logically independent but lands in one test module.

## Implementation Strategy

- **MVP** = Phase 1 + 2 + Phase 3 (US1 `edit_file`) — the highest-value tool, independently shippable.
- Then add US2, US3 incrementally; each leaves prior tools and `search_files` intact.

## Notes

- No new dependency, no frontend, no event/gateway/loop change (pure additive).
- Commit after the sprint spec is green (main-only autopilot), message via `git commit -F`.
- Rollback = delete the three descriptors/handlers + the new test module.
