# Tasks: Subagent Fan-out Cap

**Input**: spec, plan, research, data-model, contract, and quickstart in this directory.
**Tests**: Required. One focused RED before the counter existed.
**Scope**: One active writer. No push, release, or deployment. Do not mark Verified in this pass.

## Phase 1: Specify and plan

- [x] T001 Write spec, checklist, plan, research, data-model, contract, and quickstart.
- [x] T002 Point `.specify/feature.json` at this directory. The managed agent-context script was not re-run; `AGENTS.md` and `CLAUDE.md` already name `specs/090-subagent-fanout-cap/plan.md`.

## Phase 2: Spawn count

- [x] T003 Add failing tree-cap and missing-counter checks in `tests/unit/test_subagent_spawn.py` (FR-001, FR-002, FR-005, FR-007).
- [x] T004 Add `max_subagent_fanout`, `SubagentFanout`, and the shared assembly argument. Rerun T003.

## Phase 3: Record the slice

- [x] T005 Document the knob in the changelog, board, capabilities, gap tail, and autonomy guide.
- [x] T006 Run the focused spawn, messaging, and tools-boundary tests, plus mypy and Ruff on the touched files. Write `implementation-evidence.md`. The full suite stays outstanding, so the board status is Implemented.
- [x] T007 Move the counter to one object per root `drive`. A child reuses that object and does not mint another. A foreign object fails closed.
- [x] T008 Capture the run counter when background, schedule, or swarm admits work, and pass that object into the child host. A host built after `drive` returns still uses it. The full suite stays outstanding.
