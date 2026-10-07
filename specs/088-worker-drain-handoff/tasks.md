# Tasks: Worker Drain Handoff

**Input**: spec, plan, research, data-model, contracts and quickstart in this directory.
**Tests**: Required; one focused RED before the coordinator change.
**Scope**: One active writer. No push, release, or deployment.

## Phase 1: Specify and plan

- [x] T001 Write spec, checklist, plan, research, data-model, contract, and quickstart in specs/088-worker-drain-handoff.
- [x] T002 Point `.specify/feature.json` at this directory and refresh the managed agent-context block.

## Phase 2: Handoff behavior

- [x] T003 Add failing drain, in-flight release, peer takeover, and end-drain checks in tests/unit/test_webapi_admission.py (FR-001..007, FR-010).
- [x] T004 Implement `begin_drain` / `end_drain` and the pre-take refusal in src/loopplane/webapi/admission.py; rerun T003.

## Phase 3: Record the slice

- [x] T005 Document the two methods in docs/api-reference.md and record the unit on the agent board and in gap C2/C4, leaving mid-turn migration open.
- [x] T006 Run the focused admission tests and `git diff --check`. Write specs/088-worker-drain-handoff/implementation-evidence.md.
