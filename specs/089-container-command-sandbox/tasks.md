# Tasks: Container Command Sandbox

**Input**: spec, plan, research, data-model, contract, and quickstart in this directory.
**Tests**: Required; one focused RED before the executor exists.
**Scope**: One active writer. No push, release, or deployment.

## Phase 1: Specify and plan

- [x] T001 Write spec, checklist, plan, research, data-model, contract, quickstart, and ADR 0022.
- [x] T002 Point `.specify/feature.json` at this directory and refresh the managed agent-context block.

## Phase 2: Container behavior

- [x] T003 Add failing confinement, timeout, and fail-closed checks in `tests/unit/test_container_executor.py` (FR-001..FR-010).
- [x] T004 Implement `DockerCommandExecutor` in `src/loopplane/tools/container.py`, export it, and add the `docker` extra. Rerun T003.

## Phase 3: Record the slice

- [x] T005 Document the executor, update the packaging pin, and record the unit on the board, changelog, capabilities, and gap C2/C4.
- [x] T006 Run the focused tests, packaging, mypy, and Ruff. Write `implementation-evidence.md`.
