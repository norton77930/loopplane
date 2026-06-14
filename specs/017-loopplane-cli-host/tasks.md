---
description: "Task list for unit 017 — LoopPlane CLI Host"
---

# Tasks: LoopPlane CLI Host

**Input**: Design documents from `specs/017-loopplane-cli-host/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Write each test FIRST and confirm it FAILS
before the matching implementation.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create `src/loopplane/cli/` with an empty `__init__.py` placeholder.

---

## Phase 2: Foundational — renderer, providers, run core (BLOCKS user stories)

- [ ] T002 [P] Unit test `tests/unit/test_cli_render.py`: `EventRenderer` writes
  metadata-safe lines for assistant-output, tool-call, and run-terminated events
  and never raw tool I/O or exceptions (FR-004/FR-009). (FAIL first)
- [ ] T003 [P] Unit test `tests/unit/test_cli_providers.py`: `select_model` returns
  the built-in demo model with no env; imports an `LOOPPLANE_MODEL=module:function`
  builder when set; falls back to the demo on a bad reference without echoing a
  credential (FR-005/FR-006). (FAIL first)
- [ ] T004 Implement `src/loopplane/cli/render.py` — `EventRenderer` (an `EventSink`
  writing to an injected text stream).
- [ ] T005 Implement `src/loopplane/cli/providers.py` — a built-in **stateless demo
  `ModelBoundary`** (a canned response per turn, never exhausts, no network) and
  `select_model(env)`.
- [ ] T006 Implement `src/loopplane/cli/session.py` — `run_once(host, prompt, out)`
  and `chat_loop(host, lines, out)` over `LoopPlaneHost`. Depends on T004.
- [ ] T007 Implement `src/loopplane/cli/app.py` — `argparse` parser + `dispatch(argv)`
  for `chat` / `run` / `sessions` / `resume`. Depends on T004–T006.
- [ ] T008 Implement `src/loopplane/cli/__init__.py` — `main()` (the console entry
  point: parse → dispatch → `anyio.run`, returning an exit code) + `__all__`.

**Checkpoint**: renderer + providers unit tests pass.

---

## Phase 3: User Story 1 — interactive chat (P1) 🎯 MVP

- [ ] T009 [US1] Integration test `tests/integration/test_cli_us1.py`: `chat_loop`
  with scripted input lines + the demo model renders output per turn and ends
  cleanly on EOF/`quit` (FR-002, SC-001). (FAIL first)

---

## Phase 4: User Story 2 — one-shot run (P1)

- [ ] T010 [US2] Integration test `tests/integration/test_cli_us2.py`:
  `dispatch(["run", "<prompt>"])` renders the response + outcome and returns exit 0;
  a missing prompt returns a usage exit (FR-003, SC-002). (FAIL first)

---

## Phase 5: User Story 3 — list and resume sessions (P2)

- [ ] T011 [US3] Integration test `tests/integration/test_cli_us3.py`: with a
  configured durable store, `sessions` lists a prior session (public-safe) and
  `resume` continues it; with no store, a clear message (FR-007). (FAIL first)

---

## Phase 6: User Story 4 — real model when configured (P2)

- [ ] T012 [US4] Integration test `tests/integration/test_cli_us4.py`: with no
  `LOOPPLANE_MODEL`, the CLI runs on the demo model; with it pointing at a fake
  importable builder, the CLI uses that model (FR-006, SC-003). (FAIL first)

---

## Phase 7: User Story 5 — a safe, thin command (P3)

- [ ] T013 [US5] Integration test `tests/integration/test_cli_us5.py`: a run's
  rendered output carries no secret/credential/private path/raw exception; a failing
  run renders a public-safe outcome, not a traceback (FR-008/FR-009). (FAIL first)

---

## Phase 8: Boundary, packaging, and polish

- [ ] T014 [P] Boundary test `tests/integration/test_cli_boundary.py`:
  `loopplane.cli` imports only `loopplane.host` / `loopplane.model` /
  `loopplane.events` (plus stdlib/anyio); it executes no tool and re-emits no bus.
- [ ] T015 Add `[project.scripts] loopplane = "loopplane.cli:main"` to `pyproject.toml`.
- [ ] T016 [P] Add `examples/cli_quickstart.py` — drive `run_once` with the demo model
  and capture the rendered output (credential-free).
- [ ] T017 [P] Add `docs/cli.md` — the CLI guide.
- [ ] T018 Update `docs/api-reference.md` with the `loopplane.cli` public names
  (unit-014 `test_api_reference` enforces the `__all__` bijection).
- [ ] T019 Update `docs/README.md` and `examples/README.md` indexes (unit-014
  `test_docs_examples_index` enforces index↔tree).
- [ ] T020 Run `ruff format --check`, `ruff check`, `mypy` (strict), and the full
  `pytest` suite (including the unit-014 packaging contract); fix to green.
- [ ] T021 Final review: set unit 017 to **Verified** in
  `docs/loopplane-agent-board.md` (§3 row + §4) and commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (renderer/providers/session/app/`main`) blocks the user stories.
  US1–US5 (Phases 3–7) exercise the CLI core end-to-end and are independently
  testable. Phase 8 depends on the desired stories; T015/T018/T019 keep the unit-014
  packaging / api-reference / index contracts green.

### Parallel opportunities

- T002/T003 (unit tests) run in parallel.
- T014/T016/T017 (boundary test, example, docs) run in parallel.

## Notes

- The CLI composes only `loopplane.host`; it executes no tool and re-emits no bus
  (FR-008). It adds an entry point + a `loopplane.cli` package and changes no prior
  contract; unused, the runtime is unchanged (FR-010/SC-005).
- Credential-free default: the built-in demo model runs offline; a real provider is
  the env-pointed `LOOPPLANE_MODEL` builder seam (its network path validated manually).
