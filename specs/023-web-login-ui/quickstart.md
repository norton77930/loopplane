# Quickstart: Web Frontend Login UI (unit 023)

Validates the login gate over the unit-022 secured backend. Frontend only; no new
toolchain.

## Prerequisites

- `apps/web`: `npm install` (no new dependency).
- A running web/API host with a principal authenticator, e.g.
  `create_app(host, authenticator=token_authenticator({"tok-alice": "alice"}))`.

## Flow

1. **Start the app** (`npm run dev` in `apps/web`). With no token, only the **login
   screen** shows.
2. **Log in**: enter the access token (e.g. `tok-alice`) and submit. The chat / session UI
   appears; API calls now carry `Authorization: Bearer tok-alice` and are authorized by the
   backend.
3. **Reload** the tab → still logged in (the token is in `sessionStorage`).
4. **Log out** → back to the login screen; the stored token is cleared.
5. **Invalid token** → submitting a token the backend rejects (a `401`) returns you to the
   login screen with no token shown.

## Gate

```powershell
# in apps/web
npm run typecheck    # tsc --noEmit (strict)
npm test             # vitest run — incl. login / logout / 401-to-login integration tests
npm run build        # tsc --noEmit && vite build
```

Also confirm the Python suite is unchanged (the backend is untouched):

```powershell
uv run pytest
```

**Expected**: the web gate is green (the new integration tests pass; the existing 018 `App`
/component tests are unchanged); `vite build` produces static assets; the Python suite is
unchanged.
