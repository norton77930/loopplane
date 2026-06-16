---
description: "Task list for unit 023 — Web Frontend Login UI & Auth Flow"
---

# Tasks: Web Frontend Login UI & Auth Flow

**Input**: Design documents from `specs/023-web-login-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Vitest + jsdom integration tests. Write the
login / logout / 401-to-login tests FIRST and confirm they FAIL before implementing.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no new dependency**: `apps/web/package.json` is unchanged (React +
  Vite + Vitest + jsdom only; **no Playwright**). Ensure `apps/web` deps are installed for
  the gate (`npm install` if needed).

---

## Phase 2: Foundational (tests first)

- [ ] T002 Write the tests FIRST (FAIL): `apps/web/src/__tests__/Login.test.tsx` (submits a
  token; rejects an empty token) and `apps/web/src/__tests__/AppRoot.test.tsx` — render
  `AppRoot` with an injected `makeClient` stub and a clean `sessionStorage`: (US1)
  no-token → only `Login`; submit a token → the authenticated `App` renders and the stub
  client's calls carry the token; (US2) a token preset in `sessionStorage` → `App` renders
  without re-login; logout → `Login` + `sessionStorage` cleared; (US3) a stub that throws a
  401 (`ApiError`) on a run → falls back to `Login` and the token does not appear in the
  output.

**Checkpoint**: tests fail only on the missing `Login`/`AppRoot`/`App` changes.

---

## Phase 3: User Story 1 — log in with a token and use the app (P1) 🎯 MVP

**Goal**: a token-entry screen gates the existing app.

**Independent Test**: no token → `Login`; submit → authenticated `App` with token-carrying
calls (T002).

- [ ] T003 [P] [US1] `apps/web/src/components/Login.tsx`: a form with a **masked**
  (`type="password"`, `aria-label="access token"`) input and a submit button; on submit,
  trim and call `onSubmit(token)` **only if non-empty**.
- [ ] T004 [US1] `apps/web/src/AppRoot.tsx`: `token` state initialized from
  `sessionStorage`; `login(token)` (write `sessionStorage` + set state) and `logout()`
  (remove `sessionStorage` + clear state); render `Login` when `token === null`, else a
  logout control + `App` wired with `makeClient(token)` and `onUnauthorized={logout}`.
  Default `makeClient(token) = new ApiClient({ authHeader: ` + "`Bearer ${token}`" + ` })`;
  injectable for tests.
- [ ] T005 [US1] `apps/web/src/main.tsx`: mount `<AppRoot/>` (in `StrictMode`) instead of
  `<App/>`.

**Checkpoint**: T002's US1 assertions pass; a user can log in and reach the app.

---

## Phase 4: User Story 2 — stay logged in across a reload; log out (P2)

**Goal**: `sessionStorage` persistence + a logout control.

**Independent Test**: a preset token → `App` (no re-login); logout → `Login` + cleared.

- [ ] T006 [US2] Confirm the persistence + logout scenarios pass (implemented in T004): a
  token preset in `sessionStorage` renders `App`; logout clears `sessionStorage` and returns
  to `Login`. Add cases if any gap.

---

## Phase 5: User Story 3 — an authentication failure returns to login (P3)

**Goal**: a 401 clears the token and returns to `Login`, without leaking it.

**Independent Test**: a stubbed 401 on a run → `Login`; no token in the output (T002).

- [ ] T007 [US3] `apps/web/src/App.tsx`: add `onUnauthorized?: () => void`; import
  `ApiError`; route run-path failures (the `readEvents` / `send` catches) through a helper
  so `error instanceof ApiError && error.status === 401` calls `onUnauthorized?.()`,
  otherwise the existing `errored` state is kept (018 behavior unchanged). Confirm the
  401 → `Login` test passes and the token is not leaked.

---

## Phase 6: Polish — docs, changelog, board, gates

- [ ] T008 [P] `docs/web-frontend.md`: add a **Login / auth** section (token entry,
  `sessionStorage`, logout, 401 → login).
- [ ] T009 [P] `CHANGELOG.md`: add a `023` entry under Added.
- [ ] T010 [P] `docs/loopplane-agent-board.md`: add the **023** roadmap row + a status
  evidence note; refresh §4 "Active Feature" to reflect 023 shipped (Phase C complete) and
  Phase D as the remaining gap-closure unit.
- [ ] T011 Run the gates: in `apps/web` — `npm run typecheck` (`tsc --noEmit`), `npm test`
  (`vitest run`), `npm run build` (`vite build`) — all green; confirm the Python suite is
  unchanged (`uv run pytest`); public-safety scan clean (no token in committed files).
- [ ] T012 Final review: confirm frontend-only (no backend change), the existing 018
  `App`/component tests pass unchanged, and the token is never committed; record unit 023
  on the board; commit (`023 implement`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002)** precede the stories (tests fail first).
- **US1 (T003–T005)** is the MVP: `Login` + `AppRoot` + `main` mount.
- **US2 (T006)** is satisfied by `AppRoot` (T004) — persistence + logout are part of it.
- **US3 (T007)** depends on `AppRoot` wiring `onUnauthorized` (T004) and the `App` change.
- **Polish (T008–T012)** depends on the implemented gate.

### Parallel opportunities

- T001 is independent `[P]`.
- T003 (`Login`) is `[P]` (independent of `AppRoot`'s state wiring until composed).
- T008/T009/T010 (docs / changelog / board) are independent `[P]` files.

## Notes

- `App` keeps its injected `client` prop; its only change is the optional `onUnauthorized`
  callback, so the **existing 018 `App`/component tests pass unchanged**.
- The token is **masked** in the input and never logged, URL-encoded, or committed
  (Constitution VII); logout and the 401 path clear it from state and `sessionStorage`.
- Frontend only — no backend change (unit 022), no new toolchain (no Playwright); a
  real-browser run is a manual smoke.
- Rollback = mount `App` directly in `main.tsx` and delete `Login`/`AppRoot` + the
  `onUnauthorized` prop.
