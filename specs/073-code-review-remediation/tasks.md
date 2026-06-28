# Tasks: Code Review Remediation

**Input**: Design documents from `specs/073-code-review-remediation/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/remediation-contract.md`, `quickstart.md`, and
`docs/code-review-001-072.md`.

**Tests**: Required by Constitution Principle X. For behavior changes, write or
update the focused test first and verify it fails before implementation.

**Organization**: Tasks are grouped by review remediation story so each story
can be implemented and verified independently.

## Phase 1: Setup And Baseline Evidence

**Purpose**: Preserve the review report, confirm current failures, and ensure
the active Spec Kit feature is traceable.

- [x] T001 Record current git state and preserve the untracked review report in `docs/code-review-001-072.md`
- [x] T002 Verify P0 baseline failure for `uv sync --locked`
- [x] T003 Verify P0 desktop baseline failure with `npm --prefix apps/desktop run typecheck` and `npm --prefix apps/desktop test`
- [x] T004 [P] Confirm the 073 feature artifacts exist in `specs/073-code-review-remediation/`

---

## Phase 2: User Story 1 - Reliable Mainline Gates (Priority: P1)

**Goal**: Locked Python dependency sync, desktop build/test gates, and CI path
coverage are reliable.

**Independent Test**: `uv sync --locked`, desktop typecheck/test, and workflow
path inspection all pass.

### Tests And Verification For User Story 1

- [x] T005 [US1] Run `uv sync --locked` and confirm it fails because `uv.lock` is stale
- [x] T006 [US1] Run `npm --prefix apps/desktop run typecheck` and confirm stale web imports/state fields fail
- [x] T007 [US1] Run `npm --prefix apps/desktop test` and confirm stale web imports fail
- [x] T008 [US1] Validate desktop renderer regression expectations in `apps/desktop/src/__tests__/App.test.tsx`

### Implementation For User Story 1

- [x] T009 [US1] Regenerate `uv.lock` from current `pyproject.toml`
- [x] T010 [US1] Update `apps/desktop/src/App.tsx` to consume current web state/components or a minimal current-compatible desktop shell
- [x] T011 [US1] Add `apps/web/**` to desktop CI trigger paths in `.github/workflows/desktop.yml`
- [x] T012 [US1] Run `uv sync --locked`
- [x] T013 [US1] Run `npm --prefix apps/desktop run typecheck`
- [x] T014 [US1] Run `npm --prefix apps/desktop test`
- [x] T015 [US1] Run `npm --prefix apps/web run typecheck` and `npm --prefix apps/web test` to verify web compatibility

---

## Phase 3: User Story 2 - Public-Safe Tool Errors (Priority: P1)

**Goal**: MCP adapter and web-fetch errors preserve failure class without
leaking raw exceptions, full URLs, query secrets, credentials, or tracebacks.

**Independent Test**: Focused tests inject secret-like values into MCP and web
failures and assert model-visible output is public-safe.

### Tests For User Story 2

- [x] T016 [P] [US2] Add failing MCP call-tool exception sanitization test in `tests/unit/test_mcp_resources.py`
- [x] T017 [P] [US2] Add failing MCP read-resource exception sanitization test in `tests/unit/test_mcp_resources.py`
- [x] T018 [P] [US2] Add failing web-fetch secret URL validation/timeout/status tests in `tests/unit/test_web_tools.py`
- [x] T019 [P] [US2] Add failing web-fetch raw transport detail regression test in `tests/unit/test_web_tools.py`

### Implementation For User Story 2

- [x] T020 [US2] Replace raw MCP exception formatting with stable public-safe messages in `src/loopplane/adapters/mcp/adapter.py`
- [x] T021 [US2] Add public-safe URL/error formatting helper for web fetch in `src/loopplane/tools/web.py`
- [x] T022 [US2] Update invalid URL, timeout, transport, and non-2xx web-fetch errors to avoid full raw URL/query exposure in `src/loopplane/tools/web.py`
- [x] T023 [US2] Run `uv run pytest tests/unit/test_mcp_resources.py tests/unit/test_web_tools.py`

---

## Phase 4: User Story 3 - Bounded Web Fetch Resource Use (Priority: P2)

**Goal**: Web fetch bounds response content before output and cache reuse.

**Independent Test**: A large injected response returns bounded text and later
cache hits reuse only bounded content.

### Tests For User Story 3

- [x] T024 [US3] Add failing oversized response truncation test in `tests/unit/test_web_tools.py`
- [x] T025 [US3] Add failing oversized cache reuse test in `tests/unit/test_web_tools.py`
- [x] T026 [US3] Add within-limit response regression assertion in `tests/unit/test_web_tools.py`

### Implementation For User Story 3

- [x] T027 [US3] Add adapter-level web-fetch content cap and truncation marker in `src/loopplane/tools/web.py`
- [x] T028 [US3] Store only bounded web-fetch content in the session cache in `src/loopplane/tools/web.py`
- [x] T029 [US3] Run `uv run pytest tests/unit/test_web_tools.py`

---

## Phase 5: User Story 4 - Traceable Spec Kit Audit State (Priority: P2)

**Goal**: Historical verified-unit task drift is explicit, and new verified
units cannot silently keep unchecked tasks without an exception.

**Independent Test**: Contract test reports only documented historical
exceptions and fails on unapproved verified/incomplete drift.

### Tests For User Story 4

- [x] T030 [P] [US4] Create failing Spec Kit task audit contract test in `tests/contract/test_spec_task_audit.py`
- [x] T031 [P] [US4] Create durable historical exception document in `docs/spec-task-audit-exceptions.md`

### Implementation For User Story 4

- [x] T032 [US4] Implement audit logic in `tests/contract/test_spec_task_audit.py` using `docs/loopplane-agent-board.md`, `specs/*/tasks.md`, and `docs/spec-task-audit-exceptions.md`
- [x] T033 [US4] Populate `docs/spec-task-audit-exceptions.md` with public-safe historical exceptions from `docs/code-review-001-072.md`
- [x] T034 [US4] Run `uv run pytest tests/contract/test_spec_task_audit.py`

---

## Phase 6: User Story 5 - Frontend And Desktop Hardening Follow-Up (Priority: P3)

**Goal**: Current web test warnings are cleaned up, Electron renderer security
intent is explicit, and bundle-size warning is addressed or documented.

**Independent Test**: Web tests run without the current `act(...)` warnings,
Electron options are explicit, and the bundle warning has a documented outcome.

### Tests And Verification For User Story 5

- [x] T035 [US5] Reproduce current React `act(...)` warnings with `npm --prefix apps/web test`
- [x] T036 [US5] Update `apps/web/src/__tests__/AppRoot.test.tsx` to await settled app/login state without warnings
- [x] T037 [US5] Run `npm --prefix apps/web test` and confirm the current `act(...)` warnings are gone
- [x] T038 [US5] Add explicit Electron renderer security options in `apps/desktop/electron/main.ts`
- [x] T039 [US5] Run `npm --prefix apps/desktop run typecheck` and `npm --prefix apps/desktop test`
- [x] T040 [US5] Resolve the Vite chunk-size warning if small and scoped, otherwise document deferral in `docs/code-review-001-072.md`
- [x] T041 [US5] Run `npm --prefix apps/web run build`

---

## Phase 7: Final Review And Board Update

**Purpose**: Validate all remediation work and mark 073 consistently.

- [x] T042 Run `uv sync --locked`
- [x] T043 Run `uv run ruff check`
- [x] T044 Run `uv run ruff format --check src tests`
- [x] T045 Run `uv run mypy src`
- [x] T046 Run `uv run pytest`
- [x] T047 Run `npm --prefix apps/web run typecheck`
- [x] T048 Run `npm --prefix apps/web test`
- [x] T049 Run `npm --prefix apps/web run build`
- [x] T050 Run `npm --prefix apps/desktop run typecheck`
- [x] T051 Run `npm --prefix apps/desktop test`
- [x] T052 Run `git diff --check`
- [x] T053 Run changed-file `openspec/` and public-safety scans
- [x] T054 Update `docs/loopplane-agent-board.md` to include 073 remediation status after gates pass
- [x] T055 Update `docs/code-review-001-072.md` findings with remediation status and verification evidence
- [x] T056 Mark all completed 073 tasks `[x]` in `specs/073-code-review-remediation/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: Start immediately.
- **US1**: Blocks reliable final review and should complete before broad gates.
- **US2**: Can start after baseline evidence; should complete before public-safety final review.
- **US3**: Depends on `web_fetch` edits from US2.
- **US4**: Independent of source fixes but should complete before board update.
- **US5**: Lower priority; complete after P0/P1 fixes unless it becomes necessary for final gates.
- **Final Review**: Depends on all selected remediation stories.

### Parallel Opportunities

- T004 can run while baseline commands run.
- T016-T019 can be written in parallel if editing conflicts are coordinated.
- T024-T026 are all in `tests/unit/test_web_tools.py`; run sequentially in one editing pass.
- T030-T031 can run in parallel before T032-T033.

## Implementation Strategy

### MVP First

1. Complete Phase 1 baseline evidence.
2. Complete US1 gate restoration.
3. Complete US2 public-safe tool errors.
4. Validate focused gates before continuing to P2/P3.

### Incremental Delivery

1. P0 dependency/desktop/CI repair.
2. P1 public-safety adapter/tool repair.
3. P2 web-fetch resource bounding and Spec Kit auditability.
4. P3 frontend warning cleanup, Electron hardening, and bundle follow-up.
5. Full final review and board/report updates.
