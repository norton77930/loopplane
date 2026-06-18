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
- `src/state/chat.ts` — a **pure reducer** folding events into one **ordered entry list**
  (user / assistant / tool / terminated, in stream order) + pending approval/question +
  status (the unit-025 view model; was a separate conversation + timeline).
- `src/components/*` — React views (`AppShell`, `Sidebar`, `ChatHeader`, `MessageList`,
  `Markdown`, `ToolCard`, `ApprovalDialog`, `QuestionDialog`, `Composer`, `ErrorBanner`,
  `ThemeToggle`, `Login`); `src/App.tsx` wires the client + reducer to them, and
  `src/styles.css` + `src/theme/theme.ts` provide the themed look.

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

## UI overhaul (unit 025)

Unit 025 is a **frontend-only** visual + UX overhaul, mapped onto the **existing** events
and endpoints — no backend change. The app is a two-pane shell: a **sessions sidebar**
(list + recency + new chat) and a **chat column** with a sticky header (run/connection
**status** + a **Stop** control that cancels via the existing cancel endpoint + a
**light/dark theme** toggle) and a sticky **composer** (a growing textarea that disables
while a run is in flight).

Assistant messages render as **markdown** (`react-markdown` + `remark-gfm`, with raw HTML
disabled so model output cannot inject markup); each tool call renders **inline** as a
**collapsible card** that moves from running to success/failure; approvals and questions
appear as **styled in-flow dialogs** (the approval dialog adds an "always allow this
session" choice over the existing decision scope); a run end shows a **terminal marker**;
a connection failure shows a non-blocking **error banner** over the preserved
conversation; and the message list **auto-scrolls** when pinned to the bottom, with a
**jump-to-latest** affordance when the user has scrolled up.

The **theme** (light/dark) is stored in `localStorage` and defaults to the OS preference;
it is applied via a `data-theme` attribute and CSS custom properties. The api layer
(`api/*`) and the unit-023 auth gate (`AppRoot`) are **reused unchanged**; reverting the
`apps/web` presentation diff restores the unstyled-but-functional unit-018/023 app.
Reasoning display, multi-option questions, token usage, and code syntax highlighting are
**out of scope** (units 026 / 029).
