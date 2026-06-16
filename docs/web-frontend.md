# Web frontend

The web UI (unit 018) is a from-scratch single-page app under `apps/web/`, served as
static assets, that sits on top of the unit-011 web/API host. It lets a user chat with
the agent in the browser, watch the run stream live, answer approvals and questions,
and browse sessions — talking **only** to the public `/v1` API (REST + the SSE event
stream), never to the runtime directly. Its JavaScript toolchain is isolated from the
Python package and has its own build and test gate.

## Run it

```sh
cd apps/web
npm install
npm run dev        # Vite dev server, proxying /v1 to a running web API host
```

Point it at a running web/API host (e.g. `examples/webapi_quickstart.py`).

## The JS gate

```sh
cd apps/web
npm run typecheck  # tsc --noEmit (strict)
npm test           # vitest run
npm run build      # tsc + vite build -> static assets in apps/web/dist
```

These run in CI via `.github/workflows/web.yml`, separate from the Python gate.

## Shape

- `src/api/client.ts` — the `/v1` REST + SSE client (fetch-injectable; auth supplied at
  runtime, never baked into the bundle).
- `src/api/events.ts` — parse the SSE byte stream into normalized event objects.
- `src/state/chat.ts` — a **pure reducer** folding events into the conversation +
  timeline + pending approval/question + status.
- `src/components/*` — thin React views (`Conversation`, `Timeline`, `Prompts`,
  `SessionList`); `src/App.tsx` wires the client + reducer to them.

The deterministic core (events / reducer / client) is tested in Vitest's node env with
a stubbed `fetch` and canned event frames; the components have jsdom smoke tests. The
UI renders only metadata-safe content (assistant text; tool name + outcome; normalized
termination) and embeds no secret. It consumes the existing web API and changes nothing
server-side.

## Logging in (unit 023)

Against the unit-022 per-principal backend the app must send a bearer token. `AppRoot`
(`src/AppRoot.tsx`) gates the UI: with no token it shows the **login screen**
(`src/components/Login.tsx`, a masked token field); on submit it builds an authenticated
`ApiClient` (sending `Authorization: Bearer <token>`) and shows the chat UI. The token is
held in `sessionStorage` — it survives a reload within the tab and is cleared when the tab
closes; a **Log out** control clears it, and an API **401** (an invalid or expired token)
clears it and returns to the login screen. The token is masked, never logged, never placed
in the URL, and never committed — only the user enters it. `App` is unchanged apart from an
optional `onUnauthorized` callback, so the unit-018 components and tests are untouched.
