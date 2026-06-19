# Tasks: Agent Task List (`todo_write`)

**Feature**: 044-todo-tool | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive, confined to `src/loopplane/tools/internal.py` + `tests/unit/test_todo_tool.py`
(plus updating any existing internal-descriptor-set assertion). No event-schema/content-model
change, no new dependency, no ADR.

**Tests**: requested (TDD-friendly ordering — write tests, then implement to green).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Add a module-level `MAX_TODO_ITEMS = 100` constant and the `todo_write` `ToolDescriptor` (input schema per [contracts/todo_write-tool.md](contracts/todo_write-tool.md): `todos` array of `{content, status∈{pending,in_progress,completed}}`; `read_only=False`; `concurrency_safe=False`) to the `_DESCRIPTORS` list in `src/loopplane/tools/internal.py`
- [ ] T002 Initialize per-session state `self._todos: dict[str, list[dict[str, str]]] = {}` in `InternalToolAdapter.__init__`, and register `"todo_write": self._todo_write` in the `invoke` dispatch dict, in `src/loopplane/tools/internal.py`

## Phase 2: User Story 1 — Agent records and updates a multi-step plan (P1) 🎯 MVP

**Goal**: The agent can record a list and replace/update it within a run.

**Independent test**: invoke `todo_write` with a list, then again with changed statuses; the latest list is retained and returned.

- [ ] T003 [US1] Write `tests/unit/test_todo_tool.py` covering: set + returned `TextBlock` reflects items; replace (second call leaves no residue from the first); update-status (item → in_progress/completed retained); empty `todos: []` clears; invalid `status` rejected (VALIDATION, prior list unchanged); item missing `content`/`status` rejected; blank `content` rejected; oversized (101 items) rejected with prior list unchanged. (Red until T004.)
- [ ] T004 [US1] Implement the `_todo_write` async handler in `src/loopplane/tools/internal.py`: validate the `todos` array shape and each item (non-empty `content`, `status` in the enum) and the `MAX_TODO_ITEMS` bound; on any invalid input yield `ErrorOutput(category=ErrorCategory.VALIDATION, ...)` and do **not** mutate `self._todos`; on valid input replace `self._todos[context.session_id]` with the submitted list (empty clears) and yield a `TextBlock` summarizing the recorded list (status + content per item, in order). Make T003 pass.

## Phase 3: User Story 2 — Host/observer sees the current plan as metadata (P2)

**Goal**: The recorded list is observable as metadata only, isolated per session, with no leakage.

**Independent test**: after a write, the result/state exposes only item content + status; two sessions stay independent.

- [ ] T005 [US2] Extend `tests/unit/test_todo_tool.py`: per-session isolation (two distinct `session_id`s keep independent lists) and result-content safety (the result reflects only `content` + `status`, no conversation/secret/path content).

## Phase 4: User Story 3 — Tool governed like every other tool (P3)

**Goal**: The tool is a normal Gateway tool subject to the existing governance layers.

**Independent test**: `describe()` advertises `todo_write` with `read_only=False`, so plan-mode/permission deciders treat it as a mutating tool.

- [ ] T006 [US3] Extend `tests/unit/test_todo_tool.py`: assert `InternalToolAdapter().describe()` includes a `todo_write` descriptor with `read_only is False` and the documented input schema (so the plan-mode/permission/hook layers govern it like any tool — no special-casing).

## Phase 5: Polish & Cross-Cutting

- [ ] T007 Search `tests/` for any assertion of the exact internal/baseline descriptor name set (e.g. a test listing `read_file`, `write_file`, … `memory_write`) and add `todo_write` so the suite reflects the new baseline tool. If none exists, note that in the task and skip.
- [ ] T008 Run the four gates and confirm green: `ruff check`, `ruff format --check`, `mypy` (src, strict), `pytest`. Fix any issue introduced by this unit before committing.

## Dependencies

- T001, T002 (Foundational) → block everything.
- T003 → T004 (TDD: tests then implementation).
- T004 → T005, T006 (need the working handler/descriptor).
- T005, T006 → T007 → T008 (polish + gates last).

## Parallel opportunities

- Minimal: the feature spans only two files. T003 (test file) can be drafted alongside T001/T002 (source file) but must run after them to import the descriptor. T005 and T006 both extend the same test file, so run them sequentially, not in parallel.

## Implementation strategy

- **MVP = Phase 1 + Phase 2 (US1)**: a working, validated `todo_write` with replace semantics and the core test set. US2 and US3 are thin verification layers over the same handler/descriptor (no new production code expected).
- Keep all production changes inside `src/loopplane/tools/internal.py`; keep all new tests in `tests/unit/test_todo_tool.py`; the only other allowed edit is the existing descriptor-set assertion (T007).

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 2 low (informational). 100%
requirement coverage (FR-001..FR-011 each mapped to ≥1 task; SC-001..004 covered); every
task traces to a requirement/design item; spec ↔ plan ↔ data-model ↔ contract ↔ tasks
agree on the schema (todos array; `content` + `status` enum; `MAX_TODO_ITEMS=100`; replace
semantics; empty clears; normalized errors that never mutate on failure); no Constitution
violations (additive X, Gateway-only V, no event-schema/content-model change VI,
reference-not-clone IX, testable X). Low notes are informational only (FR-005 surfaces the
list via the tool-result, not the 010 overlay — research D5; `todo_write` is `read_only=False`
so plan mode denies it, which is the intended governance). **Cleared for `/speckit-implement`.**
