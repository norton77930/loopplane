# Tasks: Worktree Isolation

**Feature**: 051-worktree-isolation | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive, cross-cutting — a new `tools/worktree.py` (GitRunner seam + WorktreeManager +
3 tools) + `RunContext`/`RuntimeConfig` fields + controller/dispatcher/host/assembly wiring +
export + api-reference + tests. Default-off (`max_worktrees = 0`) byte-identical. Worktrees live
under a managed area of the working scope (001/002 confinement preserved). **No task group** (git
ops are synchronous; `cleanup()` at scope exit instead of `cancel_all`). Reuses the shell-execution
seam + the 048/049/050 manager + neutral-Protocol pattern. **No new ADR.**

**Tests**: requested (TDD-friendly; a throwaway git repo fixture / an injectable fake runner — no
network).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Add the gate `RuntimeConfig.max_worktrees: int = 0` to `src/loopplane/host/config.py`
  (coerce + validate non-negative int; no secret), mirroring `max_background_tasks`/`max_schedules`.
- [ ] T002 In `src/loopplane/context.py` add a neutral `WorktreeManager` Protocol + a
  `WorktreeManagerFactory` alias (the 048/049/050 pattern) and the additive field
  `RunContext.worktrees: WorktreeManager | None = None`. The controller/loop must reference the
  Protocol, never `loopplane.tools`.

## Phase 2: User Story 1 — Work in an isolated worktree (P1) 🎯 MVP

- [ ] T003 [US1] Create `src/loopplane/tools/worktree.py`: a `GitRunner` seam (production: the
  existing shell-execution path running `git -C <scope> …`; tests: a fake) and a `WorktreeManager`
  holding the working scope, a registry (`worktree_id -> Worktree(path, branch)`), the cap, and the
  runner. `create(branch=None) -> Worktree | error`: deny at the count cap; create under
  `<scope>/.loopplane-worktrees/<id>` via `git worktree add`; reject any path escaping the working
  scope; contain git failure as a normalized error. Add `make_worktree_manager[_factory]` (the 048
  `make_supervisor_factory` pattern) so the host assembly owns the tools import.
- [ ] T004 [US1] Add the `worktree_create` Gateway tool (descriptor + handler) reading
  `context.worktrees`; write `tests/unit/test_worktree_isolation.py` (a throwaway `git init` repo)
  asserting an isolated checkout is created and a change inside it leaves the main tree unchanged.

## Phase 3: User Story 2 — Inspect & remove (P2)

- [ ] T005 [US2] Add `worktree_list` + `worktree_remove` tools (descriptors + handlers + dispatch)
  over the registry: list reports id + path + branch (metadata); remove runs `git worktree remove`
  + prunes and drops the registry entry; unknown id → a clear normalized error.
- [ ] T006 [US2] Extend the tests: list metadata, remove deletes + prunes (gone from list),
  unknown-id error.

## Phase 4: User Story 3 — Bounded, confined, contained, lifecycle (P3)

- [ ] T007 [US3] Enforce the count cap + the working-scope confinement (reject escaping paths) +
  containment (non-git scope / git unavailable / failing git command / bad input → normalized
  public-safe error, never a raise); implement `cleanup()` removing all managed worktrees at the
  run/session scope exit (directories + git prune; no leak).
- [ ] T008 [US3] Extend the tests: count-cap denial, confinement rejection, non-git/git-failure
  containment, `cleanup()` lifecycle (no leak on disk), and **default-off byte-identity**
  (`max_worktrees = 0` → no tools registered).

## Phase 5: Wiring (scope owners thread the manager)

- [ ] T009 Wire additively (the 048/049/050 pattern, but `cleanup()` not `cancel_all`): optional
  `RuntimeController.drive(..., worktree_manager=None)` stamps it onto the `RunContext`; the
  **Dispatcher** builds a manager (when `max_worktrees > 0`) + calls `cleanup()` on close; the
  one-shot **`host.run`** builds one + calls `cleanup()` after `drive`; `host/assembly.py` registers
  the 3 tools + builds/injects the opaque manager factory only when `max_worktrees > 0`. The
  controller holds the opaque factory (typed via the context Protocol) — **no `loopplane.tools`
  import in controller/dispatcher**.
- [ ] T010 Export `WorktreeManager` + the tool adapter from `src/loopplane/tools/__init__.py` and
  add them to `docs/api-reference.md` (unit-014 bijection), mirroring 048/049/050.

## Phase 6: Polish & Cross-Cutting

- [ ] T011 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof + default-off byte-identity). ALSO confirm the structural
  audits stay green: `test_no_execution_path_outside_the_gateway` (controller/loop do not import
  `loopplane.tools`) and `test_public_safety` (no secret-looking literals).

## Dependencies

- T001, T002 → block all. T003 → T004 (MVP). T004 → T005 → T006. T003/T004 → T007 → T008.
  T002/T003 → T009. T003 → T010. T010 → T011 (gates last).

## Implementation strategy

- **MVP = Phase 1 + 2 (US1)** + T009 wiring. US2 adds inspect/remove; US3 adds safety + cleanup.
  The implement is cross-cutting but simpler than 048-050 (no task group) — a fork subagent MAY do
  the mechanical multi-file work (mirroring the now-correct 048/049/050 module + wiring, minus the
  task group), then the four gates + the two structural audits are verified + committed in the main
  session. ULTRACODE: an adversarial verification workflow runs before commit (GO/0 blocking).
- All changes additive; default-off (`max_worktrees = 0`) byte-identical; reuse the shell-exec seam
  + the working-scope confinement + the 048/049/050 threading; no new ADR.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
