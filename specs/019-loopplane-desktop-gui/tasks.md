---
description: "Task list for unit 019 — LoopPlane Desktop GUI"
---

# Tasks: LoopPlane Desktop GUI

**Input**: Design documents from `specs/019-loopplane-desktop-gui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). The Python sidecar is tested in the `pytest`
gate; the TS transport + renderer in Vitest; the Electron shell is typechecked and
smoke-tested manually. Write each test FIRST and confirm it FAILS first.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Scaffold `apps/desktop/`: `package.json` (electron, react, react-dom,
  typescript, vite, vitest, jsdom, @testing-library/react; install with
  `ELECTRON_SKIP_BINARY_DOWNLOAD=1`), `tsconfig.json` (+ a `@web` path alias to
  `../web/src`), `vite.config.ts` (renderer + the `@web` alias), `index.html`,
  `src/test-setup.ts`; run `npm install`.

---

## Phase 2: Foundational — the bridge + the transport (BLOCKS the renderer)

- [ ] T002 [P] Python test `tests/integration/test_desktop_sidecar.py`: load
  `apps/desktop/sidecar/bridge.py` by file path; with a scripted host,
  `collect_events(host, prompt)` returns the serialized normalized-event lines and an
  outcome line, and the bridge opens no network port (FR-001/FR-002, SC-001). (FAIL first)
- [ ] T003 Implement `apps/desktop/sidecar/bridge.py` — `collect_events(host, prompt)`
  (drive `host.run` with a `serialize_event` sink) + `serve(host, in, out)` (the stdio
  NDJSON loop incl. approval/question request lines). Reuses only `loopplane.host` +
  `loopplane.events.serialize_event`.
- [ ] T004 [P] Vitest `apps/desktop/src/__tests__/sidecar.test.ts`: `SidecarTransport.run`
  over a stubbed `window.api` yields the parsed `RawEvent`s until the outcome line, and
  `answerApproval`/`answerQuestion` send their request lines (FR-002/FR-004). (FAIL first)
- [ ] T005 Implement `apps/desktop/src/sidecar.ts` — `SidecarTransport` over the
  `window.api` bridge (mirrors 018's client; reuses 018's `RawEvent` via `@web`).

**Checkpoint**: the Python bridge passes the pytest gate; the transport passes Vitest.

---

## Phase 3: User Story 3 — reuse the unit-018 UI (P2) 🎯 reuse-not-copy

- [ ] T006 [US3] Vitest (jsdom) `apps/desktop/src/__tests__/App.test.tsx`: the desktop
  App renders a streamed run using 018's `reduce` + `Conversation`/`Timeline` over a
  stubbed `SidecarTransport` (FR-003, SC-002). (FAIL first)
- [ ] T007 [US3] Implement `apps/desktop/src/App.tsx` (+ `src/main.tsx`) reusing 018's
  `initialState`/`reduce`/`userPrompt` and components via `@web`, driven by
  `SidecarTransport`.

---

## Phase 4: User Stories 1/2/4 — launch, bridge, interactive (P1/P2)

- [ ] T008 Implement `apps/desktop/electron/main.ts` + `electron/preload.ts`: spawn the
  Python sidecar, create the window, bridge sidecar stdout lines ↔ renderer IPC
  (`window.api`), and stop the sidecar on window close (no orphan) (FR-001/FR-008).
  Typechecked; GUI verified by a manual smoke (Electron binary skipped in CI).

---

## Phase 5: Gate, docs, and final review

- [ ] T009 [P] Add `docs/desktop-gui.md` and link it in `docs/README.md` (the unit-014
  docs-index contract checks every `docs/*.md` is linked).
- [ ] T010 Add `.github/workflows/desktop.yml` — the isolated desktop gate (`tsc
  --noEmit`, `vitest run`; `ELECTRON_SKIP_BINARY_DOWNLOAD=1`), separate from the Python
  and web gates.
- [ ] T011 Run the gates: `pytest` (incl. `test_desktop_sidecar.py`) green and the full
  Python suite unchanged; `apps/desktop` `npm run typecheck` + `npm test` green; the
  unit-018 web gate unchanged; confirm the wheel still excludes `apps/`.
- [ ] T012 Final review: set unit 019 to **Verified** in
  `docs/loopplane-agent-board.md` (§3 row + §4) and mark the **015–019 roadmap
  extension complete**; commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (bridge + transport) blocks the renderer. Phase 3 reuses 018 over
  the transport; Phase 4 wires the Electron shell. Phase 5 wires the gate + docs and
  closes the roadmap. T009 keeps the docs-index contract green.

### Parallel opportunities

- T002 (Python bridge test) and T004 (TS transport test) run in parallel.

## Notes

- The desktop **composes** the host + unit 018 and changes nothing in 011/012/018 or
  the runtime (FR-009). The Python sidecar is loaded by path in tests, so it adds no
  `loopplane` package and is excluded from the wheel; the api-reference/packaging
  contracts are unaffected.
- The renderer runs **no tool** (V) and is a consumer of the normalized stream (VI);
  no secret is embedded (VII). Packaging a signed installer is out of scope (reserved).
