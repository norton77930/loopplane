---
description: "Task list for unit 018 — LoopPlane Web Frontend"
---

# Tasks: LoopPlane Web Frontend

**Input**: Design documents from `specs/018-loopplane-web-frontend/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Vitest is the gate. Write each test FIRST and
confirm it FAILS before the matching implementation. The Python `pytest` suite is
untouched and stays green.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Scaffold `apps/web/`: `package.json` (react, react-dom, vite,
  @vitejs/plugin-react, typescript, vitest, jsdom, @testing-library/react),
  `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`; run `npm install`.

---

## Phase 2: Foundational — the pure core (BLOCKS the components)

- [ ] T002 [P] Vitest `src/__tests__/events.test.ts`: the SSE parser turns canned
  `data:` frames into typed events and passes unknown `type`s through (R2). (FAIL first)
- [ ] T003 [P] Vitest `src/__tests__/chat.test.ts`: `reduce` folds events into the
  conversation (assistant text per turn), the timeline (tool name+outcome,
  termination), and pending approval/question + status (R3). (FAIL first)
- [ ] T004 [P] Vitest `src/__tests__/client.test.ts`: `ApiClient` (stubbed `fetch`)
  hits the right `/v1` endpoints, iterates the SSE stream, carries the auth header, and
  raises a typed error on an HTTP error / dropped stream (R1, FR-006/FR-008). (FAIL first)
- [ ] T005 Implement `src/api/types.ts` — the `RuntimeEvent` union + `SessionSummary`.
- [ ] T006 Implement `src/api/events.ts` — SSE frame → event parsing.
- [ ] T007 Implement `src/state/chat.ts` — the pure `reduce(state, event)`.
- [ ] T008 Implement `src/api/client.ts` — the `/v1` REST + SSE client (fetch-injectable).

**Checkpoint**: the pure core passes Vitest in the node env.

---

## Phase 3: User Story 1 — chat in the browser (P1) 🎯 MVP

- [ ] T009 [US1] Vitest (jsdom) `src/__tests__/Conversation.test.tsx`: a streamed run's
  assistant output renders incrementally; the input clears for the next turn (FR-002). (FAIL first)
- [ ] T010 [US1] Implement `src/components/Conversation.tsx`.

---

## Phase 4: User Story 2 — the run timeline (P1)

- [ ] T011 [US2] Vitest `src/__tests__/Timeline.test.tsx`: a run that uses a tool shows
  the tool name + outcome (metadata only) and the terminal outcome, in order (FR-003). (FAIL first)
- [ ] T012 [US2] Implement `src/components/Timeline.tsx`.

---

## Phase 5: User Story 3 — approvals and questions (P2)

- [ ] T013 [US3] Vitest `src/__tests__/Prompts.test.tsx`: a pending approval/question
  renders and submitting calls the client's answer endpoint (FR-004). (FAIL first)
- [ ] T014 [US3] Implement `src/components/Prompts.tsx`.

---

## Phase 6: User Story 4 — browse sessions (P2)

- [ ] T015 [US4] Vitest `src/__tests__/SessionList.test.tsx`: the session list renders
  public-safe identity + recency and opening one shows its conversation (FR-005). (FAIL first)
- [ ] T016 [US4] Implement `src/components/SessionList.tsx`.

---

## Phase 7: User Story 5 — a safe, resilient UI (P3)

- [ ] T017 [US5] Vitest `src/__tests__/App.test.tsx`: the app wires client → reducer →
  components; an API error / dropped stream renders a clear state and does not crash
  (FR-008); rendered content is metadata-safe (FR-007). (FAIL first)
- [ ] T018 [US5] Implement `src/App.tsx` + `src/main.tsx` (the shell).

---

## Phase 8: Gate, packaging isolation, and polish

- [ ] T019 [P] Add `docs/web-frontend.md` and link it in `docs/README.md` (the unit-014
  docs-index contract checks every `docs/*.md` is linked). No Python package / example
  is added, so the api-reference and examples index are unchanged.
- [ ] T020 Add `.github/workflows/web.yml` — the isolated JS CI gate (`tsc --noEmit`,
  `vitest run`, `vite build`); it does not touch the Python gate.
- [ ] T021 Run the JS gate in `apps/web` (`npm run typecheck`, `npm test`, `npm run
  build`) to green; confirm the Python `pytest` suite is unchanged and still green and
  that the wheel still excludes `apps/`.
- [ ] T022 Final review: set unit 018 to **Verified** in
  `docs/loopplane-agent-board.md` (§3 row + §4) and commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (types → events/reducer/client) blocks the components. US1–US5
  (Phases 3–7) build the components/shell over the core and are independently testable.
  Phase 8 wires the gate + docs; T019 keeps the docs-index contract green.

### Parallel opportunities

- T002/T003/T004 (pure-core tests) run in parallel.
- The component test+impl pairs (US1–US4) are independent once the core lands.

## Notes

- The UI consumes only the unit-011 `/v1` API; it runs no tool, re-emits no bus, and
  changes nothing server-side (FR-001/FR-010). The toolchain is isolated under
  `apps/`; `pyproject.toml`, the wheel (`src/loopplane` only), and the Python CI gates
  are untouched.
- No secret is embedded in the source or the built bundle; the UI renders only
  metadata-safe content (FR-006/FR-007, SC-005).
