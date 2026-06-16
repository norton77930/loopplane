# Contract: Login & auth gate

The frontend auth gate over the unit-022 secured backend. Token capture, gating,
persistence, logout, and the 401 fallback — all in `AppRoot` + `Login`, reusing the
unit-018 `App` and `ApiClient` unchanged.

## Obligations

1. **Gate (FR-001/FR-004)**: with no token, `AppRoot` renders **only** `Login`; with a
   token, it renders the authenticated `App` wired to a token-carrying client. The
   authenticated UI is never shown without a token.
2. **Capture (FR-002/FR-003)**: `Login` accepts a **non-empty** token (empty is rejected)
   via a masked input; the token becomes the `Bearer <token>` `authHeader` for every API
   call.
3. **Persist (FR-005)**: the token is stored in `sessionStorage` — a reload within the tab
   stays authenticated; closing the tab clears it.
4. **Logout (FR-006)**: a logout control clears the token from state **and**
   `sessionStorage` and returns to `Login`.
5. **401 → login (FR-007)**: an API authorization failure (`ApiError.status === 401`) on a
   run path clears the token and returns to `Login`; any other error keeps the existing
   `errored` state.
6. **No leak (FR-008)**: the token is masked in the input and never logged, URL-encoded, or
   committed; the `Login` fallback and error text contain no token.
7. **018 unaffected (FR-009)**: `App` keeps its injected `client` prop; its only change is
   the optional `onUnauthorized` callback. The existing 018 `App`/component tests pass
   unchanged.

## Test matrix (Vitest + jsdom, stubbed client)

| Case | Expected |
|---|---|
| no token | only `Login` renders |
| submit empty token | not accepted; stays on `Login` |
| submit a token | authenticated `App` renders; calls carry the token |
| reload with a stored token | authenticated `App` renders (no re-login) |
| logout | `Login` renders; `sessionStorage` token cleared |
| stubbed 401 on a run | falls back to `Login`; token cleared; not leaked |

## Non-obligations

- No username/password, token issuance/refresh/rotation, IdP, or roles.
- No backend change (unit 022 owns identity/scoping).
- No persistence beyond the tab session (no `localStorage`).
- No real-browser automated E2E (a manual smoke instead).

## Rollback (Constitution X)

Mount `App` directly in `main.tsx` and delete `Login`/`AppRoot` and the `onUnauthorized`
prop. The backend and the rest of the frontend are untouched.
