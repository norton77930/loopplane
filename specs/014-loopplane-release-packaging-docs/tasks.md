---
description: "Task list for Release Packaging & Docs (014)"
---

# Tasks: Release Packaging & Docs

**Input**: Design documents from `/specs/014-loopplane-release-packaging-docs/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each story writes its **contract test first** (it must
FAIL before the artifact exists), then creates the artifact until green. Every check runs **in-process /
offline** — no network, no upload.

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases PA–PF map below; US1 (a
buildable, typed, single-version distribution) is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency.

## Non-breaking reminder (every task)

This unit is **strictly additive and non-breaking**. It MUST NOT edit any layer's public surface
(`src/loopplane/<layer>/__init__.py` `__all__`) or any runtime module's behavior, and MUST NOT add a
runtime dependency. The **only** code additions are the `py.typed` marker and the version single-sourcing
in `pyproject.toml` + `src/loopplane/__init__.py` (the literal is kept as the single source). Permitted
edits: `pyproject.toml` (metadata + version wiring), the docs, `CHANGELOG.md`, `.github/workflows/ci.yml`,
and the new `tests/contract/` modules. Every committed file is public-safe (Constitution VII). See
[contracts/](./contracts).

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Add `tests/release_helpers.py`: small shared helpers for the contract tests — load `pyproject.toml` via `tomllib`; discover the `loopplane` packages that declare `__all__` (AST over each `src/loopplane/**/__init__.py`, import-free); list `docs/*.md` and `examples/*.py`. No product code.
- [X] T002 Ensure `.gitignore` ignores build artifacts (`/dist/` already present; added `/build/` + `*.egg-info/`) so a local `uv build` never commits a distribution.

**Checkpoint**: shared test helpers ready; build output is git-ignored.

---

## Phase 2: User Story 1 - A buildable, installable, typed distribution (Priority: P1) 🎯 MVP

**Goal**: complete packaging metadata, a single-source version, and a shipped `py.typed` so the package
builds (sdist + wheel) offline, installs, types, and reports one version.

**Independent Test**: `test_packaging.py` green; `uv build` produces an sdist + wheel offline with
`loopplane/py.typed` in the wheel.

- [X] T003 [P] [US1] Write `tests/contract/test_packaging.py` (5 tests): metadata completeness (`name`, `description`, `readme`, `requires-python`, `authors`, `keywords`, `classifiers`, `[project.urls]`); **no** literal `version` under `[project]`; `dynamic` includes `"version"`; `[tool.hatch.version].path` == `src/loopplane/__init__.py`; `loopplane.__version__` is a non-empty version string; the runtime `dependencies` set is unchanged (`anyio`/`pydantic`/`jsonschema`) and the optional-extras keys (`mcp`/`otel`/`web`) are preserved; `src/loopplane/py.typed` exists; every public subpackage imports (FR-001–FR-004; SC-001/006).
- [X] T004 [US1] Updated `pyproject.toml`: added public-safe `authors = [{name = "LoopPlane contributors"}]` (no PII), `keywords`, trove `classifiers` (Development Status :: 4 - Beta, Intended Audience, `Programming Language :: Python :: 3.12`, `Typing :: Typed`; no `License ::` yet), `[project.urls]` (public repo home); switched `[project]` to `dynamic = ["version"]`, removed the literal `version`, added `[tool.hatch.version] path = "src/loopplane/__init__.py"` and `[tool.hatch.build.targets.wheel] packages = ["src/loopplane"]`. **No new runtime dependency** (research D1/D2/D7).
- [X] T005 [P] [US1] Add `src/loopplane/py.typed` (empty PEP 561 marker) (FR-003; research D3).
- [X] T006 [US1] `pytest tests/contract/test_packaging.py` → **5 passed**; `uv build` → `dist/loopplane-0.1.0.tar.gz` + `loopplane-0.1.0-py3-none-any.whl` built offline; the wheel name **0.1.0** (with no `[project] version`) confirms the single source; the wheel ships `loopplane/py.typed` + all subpackages (138 entries) (SC-001).

**Checkpoint**: MVP — the distribution builds, types, and reports one version.

---

## Phase 3: User Story 2 - A public API reference that cannot drift (Priority: P2)

**Goal**: a metadata-only API reference of every shipped package's public surface, checked against the
code so it cannot drift.

**Independent Test**: `test_api_reference.py` green — every `loopplane` package with `__all__` is
documented and each package's documented names **==** its `__all__`.

- [X] T007 [P] [US2] Write `tests/contract/test_api_reference.py` (3 tests): discover the `loopplane` packages that declare `__all__`; parse `docs/api-reference.md` (heading ``### `loopplane.x` `` + bullets ``- `Name` — …``); assert the documented-package set **==** the discovered set, per package the listed-name set **==** that package's `__all__` (bijection), and the doc has no fenced code block (metadata-only) (FR-010–FR-012; SC-002).
- [X] T008 [US2] Create `docs/api-reference.md`: every `loopplane` package that declares `__all__` (25 — the 12 roadmap layers + 13 Phase-1 foundation packages), grouped (Runtime foundation / Host interface / Loop-engineering & layers), each public name with a one-line description. Names generated from the actual `__all__` values; metadata-only (research D4).
- [X] T009 [US2] Run `pytest tests/contract/test_api_reference.py` → **3 passed** (no drift across all 25 packages; every layer represented).

**Checkpoint**: US1 + a drift-proof public API reference.

---

## Phase 4: User Story 3 - A navigable getting-started surface (Priority: P3)

**Goal**: a release-quality README, a getting-started guide, and docs/examples indexes that stay
consistent with the files that ship.

**Independent Test**: `test_docs_examples_index.py` green — the docs index links every `docs/*.md`, the
examples index lists every `examples/*.py`, no missing/dangling entry, README links resolve.

- [ ] T010 [P] [US3] Write `tests/contract/test_docs_examples_index.py` (MUST FAIL first): the set of guides linked from `docs/README.md` **==** the `docs/*.md` set (minus the index itself); the set of examples listed in `examples/README.md` **==** the `examples/*.py` set; every link/entry targets a file that exists (no dangling) and none is missing; `README.md` contains a quickstart link (→ `docs/getting-started.md`) and a docs link (→ `docs/README.md`) that both resolve (FR-020–FR-022; SC-005).
- [ ] T011 [P] [US3] Create `docs/README.md` (docs index): link every per-layer guide present under `docs/` (the existing layer guides + `api-reference.md` + `getting-started.md`); `release-readiness.md` is added in US5 (T022).
- [ ] T012 [P] [US3] Create `examples/README.md` (examples index): every `examples/*.py` with a one-line description and a `python examples/<name>.py` run command.
- [ ] T013 [P] [US3] Create `docs/getting-started.md`: install (`uv sync` / `pip install loopplane`), run the smallest end-to-end example (reference `examples/host_quickstart.py` / `examples/loop_quickstart.py`), document the local quality-gate commands (ruff format --check / ruff check / mypy / pytest), and link out to the per-layer guides and examples.
- [ ] T014 [P] [US3] Rewrite `README.md` to release quality: overview, install, a quickstart link (→ `docs/getting-started.md`), a layer map (001–013), a docs link (→ `docs/README.md`), and a **License** section naming the deferred license gate. Public-safe.
- [ ] T015 [US3] Run `pytest tests/contract/test_docs_examples_index.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US3 — installable, typed, documented, navigable.

---

## Phase 5: User Story 4 - Reproducible quality gates in CI (Priority: P4)

**Goal**: the CI definition runs the canonical gates + an offline build; the same gates run locally.

**Independent Test**: `test_ci_gates.py` green — the workflow runs format-check + lint + strict types +
tests + an offline build, no secret.

- [ ] T016 [P] [US4] Write `tests/contract/test_ci_gates.py` (MUST FAIL first if the build step is absent): read `.github/workflows/ci.yml`; assert it runs ruff `format --check`, ruff `check`, `mypy`, `pytest`, and an offline `uv build`; assert no secret token pattern is referenced (FR-030/FR-031; SC-003).
- [ ] T017 [US4] Update `.github/workflows/ci.yml`: add an offline `uv build` step (build the sdist + wheel; **no upload**) after the gates; confirm the four canonical gates remain. No secret.
- [ ] T018 [US4] Run `pytest tests/contract/test_ci_gates.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US4 — gates encoded and reproducible.

---

## Phase 6: User Story 5 - Release-readiness: public-safe audit and changelog (Priority: P5)

**Goal**: a public-safe changelog, a release-readiness checklist, and a clean repo-wide public-safety
audit.

**Independent Test**: `test_changelog.py` green; the docs index includes `release-readiness.md`; the
repo-wide public-safety scan + `PHASE14` are 0 findings.

- [ ] T019 [P] [US5] Write `tests/contract/test_changelog.py` (MUST FAIL first): assert `CHANGELOG.md` has the `# Changelog` heading and a `## [0.1.0]` release with an `### Added` section that references the released units/layers (001–013), and contains no private reference; assert `docs/release-readiness.md` enumerates the release gates (FR-041/FR-042; SC-005).
- [ ] T020 [P] [US5] Create `CHANGELOG.md` (Keep a Changelog): a `0.1.0` release whose `### Added` summarizes the shipped layers (units 001–013) at a high level. Public-safe (research D8).
- [ ] T021 [P] [US5] Create `docs/release-readiness.md`: a checklist enumerating the release gates — distribution builds; quality gates green; public-safety audit clean; **`LICENSE` present** (the deferred maintainer gate, with the steps to wire it); changelog current.
- [ ] T022 [US5] Update `docs/README.md` to link `release-readiness.md` (keep the docs index consistent now that it exists).
- [ ] T023 [P] [US5] Extend `tests/contract/test_public_safety.py` with `PHASE14_TARGETS` (`README.md`, `CHANGELOG.md`, `docs/api-reference.md`, `docs/getting-started.md`, `docs/README.md`, `docs/release-readiness.md`, `examples/README.md`, `specs/014-loopplane-release-packaging-docs`) and a `test_phase14_release_files_are_public_safe` scan.
- [ ] T024 [US5] Run `pytest tests/contract/test_changelog.py tests/contract/test_docs_examples_index.py tests/contract/test_public_safety.py --basetemp=".pytmp"` → green.

**Checkpoint**: All user stories independently functional; release artifacts complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T025 [P] Run `ruff format` + `ruff check` (src + tests) + `mypy` (strict, src) → clean.
- [ ] T026 Run the full suite `pytest --basetemp=".pytmp"` → green (every prior layer + the new 014 contract tests, confirming no runtime behavior changed); run the `uv build` smoke (sdist + wheel; `loopplane/py.typed` present) or record the local-frontend caveat (verified in CI).
- [ ] T027 Confirm the repo-wide public-safety scan is green; update `docs/loopplane-agent-board.md` — set **014 → Verified** with a §3 evidence paragraph, and mark the roadmap (000–014) **complete**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies — shared helper + gitignore.
- **US1 (Phase 2)**: depends on Setup. MVP (packaging + version + typing).
- **US2 (Phase 3)**: depends on Setup (the discovery helper); independent of US1 at the file level.
- **US3 (Phase 4)**: depends on US2 (the docs index must list `api-reference.md`); creates the README,
  getting-started, and indexes.
- **US4 (Phase 5)**: independent (CI file + its test); may run any time after Setup.
- **US5 (Phase 6)**: depends on US3 (updates the docs index; the public-safety scan covers all new docs).
- **Polish (Phase 7)**: depends on all stories.

### Within each phase

- The contract test is written first and MUST FAIL before the artifact exists.
- Each phase ends on its pytest gate; commit per stable phase; push after each safe commit.

## Parallel Opportunities

- T001 (helper) is independent setup.
- Each story's contract test (`[P]`) is a distinct file; the docs files in US3 (T011–T014) are distinct
  files (`[P]`) authored together, then gated by T015.
- US2 (API reference) and US4 (CI) are independent of US1/US3 at the file level and can be authored in
  parallel once Setup is done.
- Polish T025 is `[P]`; T026/T027 are the final serial gates.

## Implementation Strategy

### MVP First (US1)

1. Phase 1 Setup → Phase 2 US1 (packaging + version + `py.typed`).
2. **STOP and VALIDATE**: `test_packaging.py` green and `uv build` produces a typed, single-version
   distribution offline.

### Incremental Delivery

Setup → US1 (MVP) → US2 (API reference) → US3 (navigation) → US4 (CI gates) → US5 (audit + changelog) →
Polish. Each phase is an independently testable, revertible increment; no layer public API and no runtime
behavior changes; no new runtime dependency.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- The API reference, the docs index, and the examples index are **checked against the code / file tree**
  — a drift fails the build (SC-002/005). The version has a single source; the build ships `py.typed`.
- **License is deferred** to the maintainer (a release-readiness gate); the build does not bind a
  `LICENSE`, so it succeeds now.
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: editing any layer `__all__` or runtime module; adding a runtime dependency; committing a
  `dist/` artifact, a secret, a private path, an internal name, or an IP.
