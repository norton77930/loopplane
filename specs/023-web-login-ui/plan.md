# Implementation Plan: Web Frontend Login UI & Auth Flow

**Branch**: `023-web-login-ui` (main-only) | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/023-web-login-ui/spec.md`

## Summary

Add a login experience over the existing unit-018 SPA so it can authenticate against the
unit-022 per-principal backend. A new **`Login`** screen captures an access token; a new
top-level **`AppRoot`** wrapper owns the token state, gates the UI (no token → `Login`;
token → the existing `App`), persists the token in **`sessionStorage`** (survives a reload
within the tab, cleared on tab close), and provides **logout**. The token is fed to the
existing `ApiClient` via its `authHeader` seam (`Bearer <token>`); `App` gains an
**`onUnauthorized`** callback so an API **401** (`ApiError.status === 401`) clears the
token and returns to `Login`. `main.tsx` mounts `AppRoot`. Frontend only — the backend
(022) and the existing 018 `App`/components/state/client are reused unchanged; `App` still
takes an injected `client`, so the 018 `App` tests are unaffected. Vitest + jsdom
integration tests cover login / logout / 401-to-login; no new toolchain.

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (the existing `apps/web` toolchain).

**Primary Dependencies**: none new. React + Vite + Vitest + jsdom + Testing Library, all
already in `apps/web/package.json`. No Playwright.

**Storage**: `sessionStorage` (browser, tab-scoped) holds the access token.

**Testing**: Vitest + jsdom (Testing Library). New integration tests render `AppRoot` with
an injected client factory and a stubbed network: login → authenticated app, logout, and a
401 → back-to-login. The existing 018 `App`/component tests stay green.

**Target Platform**: a browser single-page app (the unit-018 web frontend).

**Project Type**: web frontend — additive components under `apps/web/src/`. The Python
package is untouched.

**Performance Goals**: unchanged; the auth gate is a single state branch.

**Constraints**: frontend-only; no backend change; the existing `App` keeps its injected
`client` prop (018 tests unaffected); the token is never logged, URL-encoded, or committed
(Constitution VII); the web gate (`tsc --noEmit` + `vitest run` + `vite build`) stays
green and the Python suite is unchanged.

**Scale/Scope**: two new components (`Login`, `AppRoot`), a small additive `App` change
(`onUnauthorized` + 401 detection), `main.tsx` re-mount, two test modules, and a doc/board
/changelog touch.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–010). | PASS |
| II — Greenfield | `Login`/`AppRoot` are written fresh; no legacy UI copied (VII). | PASS |
| III — Harness before automation | UI auth gate; no loop automation. | PASS |
| IV — Boundary Clarity | The UI still reaches the runtime only through the public web API via `ApiClient`. | PASS |
| V — Tool Gateway Ownership | Untouched — the UI runs no tool. | PASS |
| VI — Event Bus Ownership | Untouched — the UI consumes the normalized SSE stream as before. | PASS |
| VII — Public-Safe | The token is user-entered, never logged / URL-encoded / committed; the login input is masked; the 401 fallback leaks nothing. | PASS (FR-007, FR-008) |
| VIII — No SDK Replacement | No framework swap; the runtime core is untouched. | PASS |
| IX — Reference, not clone | A conventional token-login gate, written for this app. | PASS |
| X — Testable Evolution | Login/logout/401 integration tests; rollback = mount `App` directly again and drop `Login`/`AppRoot`. | PASS |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/023-web-login-ui/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   └── login-auth-gate.md           # the auth gate: token capture, persistence, gating, logout, 401-to-login, no-leak
├── checklists/requirements.md
└── tasks.md                          # created by /speckit.tasks
```

### Source Code (repository root)

```text
apps/web/src/
├── components/
│   └── Login.tsx          # NEW — token-entry form (masked input; rejects empty); onSubmit(token)
├── AppRoot.tsx            # NEW — auth gate: token state from sessionStorage; Login | App; logout; injectable makeClient
├── App.tsx                # EDIT — add onUnauthorized?; a 401 (ApiError.status===401) on a run path calls it
├── main.tsx               # EDIT — mount <AppRoot/> instead of <App/>
└── __tests__/
    ├── Login.test.tsx     # NEW — submit a token / reject empty
    └── AppRoot.test.tsx   # NEW — login→app, logout→login, 401→login (stubbed client), token not leaked
```

Edited (docs / drift):

```text
docs/web-frontend.md                 # + a Login / auth section
CHANGELOG.md                         # + a 023 entry
docs/loopplane-agent-board.md        # + the 023 row + audit; refresh §4 Active Feature
```

**Structure Decision**: A new `AppRoot` wrapper owns the auth state and the
`sessionStorage` token, rendering either `Login` or the existing `App`. Keeping the auth
logic in `AppRoot` (not `App`) means the unit-018 `App` keeps its injected-`client` shape
and its tests pass unchanged; `App`'s only change is an optional `onUnauthorized` callback
invoked on a 401. `AppRoot` exposes an injectable `makeClient(token)` so tests drive it
with a stubbed client, mirroring how `App` already accepts an injected `client`.

## Phases

- **Phase 0 — Research** (`research.md`): the `AppRoot` gate vs. folding auth into `App`
  (keep `App` 018-compatible); `sessionStorage` token persistence (the confirmed decision)
  and a masked input; the `Bearer <token>` `authHeader` wiring; the 401 → logout path via
  the existing `ApiError`; the injectable `makeClient` test seam; and the Vitest+jsdom test
  approach (no Playwright).
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the token / auth
  state; `Login` and `AppRoot` props; the login-auth-gate contract; and a quickstart of
  login → use → logout.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — write the `AppRoot`/`Login` integration
  tests first (FAIL), then `Login`, then `AppRoot` + the `App` `onUnauthorized` change,
  then `main.tsx`, then docs/changelog/board; run the web gate + the Python suite.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
