# Tasks: Weighted Tenant Turns

**Input**: spec, plan, research, data-model, contracts and quickstart in this directory.
**Tests**: Required; focused RED before each corresponding implementation phase.
**Scope**: One active writer; no commits/branches/worktrees/deployment.

## Phase 1: Setup

- [x] T001 Validate scope, prerequisites and checklist in specs/087-weighted-tenant-turns/checklists/requirements.md.
- [x] T002 Refresh managed agent context and record design analysis in specs/087-weighted-tenant-turns/implementation-evidence.md.

## Phase 2: Foundation

- [x] T003 Add failing policy/share/cap checks in tests/unit/test_weighted_tenant_turns.py (FR-002..007).
- [x] T004 Implement immutable policy and deterministic selection/state helpers in src/loopplane/fairness_weighted.py; rerun T003.

## Phase 3: US1 - Weighted starts (P1)

Goal: proportional starts, tenant rather than request entitlement, visibility across workers.
Independent test: complete-cycle 3:1 counts, FIFO/flooding and worker-layout equivalence.

- [x] T005 [US1] Add failing async store/fairness tests for shares, multi-tenant visibility and distinct grants in tests/unit/test_weighted_tenant_turns.py (FR-002/003/005/009/010).
- [x] T006 [US1] Implement memory store and explicit fairness composition in src/loopplane/fairness_weighted.py; rerun T005.
- [x] T007 [US1] Add failing cross-instance durable scheduling tests in tests/unit/test_weighted_tenant_postgres.py with tests/weighted_pg_stub.py (FR-003/008/009/015).
- [x] T008 [US1] Implement dedicated atomic Postgres state in src/loopplane/fairness_weighted_postgres.py; rerun T007.

## Phase 4: US2 - Preserve protection (P1)

Goal: same admission/cap/default behavior. Independent test: existing regression suite plus weighted admission.

- [x] T009 [US2] Add weighted admission and active/consecutive-cap checks in tests/unit/test_webapi_admission.py and tests/unit/test_weighted_tenant_turns.py (FR-001/004/012).
- [x] T010 [US2] Run unchanged 072/086 and updated 085 tests; correct only new weighted implementation in src/loopplane/fairness_weighted.py if needed.

## Phase 5: US3 - Recovery (P1)

Goal: bounded progress without leaked grants or replay. Independent test: cancellation/expiry/outage/body exception scenarios.

- [x] T011 [US3] Add failing cancellation/expiry/no-idle-credit/outage/body-error checks in tests/unit/test_weighted_tenant_turns.py and tests/unit/test_weighted_tenant_postgres.py (FR-005/006/010/011).
- [x] T012 [US3] Complete shielded cleanup, waiter renewal and acquisition-only degradation in src/loopplane/fairness_weighted.py and src/loopplane/fairness_weighted_postgres.py; rerun T011.

## Phase 6: US4 - Configuration and privacy (P2)

Goal: immutable consistent configuration and safe errors. Independent test: invalid/mismatched settings and redaction.

- [x] T013 [US4] Test mutation isolation, invalid/mismatched maps/caps, missing extra and safe representations in tests/unit/test_weighted_tenant_turns.py and tests/unit/test_weighted_tenant_postgres.py (FR-007/008/014).
- [x] T014 [US4] Complete policy validation and safe failure handling in src/loopplane/fairness_weighted.py and src/loopplane/fairness_weighted_postgres.py; rerun T013.

## Phase 7: Polish and verification

- [x] T015 Document public symbols, activation, cap precedence and rollback in docs/api-reference.md and specs/087-weighted-tenant-turns/quickstart.md (FR-004/013/014).
- [x] T016 Update docs/capabilities.md, docs/gap-analysis.md and docs/loopplane-agent-board.md with actual delivered scope (FR-015).
- [x] T017 Run focused suite, ruff format/check, mypy, full pytest, lock/dependency checks, docs/import/public-safety contracts and git diff --check; record literal outcomes in specs/087-weighted-tenant-turns/implementation-evidence.md (FR-001/012..015).
- [x] T018 Review requested behavior and architecture standards separately, resolve findings, rerun affected checks and record final status in specs/087-weighted-tenant-turns/implementation-evidence.md; mark board Verified only with evidence.

- [x] T019 Repair the preexisting incomplete host test double exposed by T017 in tests/integration/test_webapi_us1.py; retain its 409 assertion, rerun the isolated check and full validation. No product behavior change.

## Dependencies and execution

T001 -> T002 -> T003/T004 -> T005/T006 -> T007/T008 -> US2 -> US3 -> US4 -> polish.
T019 was discovered during T017 validation and must close before T017/T018 finish.
Single writer serializes edits; independent read-only reviews may run alongside work.
No [P] implementation tasks: these phases share the two new implementation files.
MVP is US1 memory scheduling after foundation; full unit includes durable/recovery
and protection coverage. Rollback restores original fairness construction after drain.

## Coverage

FR-001:T009/010/017; FR-002/003:T003..008; FR-004:T003/009/015;
FR-005/006:T003/005/011/012; FR-007:T003/004/013/014;
FR-008:T007/008/013/014; FR-009:T005..008; FR-010:T005/011/012;
FR-011:T011/012; FR-012:T009/010/017; FR-013:T015/017;
FR-014:T013..015/017; FR-015:T007/016..018.
SC-001/002:T003..008/011; SC-003:T009/010; SC-004:T011/012; SC-005:T017.
