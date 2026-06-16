# Data Model: Web Frontend Login UI & Auth Flow (unit 023)

Frontend state and component shapes. Illustrative TypeScript; the authority is the spec.

## Access token (frontend auth state)

- A `string | null` held in `AppRoot` state and mirrored in `sessionStorage` under a fixed
  key (e.g. `"loopplane.token"`).
- `null` → unauthenticated (show `Login`). A non-empty string → authenticated (show `App`
  with a token-carrying client).

## `Login` — `apps/web/src/components/Login.tsx`

```tsx
function Login(props: { onSubmit: (token: string) => void }): JSX.Element
```

- A form with a **masked** token input (`aria-label="access token"`) and a submit button.
- On submit, trims the value and calls `onSubmit(token)` **only if non-empty** (an empty
  token is not accepted).

## `AppRoot` — `apps/web/src/AppRoot.tsx`

```tsx
function AppRoot(props?: { makeClient?: (token: string) => ApiClient }): JSX.Element
```

- `token` state initialized from `sessionStorage`.
- `login(token)`: write `sessionStorage` + set state. `logout()`: remove `sessionStorage` +
  clear state.
- Renders `Login` when `token === null`; otherwise a logout control + `App` wired with
  `makeClient(token)` and `onUnauthorized={logout}`.
- `makeClient` default: `(token) => new ApiClient({ authHeader: `Bearer ${token}` })`;
  injectable for tests.

## `App` change — `apps/web/src/App.tsx`

```tsx
function App(props: { client?: ApiClient; onUnauthorized?: () => void }): JSX.Element
```

- Adds the optional `onUnauthorized` prop. A run-path failure routes through a small
  helper: `error instanceof ApiError && error.status === 401 → onUnauthorized?.()`,
  otherwise the existing `errored` state. The `client` prop and all other behavior are
  unchanged (018-compatible).

## `main.tsx` change

Mounts `<AppRoot/>` (in `StrictMode`) instead of `<App/>`.

## Reused unchanged (unit 018)

`ApiClient` (its `authHeader` option + `ApiError.status`), `App`'s chat/session UI,
`Conversation` / `Timeline` / `Prompts` / `SessionList`, and the `chat` state reducer.
