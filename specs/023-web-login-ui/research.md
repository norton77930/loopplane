# Research: Web Frontend Login UI & Auth Flow (unit 023)

Phase 0 decisions. Frontend only; additive; no new toolchain.

## R1 — A new `AppRoot` gate, not auth inside `App`

- **Decision**: Add a new top-level `AppRoot` that owns the auth state and renders either
  `Login` or the existing `App`. `App` keeps its injected-`client` prop and gains only an
  optional `onUnauthorized` callback.
- **Rationale**: The unit-018 `App` tests render `<App client={stub}/>`; keeping `App`'s
  shape means those tests are unaffected (FR-009). Auth concerns live in `AppRoot`.
- **Alternatives**: fold auth into `App` — rejected: it would change `App`'s contract and
  its 018 tests, and mix the run UI with the auth gate.

## R2 — `sessionStorage` token persistence

- **Decision**: store the token under a fixed key in `sessionStorage`; initialize
  `AppRoot`'s token state from it; write on login, remove on logout.
- **Rationale**: the confirmed decision — survives a reload within the tab, cleared when
  the tab closes; better UX than re-entry each load, less persistent than `localStorage`.
- **Note**: jsdom provides `sessionStorage`, so tests exercise it directly (cleared between
  tests).

## R3 — Token → `Bearer` via the existing `authHeader` seam

- **Decision**: `AppRoot` builds the client as `new ApiClient({ authHeader: `Bearer ${token}` })`
  (through an injectable `makeClient(token)` factory). The masked `Login` input captures the
  raw token.
- **Rationale**: `ApiClient` already sends `authHeader` as the `authorization` header
  (unit 018); the 022 `token_authenticator` expects `Bearer <token>`. No client change.

## R4 — 401 → logout via the existing `ApiError`

- **Decision**: `App` gains `onUnauthorized?: () => void`; on a run-path failure it inspects
  the error and, when `error instanceof ApiError && error.status === 401`, calls
  `onUnauthorized()` (which `AppRoot` wires to logout); any other error keeps the existing
  `errored` state.
- **Rationale**: `ApiClient` already throws `ApiError` carrying the HTTP `status`. Routing
  only 401 to logout preserves the 018 behavior for generic failures (its test asserts the
  error state on a generic throw).

## R5 — Masked input + no leak

- **Decision**: the token input is a masked (password-type) field; the token is never
  logged, never put in the URL, and never written to committed code — only the user enters
  it; the logout and 401 paths clear it from state and `sessionStorage`.
- **Rationale**: Constitution VII — the credential stays confidential.

## R6 — Injectable `makeClient` test seam

- **Decision**: `AppRoot` accepts `makeClient(token) => ApiClient` (default builds the real
  client). Tests inject a factory returning a stub client to drive login / logout / 401
  flows deterministically with no network.
- **Rationale**: mirrors how `App` already accepts an injected `client`; keeps the
  integration tests offline and deterministic.

## R7 — Vitest + jsdom integration (no Playwright)

- **Decision**: integration tests via the existing Vitest + jsdom + Testing Library; a
  real-browser run is a manual smoke (like unit 019's Electron launch).
- **Rationale**: the confirmed decision — consistent with unit 018; adds no toolchain,
  browser binaries, or CI gate.

## R8 — Frontend-only, reversible

- **Decision**: only `apps/web/src` changes; the Python package and unit 022 are untouched.
  Rollback = mount `App` directly in `main.tsx` and delete `Login`/`AppRoot`.
