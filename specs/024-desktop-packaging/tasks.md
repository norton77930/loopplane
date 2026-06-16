---
description: "Task list for unit 024 — Desktop Packaging"
---

# Tasks: Desktop Packaging

**Input**: Design documents from `specs/024-desktop-packaging/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Vitest (node env). Write the resolver + config↔spec
consistency tests FIRST and confirm they FAIL before implementing. The actual freeze /
installer build is a reserved manual / CI step, not part of the gate.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no runtime (Python) dependency change**: `loopplane`'s `pyproject`
  is untouched; `electron-builder` is a **desktop devDependency** used only by the reserved
  build (the default gate `tsc --noEmit` + `vitest run` neither imports nor needs it
  installed).

---

## Phase 2: Foundational (tests first)

- [ ] T002 `apps/desktop/src/__tests__/sidecar-spawn.test.ts` (FAIL first): unit-test
  `resolveSidecar` — (US1) packaged → `command` is `<resourcesPath>/sidecar/loopplane-sidecar`
  (+ `.exe` when `platform==="win32"`), `args==[]`; missing frozen (injected `exists`→false)
  → **throws**; (US2) not packaged → `command==="python"`, `args==[<devDir>/bridge.py]`; and
  a **config↔spec consistency** test that reads `apps/desktop/electron-builder.yml` and
  `apps/desktop/sidecar/loopplane-sidecar.spec` and asserts both name `loopplane-sidecar`.

**Checkpoint**: tests fail only on the missing resolver / spec / config.

---

## Phase 3: User Story 1 — the packaged app runs without a system Python (P1) 🎯 MVP

**Goal**: a packaged app spawns the bundled frozen sidecar; the freeze + package agree.

**Independent Test**: the resolver targets the frozen exe when packaged, and the config
bundles exactly that exe (T002).

- [ ] T003 [P] [US1] `apps/desktop/electron/sidecar-spawn.ts`: export `frozenSidecarName(platform)`
  (`loopplane-sidecar` + `.exe` on win32) and `resolveSidecar({ packaged, platform,
  resourcesPath, devDir, exists? })` — packaged → `join(resourcesPath,"sidecar",name)` (throw
  a clear error if `!exists`); else → `{ command:"python", args:[join(devDir,"bridge.py")] }`.
  **No `electron` import** (so it is unit-testable).
- [ ] T004 [US1] `apps/desktop/electron/main.ts`: replace the hardcoded
  `spawn("python", [bridge.py])` with `resolveSidecar({ packaged: app.isPackaged, platform:
  process.platform, resourcesPath: process.resourcesPath, devDir: ../sidecar })`; wrap it so a
  missing-frozen error surfaces (an error box) and quits rather than hanging.
- [ ] T005 [US1] `apps/desktop/sidecar/loopplane-sidecar.spec`: a PyInstaller spec —
  `Analysis(["bridge.py"], hiddenimports=collect_submodules("loopplane"))` →
  `EXE(name="loopplane-sidecar", console=True)` (a `.spec`, so ruff/mypy/pytest ignore it).
- [ ] T006 [US1] `apps/desktop/electron-builder.yml`: `appId`/`productName`,
  `directories.output: release`, `files` (compiled electron + renderer `dist`), and
  `extraResources: [{ from: sidecar/dist, to: sidecar, filter: [loopplane-sidecar*] }]`, with
  `win`/`mac`/`linux` targets.

**Checkpoint**: T002's resolver + consistency assertions pass.

---

## Phase 4: User Story 2 — development still works unchanged (P2)

**Goal**: dev mode spawns `python bridge.py`, exactly as unit 019.

**Independent Test**: the resolver in dev mode → `python` + bridge; the 019 tests pass.

- [ ] T007 [US2] Confirm the dev-mode resolver path (`python` + `bridge.py`) passes (T002),
  and the existing unit-019 desktop tests (`src/__tests__/sidecar.test.ts`, `App.test.tsx`)
  pass **unchanged**.

---

## Phase 5: User Story 3 — a maintainer can build from a documented procedure (P3)

**Goal**: the build scripts/config are present and consistent.

**Independent Test**: the config↔spec consistency test passes; the scripts exist.

- [ ] T008 [US3] `apps/desktop/package.json`: add `electron-builder` to `devDependencies`
  (pinned), and `scripts`: `build:sidecar` (PyInstaller over the `.spec`) and `dist`
  (electron-builder). Confirm the consistency test (T002) passes.

---

## Phase 6: Polish — gitignore, docs, changelog, board, gates

- [ ] T009 [P] `.gitignore`: ignore `apps/desktop/sidecar/build/`,
  `apps/desktop/sidecar/dist/`, and `apps/desktop/release/` (build artifacts; never committed).
- [ ] T010 [P] `docs/desktop-gui.md`: add a **Packaging** section — freeze the sidecar
  (PyInstaller), build + package (electron-builder), what ships, and the reserved signing step.
- [ ] T011 [P] `CHANGELOG.md`: add a `024` entry under Added.
- [ ] T012 [P] `docs/loopplane-agent-board.md`: add the **024** roadmap row + a status
  evidence note; refresh §4 "Active Feature" to **gap-closure COMPLETE** (Phase A–D all done).
- [ ] T013 Run the gates: in `apps/desktop` — `npm run typecheck` + `npm test` (green);
  from the root `uv run pytest` (unchanged); public-safety scan clean; confirm no build
  artifact (`sidecar/dist`, `release/`, `dist/`) is staged.
- [ ] T014 Final review: confirm desktop-only (runtime/hosts/web/CLI untouched), the 019
  app/tests unchanged, and the reserved build is documented; record unit 024 on the board;
  commit (`024 implement`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002)** precede the stories (tests fail first).
- **US1 (T003–T006)** is the MVP: the resolver makes the resolver tests pass; the `.spec` +
  `electron-builder.yml` make the consistency test pass; `main.ts` wires the resolver.
- **US2 (T007)** is satisfied by the resolver (T003) — the dev branch.
- **US3 (T008)** adds the scripts/devDep and confirms consistency.
- **Polish (T009–T014)** depends on the implemented pipeline.

### Parallel opportunities

- T001 is independent `[P]`.
- T003 (resolver) is `[P]` (pure module, independent of the config files until tested together).
- T009/T010/T011/T012 (gitignore / docs / changelog / board) are independent `[P]` files.

## Notes

- The resolver imports **no `electron`**, so it is unit-tested directly; `main.ts` supplies
  `app.isPackaged` / `process.platform` / `process.resourcesPath`.
- The frozen name `loopplane-sidecar` is shared by the resolver, the `.spec` (`EXE(name=…)`),
  and the `electron-builder` `extraResources` filter — the consistency test guards it.
- The default gate proves the resolver + consistency **offline**; the PyInstaller freeze, the
  installer artifact, and signing/notarization are a **reserved manual / CI step** (unit-019
  precedent). Built artifacts are gitignored.
- Desktop-only — runtime / hosts / web UI / CLI and the 019 bridge/transport/preload are
  untouched. Rollback = drop the resolver/spec/config and restore the dev-only spawn.
