# Phase 0 Research: Web Agent UI

All decisions below resolve the Technical Context to a buildable, frontend-only plan. There were
**no `[NEEDS CLARIFICATION]`** markers in the spec; the open items were library/approach choices
the spec deliberately left to planning.

## R1 — Markdown rendering library

- **Decision**: Render assistant output with **`react-markdown`** (^9) + **`remark-gfm`** (^4),
  with **raw HTML disabled** (no `rehype-raw`). GFM covers FR-001's tables (plus task lists,
  strikethrough, autolinks); headings/lists/code blocks/links are core CommonMark.
- **Rationale**: `react-markdown` parses to a React element tree and renders **components**, never
  `dangerouslySetInnerHTML`; without `rehype-raw`, any raw HTML in model output is rendered as
  inert text. That directly satisfies the FR-001 edge case ("rendered formatted and safely — no
  raw-HTML injection from model output") with no extra sanitizer. It is the de-facto standard for
  React markdown and fits the isolated `apps/web` toolchain.
- **Alternatives considered**:
  - *Hand-rolled markdown parser* — rejected: re-implements a parser (large, error-prone) and the
    XSS surface we are trying to avoid; violates "simplicity first" more than a vetted library does.
  - *`marked` / `markdown-it` + `DOMPurify` + `dangerouslySetInnerHTML`* — rejected: pulls HTML
    back into the DOM and adds a sanitizer dependency to undo the risk; `react-markdown`'s
    no-raw-HTML default avoids the class of bug entirely.
- **Scope note**: code blocks render as `<pre><code>` only; **syntax highlighting is deferred to
  unit 029** (it adds a highlighter dependency and is explicitly out of scope here).

## R2 — Theming (light / dark)

- **Decision**: **CSS custom properties** (design tokens) defined under a `:root` (light) and a
  `[data-theme="dark"]` selector. A `theme` module reads a stored preference from `localStorage`
  (`"light" | "dark"`), falls back to `window.matchMedia("(prefers-color-scheme: dark)")` when
  unset, and applies the resolved theme by setting `data-theme` on `document.documentElement`. The
  toggle writes the choice back to `localStorage`.
- **Rationale**: Custom properties theme the entire tree from one attribute flip — no per-component
  prop drilling, no framework. `localStorage` (not `sessionStorage`) makes the choice persist
  across reloads **and** tabs (FR-013), distinct from the tab-scoped auth token. All storage access
  is wrapped in `try/catch` so a blocked/unavailable store falls back to the system default without
  error (FR-013 / edge case).
- **Alternatives considered**: a CSS-in-JS theme provider (adds a dependency + runtime cost; the
  app has no other need for it); class-based theming (`.theme-dark`) — equivalent, but a single
  `data-theme` attribute reads cleaner and matches the "modern app" idiom.

## R3 — View-model shaping: ordered conversation entries

- **Decision**: Evolve the **existing pure reducer** (`state/chat.ts`) so it folds the same
  normalized events into a single **ordered `entries: ConversationEntry[]`** — a discriminated
  union of `user` / `assistant` / `tool` / `terminated` — instead of the current two parallel
  arrays (`turns` + `timeline`). `status`, `pendingApproval`, and `pendingQuestion` are unchanged.
- **Rationale**: FR-002/FR-003 require tool cards to appear **inline, in stream order**, between
  assistant messages. The current state keeps `turns` and `timeline` as **separate** arrays with
  no interleaving index, so the order **cannot** be reconstructed by a post-hoc selector — the
  ordering information must be captured **as events arrive**. Keeping it in the reducer preserves
  the proven, well-tested event-handling logic (append-merge for assistant increments;
  `callId`-match update for tool completion; forward-compatible default) and stays a pure function
  over the **same** events — Constitution VI explicitly grants a consumer this adaptation, and no
  event schema changes.
- **Interleave rule**: an `assistant-output-increment` **merges** into the last entry only if that
  entry is an `assistant` entry; otherwise it **appends** a new one. So assistant text that arrives
  after a `tool-call-started` (whose card was appended) naturally begins a **new** assistant entry
  below the card — producing message → tool card → message ordering for free.
- **Alternatives considered**: a separate selector deriving entries from `turns`+`timeline`
  (impossible without interleave order, as above); a second reducer alongside the first (duplicate
  event handling, two sources of truth) — rejected.

## R4 — Approval "always allow for this session"

- **Decision**: Map the optional **"always allow for this session"** choice (FR-004) onto the
  **existing** `ApprovalDecision.scope` field (`"once" | "session"`) already on the api client.
  `ApprovalDialog` offers Allow (`scope: "once"`), Deny (`allow: false`), and
  Always-allow-this-session (`allow: true, scope: "session"`); `App.approve` is widened to forward
  an optional `scope`.
- **Rationale**: No backend or contract change — the decision shape already supports session
  scope; only the dialog + the `approve` call site need the extra option.

## R5 — Auto-scroll and jump-to-latest

- **Decision**: `MessageList` tracks whether the user is **pinned to the bottom** (a scroll
  listener comparing `scrollTop + clientHeight` to `scrollHeight` within a small threshold). On new
  content it auto-scrolls **only when pinned**; when the user has scrolled up it shows a
  **jump-to-latest** affordance that scrolls to the bottom and re-pins (FR-011).
- **Rationale**: Standard, dependency-free chat behavior; respects the user's scroll position
  during streaming while keeping "follow the latest" one click away. jsdom does not lay out
  scrolling, so the test asserts the affordance's **presence/absence** by stubbing the scroll
  metrics rather than measuring real layout.

## R6 — Opening an existing session

- **Decision**: Selecting a session in the sidebar sets it active, **replays its history through
  the same reducer** to rebuild the ordered entries, then streams live events (the existing
  `history` + `streamSession` endpoints). "New chat" resets to `initialState` and clears the active
  session so the next send opens a fresh one (the current lazy-open behavior).
- **Rationale**: Reuses existing endpoints with no contract change; replaying history through the
  reducer keeps one code path for "fold events → view model". History items are treated as the same
  normalized events the stream emits; any unknown item is ignored by the forward-compatible default
  (FR-016), so a shape mismatch degrades gracefully rather than crashing.
- **Scope note**: this is the additive, low-risk slice of US3 (P3); it does not add multi-session
  concurrency (one active session at a time, as today).

## R7 — Explicitly deferred (out of scope for 025)

Recorded so the boundary is unambiguous and traceable to the spec's "Out of Scope":

- **Syntax highlighting** of code blocks → unit 029 (needs a highlighter dependency).
- **Reasoning / thinking display**, **multi-option questions**, **token usage** → unit 026 (the
  backend already emits these; 025 keeps the single-answer question + plain status).
- **Skills / MCP / memory panels**, **model selection**, **file upload** → units 027 / 028.
- **Transport / backend change** → none; the REST + SSE contract is reused verbatim.

**Output**: all Technical Context choices resolved; no open clarifications remain.
