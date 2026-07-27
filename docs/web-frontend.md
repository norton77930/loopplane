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
**out of scope** for unit 025 (reasoning / options / usage land in unit 026; syntax
highlighting in unit 029).

## Signals (unit 026)

Unit 026 is a **frontend-only** extension that renders three signals the backend **already
emits** over the existing stream (grounded in `src/loopplane/events/envelope.py`) but the
unit-018/025 UI ignored — **no backend change**:

- **Reasoning / thinking** — `assistant-reasoning-increment` events fold into a `reasoning`
  conversation entry (merged like the answer, so it interleaves **before** the turn's answer);
  `ReasoningBlock` renders it as a distinct, de-emphasized, **collapsible** block. A turn with
  no reasoning shows nothing.
- **Question options** — the `question-asked` payload's `questions[].{ text, options }` is read
  correctly (unit 018 mis-named the field `prompt`); `QuestionDialog` renders the options as a
  select-one-or-many choice group submitting the selection as `answers`, and falls back to the
  free-text field when there are no options.
- **Token usage** — `turn-completed` carries `usage` (input / output / cached / reasoning); the
  reducer keeps `{ last, total }` and `UsageIndicator` (in the header) shows the per-turn usage
  and a session total, hidden when all-zero.

Each signal degrades gracefully when absent (the central correctness requirement); the reducer
stays a pure consumer of the existing events (Constitution VI). Reverting the `apps/web` diff
restores the unit-025 app.

## Inspection panels (unit 027)

Unit 027 adds **read-only** inspection of the agent's capabilities/context — a tabbed, right-side
`InspectionPanel` (toggled from the header) over four additive, metadata-only endpoints:
**Skills** (loaded skills + load problems), **Tools** (registered tools), **MCP** (connected
servers + their tools), and **Memory** (entries with a source + snippet, with a search box). The
panel is read-only — no execute/edit affordance — and uses the existing `ApiClient`
(`inspectSkills` / `inspectTools` / `inspectMcp` / `inspectMemory`). The backend host query methods
compose existing layers; no tool is executed and no state is mutated.

## Model selection & attachments (unit 028)

Unit 028 adds, additively in the composer: a **model selector** (`ModelSelector`, lists
`GET /v1/models` and binds the session's model — one model per run, routed in the web/API layer)
and **file attachments** (`Attachments`, upload via `POST /v1/uploads` with a per-file status).
Unit 077 replaces the former prompt-concatenation handoff with the existing structured `uploads`
request field. Images still enter through the multimodal content seam; non-image references become
bounded opaque metadata only after owner validation and only when the host projects `read_upload` as
available. The browser never reads raw upload content, and actual tool invocation remains exclusively
Gateway-routed. Files remain transient input by id; no binary durability or cross-principal sharing is added.

## Agent Controls (unit 077)

Settings now includes a first-level **Agent Controls** category backed by the owner-scoped
`GET /v1/sessions/{session_id}/agent-controls` projection. It presents host-approved one-run
permission choices (never `bypassPermissions`), authoritative non-durable active/last posture,
existing plan-exit approval state, exact session/monthly spend, enum-only budget/tracking posture,
current/bindable workspace context metadata, and safe upload/artifact references. Missing,
unpriced, partially priced, and unavailable values remain distinct; `null` is never shown as `$0`.
Permission drafts, reference attachment, and localized follow-up suggestions only update editable
client state until an explicit send. Suggestions are derived from visible state with zero network,
model, tool, or automatic-send effects. Existing deny-wins, approval ordering, Tool Gateway,
Event Bus, checkpoint, persistence, and defaults remain authoritative.

## Parity extras (unit 029)

Unit 029 is the final frontend-only polish (no backend, no ADR): **i18n** (`src/i18n/` — a `t()`
lookup over en + zh-TW string maps, an `I18nProvider` persisting the choice in `localStorage`, a
`LanguageSwitcher` in the header, with an English fallback; only UI chrome is localized);
**code syntax highlighting** (`rehype-highlight` added to the unit-025 `Markdown`, with theme-bound
`hljs` token CSS and a plain fallback for unknown languages); a **command palette** in the composer
(`CommandPalette` — typing `/` lists frontend-doable commands like toggling the inspection panel,
and `@` autocompletes skill/tool mentions from the unit-027 inspection data; backend-semantic
commands are out of scope); and a **client-side cost estimate** (`pricing.ts` — the unit-026 usage
× a bundled price table for the unit-028 selected model, shown by `UsageIndicator` as a labeled
estimate, with token counts only when no price entry exists). Each degrades gracefully.
