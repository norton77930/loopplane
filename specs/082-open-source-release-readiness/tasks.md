# Tasks: Open-Source Release Readiness

**Input**: Design documents from `specs/082-open-source-release-readiness/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, handoff.md

**Tests**: REQUIRED per Constitution Principle X. Test-first ordering is mandatory where a contract test guards an implementation task (US2, US5, US6).

**Organization**: Grouped by user story (US1–US7 from spec.md). Stories are independently implementable and revertible. Tasks tagged **[DEFER-078]** MUST NOT start until unit 078 is Verified on `docs/loopplane-agent-board.md`; tasks tagged **[GATE-§E]** require explicit maintainer approval first (per `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` §E).

## Phase 1: Setup

- [x] T001 [GATE-§E] With maintainer confirmation, create branch `082-open-source-release-readiness` from `main` (never from 078's branch); verify `git status` on the new branch is clean and that `.superpowers/**`, `openspec/**`, and 078 in-flight files are absent from any staging at all times
- [x] T002 Register the 082 row in `docs/loopplane-agent-board.md` following the format of rows 079–081 (status per board rules; coordinate with the maintainer if autopilot is active, since the board is its control document)

## Phase 2: Foundational

**Purpose**: Evidence and guard scaffolding used by every story. No other blocking work — stories are independent by design.

- [x] T003 Create `specs/082-open-source-release-readiness/implementation-evidence.md` with: fresh baseline §G gate results on the clean branch (`uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest -q` — literal counts), a per-story evidence section, and a "078 no-touch verification" checklist (end of every story: review `git status` and confirm no file from the FR-016 set was touched)

**Checkpoint**: Baseline recorded — user stories can proceed (US1/US2 first per priority, or in parallel where staffing allows).

---

## Phase 3: User Story 1 - Install and run from a published package (Priority: P1)

**Goal**: `loopplane` installable from built artifacts (and later the index) with complete, truthful metadata.

**Independent Test**: quickstart.md §US1 — fresh-venv install of the built wheel + credential-free quickstart succeeds without the repo checkout.

- [x] T004 [US1] Extend `.github/workflows/ci.yml`: after the existing `uv build` step, add distribution metadata validation via `uvx twine check dist/*` (at minimum on the ubuntu job); keep the workflow's existing trigger set and permissions unchanged
- [x] T005 [P] [US1] Update `README.md`: add truthful badges (CI status, MIT license, Python 3.12+ — PyPI version badge only after first publish), rewrite the Install section (index-install as primary path with honest "pending first publish" interim wording; clone as contributor path), add an extras matrix table (which extras for which deployment), and cross-link `GOVERNANCE.md` / `CONTRIBUTING.md`
- [x] T006 [US1] Validation per SC-001: `uv build`; `uvx twine check dist/*`; create a fresh Python 3.12 venv, `pip install` the built wheel with `[web]` plus one provider extra, run `examples/host_quickstart.py` and the `loopplane` console script; record the literal transcript in `specs/082-open-source-release-readiness/implementation-evidence.md`
- [x] T007 [US1] [DEFER-078] Complete `pyproject.toml` metadata per FR-001: add `Changelog`/`Issues`/`Documentation` project URLs and an operating-system classifier following current PyPA guidance for the existing SPDX license expression; re-run `uv build` + `uvx twine check dist/*`
- [ ] T008 [US1] [DEFER-078] [GATE-§E] Only if the maintainer approves (research.md R5): add the `all` convenience extra (union of the nine existing extras) to `pyproject.toml`; if rejected, confirm the README extras matrix from T005 covers the need and record the decision in implementation-evidence.md

**Checkpoint**: US1 deliverable except its two [DEFER-078] tasks; the deferral is recorded in evidence, not silently dropped.

---

## Phase 4: User Story 2 - One-command tagged release (Priority: P1) 🎯 MVP

**Goal**: Tag push → validated, idempotent, fail-closed build/publish/release automation; publish inert (dry-run) until the maintainer configures the trusted publisher.

**Independent Test**: quickstart.md §US2 — local sync-check PASS/FAIL demonstration plus a `workflow_dispatch` dry-run that builds and validates without publishing.

- [x] T009 [P] [US2] Write `tests/contract/test_release_sync.py` FIRST (red): asserts tag/`loopplane.__version__` match, missing/invalidly-dated `CHANGELOG.md` section detection, all referenced release units are present and `Verified` on the board, notes extraction to stdout, rejection of non-`vX.Y.Z` refs, and non-zero exit with one-line diagnostics per failure (see data-model.md §3)
- [x] T010 [US2] Implement `scripts/release_sync_check.py` (Python stdlib only, no network) to turn T009 green; failure-help text names the runbook for the remaining non-mechanical checks from `docs/architecture/RELEASE_SYNC_RULES.md`
- [x] T011 [US2] Create `.github/workflows/release.yml` per `contracts/release-automation.md` plus committed `tests/contract/test_release_workflow.py` guards: `v*` tag push trigger (+ `workflow_dispatch` structurally unable to reach publish and checking out its requested tag for validate/build); jobs validate → build → publish → release; workflow-level `permissions: contents: read` with exact per-job elevation (`id-token: write` publish, `contents: write` release); PyPA trusted-publishing action with `skip-existing: true`; no dot/bracket `secrets` context; fork guard; dry-run mode defaulting ON via repository variable with its state shown in the run summary; `gh release create` fed by the validator's extracted notes
- [x] T012 [P] [US2] Write `docs/release-process.md`: the human-gated runbook (§E) — bump `src/loopplane/__init__.py` `__version__`, promote the CHANGELOG section, sync the board per `RELEASE_SYNC_RULES.md`, tag, watch the workflow, post-verify install; include the one-time maintainer setup for the PyPI trusted publisher and the recommended `v0.5.0` scope (064–081, plus 078 if Verified)
- [x] T013 [US2] Validation per SC-002: run quickstart §US2 locally (`v0.4.0` PASS, `v9.9.9` FAIL with diagnostics); the `workflow_dispatch` dry-run half requires the branch to be pushed — if implementation runs unpushed, record the local half now and complete the workflow-run evidence at push/PR time (deferral noted in implementation-evidence.md, not dropped)

**Checkpoint**: Release machinery complete and demonstrably inert — MVP for this unit.

---

## Phase 5: User Story 3 - Governance and contributor safety (Priority: P2)

**Goal**: Outside contributors can see who decides what, which paths need maintainer review, and which "flaws" are load-bearing and must not be fixed.

**Independent Test**: spec.md US3 acceptance — review walkthrough of the three documents plus CODEOWNERS routing.

- [x] T014 [P] [US3] Write `GOVERNANCE.md`: roles and decision rights; the concrete meaning of every "maintainer approval" gate (§E map: schema/SPI/default/dependency/extras changes, outward API contract, releases); how gate approval is recorded; relationship to `AGENTS.md` and the constitution
- [x] T015 [P] [US3] Write `.github/CODEOWNERS` (same home as the existing issue/PR templates): route `src/loopplane/model/`, `src/loopplane/errors.py`, `src/loopplane/events/`, `src/loopplane/context.py`, `src/loopplane/gateway/`, `src/loopplane/host/assembly.py`, `.github/workflows/`, `docs/architecture/`, `docs/adr/`, and `.specify/memory/constitution.md` to the maintainer
- [x] T016 [US3] Extend `CONTRIBUTING.md` with the hazard-map section per FR-008: the two sanctioned TYPE_CHECKING cycles (`context ⇄ tools` R1, `host ⇄ tools` R4) and why converting lazy imports is forbidden; the boundary-guard test system (and the coming declarative matrix); the §E gates; default-off/byte-identity; public-safety (Constitution VII) checklist; English-docs rule
- [x] T017 [US3] [DEFER-078] FR-009: after 078's board transition, check `docs/loopplane-agent-board.md` ADR-0015 status text; if it still says Proposed anywhere, align the wording with the ADR file's Accepted status (docs-only; change no completion-status value; skip and record if 078's closure already fixed it)

**Checkpoint**: Governance docs complete except the [DEFER-078] board-text check.

---

## Phase 6: User Story 4 - Public documentation coverage (Priority: P2)

**Goal**: Every capability category (units 021–081) reachable from `docs/README.md` within one click via five thematic guides.

**Independent Test**: quickstart.md §US4 — offline link-check green plus the one-click reachability walkthrough.

- [x] T018 [P] [US4] Write `docs/guides/agent-tools-and-permissions.md` (units 033, 034, 036, 038, 039, 044–047, 052, 054, 065–066, 069): file/web/todo/notebook/undo tools, multimodal image + PDF input, plan mode, permission rule DSL and modes, sandbox execution, slash commands; unit anchors; defer to `docs/capabilities.md` + `docs/api-reference.md` (provider units 035/037/070 belong to `docs/model-providers.md`, not here)
- [x] T019 [P] [US4] Write `docs/guides/autonomy-and-multi-agent.md` (units 013, 043, 048–051): orchestration, dynamic subagents, background tasks, scheduling, messaging/swarm, worktree isolation; emphasize cap-gated default-off posture
- [x] T020 [P] [US4] Write `docs/guides/cost-governance.md` (units 040–042, 053, 055, 062–064, 068): caching, compaction, pricing, budget caps, USD ledger, monthly caps, cost surfacing, pre-turn guard
- [x] T021 [P] [US4] Write `docs/guides/platform-and-deployment.md` (units 011, 022, 056–061, 067, 071–072): webapi deployment shape, auth (token/JWT/JWKS), MCP transports/resources, SSE reconnect + replay store, Postgres backends, tenant host pool, fairness
- [x] T022 [P] [US4] Write `docs/guides/web-ui-product.md` (units 018, 023, 025–032, 074–077, 080–081): the SPA product surface, session management, inspection, capability management, a11y/visual state
- [x] T023 [US4] Update `docs/README.md`: index the five guides + `docs/release-process.md`; verify each capability category in `docs/capabilities.md` maps to an indexed guide — including categories served by EXISTING guides (model providers 020/035/037/045/070 → `docs/model-providers.md`, extend it if those rows are not reflected; runtime core / hosts / desktop → the existing ≤020 layer guides) — and record the category→guide mapping in implementation-evidence.md
- [x] T024 [US4] Write `tests/contract/test_docs_links.py`: stdlib-only walker validating relative links and intra-repo anchors across `docs/**/*.md` + `README.md` (external URLs collected, not fetched); run green

**Checkpoint**: Docs coverage complete and mechanically link-checked.

---

## Phase 7: User Story 5 - Declarative import-boundary gate (Priority: P3)

**Goal**: One default-deny, auto-discovering boundary contract covering all packages (closes R10); existing 17 guards untouched.

**Independent Test**: quickstart.md §US5 — matrix green on current tree; three negative self-tests demonstrably fail on seeded violations.

- [x] T025 [US5] Seed the matrix: derive `{package → allow_runtime / allow_type_checking / allow_function_scoped (+ rule note)}` from `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` and the 17 existing guard tests; reconcile against current code (code + existing guards win); record every discrepancy found in implementation-evidence.md
- [x] T026 [US5] Implement `tests/contract/test_import_matrix.py` per `contracts/boundary-gate.md`: AST walker (reuse the `tests/contract/test_tools_boundary.py` approach), package auto-discovery over `src/loopplane/*/` plus top-level modules, default-deny for undeclared packages, orphan-entry detection, failure messages naming file/line/edge/rule
- [x] T027 [US5] Add the three negative self-tests in the same module (seeded forbidden edge on synthetic source; synthetic undeclared package; TYPE_CHECKING-only edge used at runtime) and prove each fails correctly; then full-tree pass green
- [x] T028 [US5] Landing checkpoint: before merging, confirm with the maintainer the landing order relative to 078's Stage-C delivery review (handoff.md §8 decision 5); record the decision in implementation-evidence.md

**Checkpoint**: R10 closed additively.

---

## Phase 8: User Story 6 - Internal decomposition of oversized modules (Priority: P3)

**Goal**: `webapi/app.py` split into per-domain routers with a test-enforced byte-identical outward contract; `capability_manager.py` decomposition deferred behind 078.

**Independent Test**: quickstart.md §US6a — snapshot + boundary + full gates green before AND after the split.

- [x] T029 [US6] Write `tests/contract/test_webapi_route_snapshot.py` FIRST per `contracts/webapi-route-snapshot.md`: checked-in sorted route inventory (methods, path, endpoint `__name__`, response-model class name, status code) + canonicalized `app.openapi()` JSON equality + `inspect.signature(create_app)` surface assert; green against the CURRENT `src/loopplane/webapi/app.py`
- [x] T030 [US6] Re-file `src/loopplane/webapi/app.py` route groups into `src/loopplane/webapi/routers/` modules (sessions, streaming/live, interaction, capabilities, inspect, cost, misc: models/uploads/commands) mounted by `create_app()`; behavior, keyword surface, and shared helpers preserved; `app.py` shrinks to composition + helpers
- [x] T031 [US6] Prove invariance per SC-004: T029 snapshot green unchanged, `tests/contract/test_webapi_boundary.py` green, full §G gates green with literal counts in implementation-evidence.md; explicitly record "no §E outward-contract gate triggered"
- [ ] T032 [US6] [DEFER-078] Decompose `src/loopplane/host/capability_manager.py` into cohesive submodules preserving the `loopplane.host` public surface semantics; full §G gates green; only after 078 is Verified on the board

**Checkpoint**: webapi hotspot resolved; host hotspot queued behind 078.

---

## Phase 9: User Story 7 - Architecture-audit refresh and verified test-debt backfill (Priority: P3)

**Goal**: Audit trustworthy again; test backfill spent only on confirmed gaps.

**Independent Test**: quickstart.md §US7 — refreshed audit rows spot-check true; new tests green; non-tautology demonstrated.

- [x] T033 [US7] Refresh `docs/architecture/ARCHITECTURE_AUDIT.md` per its own conventions (read-only snapshot, evidence tags, new snapshot commit + date): correct rows proven stale (controller/errors/engineering test files exist since 2026-07-07), re-verify every test-gap row against `tests/`, and re-verify the doc-staleness table against the current docs set
- [x] T034 [US7] Backfill ONLY refresh-confirmed gaps with `tests/unit/test_<pkg>_*.py` per G7 conventions (candidates from the stale table to re-verify first: controller checkpoint-recording boundary and dispatcher depth, `engineering/`, `memory/`, `skills/`); no production-code change; suite green
- [x] T035 [US7] Non-tautology check per spec US7 acceptance 3: a temporary local mutation of one newly covered behavior makes ≥1 new test fail; revert the mutation (never committed); record procedure + result in implementation-evidence.md

**Checkpoint**: All seven stories delivered or explicitly deferred with evidence.

---

## Phase 10: Polish & Cross-Cutting

- [x] T036 Append additive `[Unreleased]` entries to `CHANGELOG.md` for this unit's delivered stories (coordinate-merge-friendly: additive lines only, no re-ordering of existing entries)
- [x] T037 Public-safety scan per SC-007 over every file added/changed by this unit (patterns: internal/company paths, private names, secrets, absolute local paths); record zero-hit evidence in implementation-evidence.md
- [x] T038 Run the full `quickstart.md` validation pass + fresh §G gates (`ruff format --check`, `ruff check`, `mypy`, `pytest -q`, `uv build`); literal counts in implementation-evidence.md; re-run known flakes (`tests/integration/test_examples_smoke.py`, `test_us2_mcp`) in isolation before judging
- [x] T039 Final 078 no-touch verification: review `git status` / staged list confirming no FR-016 file was modified; then produce the completion report per `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` §H (what changed, literal results incl. failures/skips, §E gates touched + approval records, limitations, deferred tasks list)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → all story phases.
- **Stories (Phases 3–9)** are mutually independent; recommended order = priority order (US1 → US2 → US3 → US4 → US5 → US6 → US7), but any story may proceed once Phase 2 is done.
- **Polish (Phase 10)** requires all non-deferred story tasks complete.

### Cross-cutting gates

- **[DEFER-078]** tasks (T007, T008, T017, T032) additionally require: 078 Verified on the board. They stay unchecked with a recorded deferral note if the unit completes before 078 does.
- **[GATE-§E]** tasks (T001, T008) additionally require: recorded maintainer approval. The release cut itself is NOT a task in this unit — it is the maintainer's action per `docs/release-process.md`.
- T028 (US5) and the landing of T030 (US6) SHOULD be sequenced with the maintainer relative to 078's Stage-C review (handoff.md §8, decision 5).

### Within-story orderings

- US2: T009 (red) → T010 (green) → T011 → T013; T012 parallel after T010.
- US5: T025 → T026 → T027 → T028.
- US6: T029 (snapshot first) → T030 → T031; T032 independent, deferred.
- US7: T033 → T034 → T035.

### Parallel opportunities

- After Phase 2: T004/T005 (US1), T009/T012 (US2), T014/T015 (US3), T018–T022 (US4) are all [P]-safe across different files.
- The five US4 guides (T018–T022) are fully parallel.
- US3's T014/T015 are parallel; T016 follows (single file each, no conflicts).

## Implementation Strategy

- **MVP**: Phase 1–2 + **US2** (fully executable now, highest leverage: release machinery + runbook). Then US3 and US4 (also fully executable). US1 delivers T004–T006 now and leaves T007/T008 flagged deferred.
- **Incremental**: land each story as one revertable unit of work; stop at any checkpoint and validate via quickstart.md.
- **Deferred tail** (T007, T008, T017, T032 + the maintainer's release cut) executes after 078 is Verified — tracked, not forgotten, via the deferral notes in implementation-evidence.md.
