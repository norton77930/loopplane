---
description: "Task list for unit 025 — Web Agent UI (frontend-only overhaul of apps/web)"
---

# Tasks: Web Agent UI

**Input**: Design documents from `specs/025-web-agent-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (view-model.md, app-shell.md)

**Tests**: REQUIRED (Constitution X). Vitest + jsdom (Testing Library). Write the reducer +
component tests FIRST and confirm they FAIL before implementing. The api-layer tests
(`events`, `client`) and `AppRoot` tests stay green **unchanged** (reused as-is).

**Scope guard**: frontend-only under `apps/web/` — **no** backend/contract/Python change; **no**
syntax highlighting / reasoning / multi-option questions / usage (units 026/029). The web gate
(`tsc --noEmit` + `vitest run` + `vite build`) is green at the implement commit.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Add markdown deps to `apps/web/package.json` — `react-markdown` (^9) + `remark-gfm`
  (^4); run `npm install` in `apps/web`; confirm the baseline gate runs (`npm run typecheck`,
  `npm test`, `npm run build`). **No** syntax-highlight lib, **no** Playwright.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared view model + styling + shell frame every story renders into.

**⚠️ No user-story work begins until this phase is complete.**

- [ ] T002 [P] Write the reducer test FIRST (FAIL): rewrite `apps/web/src/__tests__/chat.test.ts`
  for the ordered-`entries` model per `contracts/view-model.md` — a user→assistant→tool(running)
  →tool(completed)→assistant interleave yields the expected ordered `entries`; an orphan/duplicate
  `tool-call-completed` is a no-op; `run-terminated` appends the terminal marker **and** clears a
  pending approval/question; an unknown event is ignored; `errored()` preserves `entries`.
- [ ] T003 Evolve `apps/web/src/state/chat.ts`: replace parallel `turns`/`timeline` with an ordered
  `entries: ConversationEntry[]` (the `user`/`assistant`/`tool`/`terminated` union from
  `data-model.md`); update `initialState`, `userPrompt`, `reduce`, `errored`, and the
  append/merge-assistant helper; keep it a **pure** function over the **same** events. Make T002 pass.
- [ ] T004 [P] Create `apps/web/src/styles.css`: theme tokens as CSS custom properties under
  `:root` (light) and `[data-theme="dark"]` (color/space/radius/typography); base reset + app layout;
  import it from `apps/web/src/main.tsx`. (Default light; the dynamic toggle is US2.)
- [ ] T005 Create `apps/web/src/components/AppShell.tsx`: a slot-based two-pane layout
  (`sidebar` | a chat column with a **sticky** header slot, a scrolling `children` region, and a
  **sticky** composer slot) per `contracts/app-shell.md` (FR-007); collapses/stacks on a narrow
  viewport.
- [ ] T006 Create `apps/web/src/components/Composer.tsx`: a sticky `<textarea>` that grows with
  multi-line content and **disables send while `status === "running"`** (FR-012); `onSend(text)`
  trims and ignores empty. Add `apps/web/src/__tests__/Composer.test.tsx` (grows; disabled while
  running; emits trimmed non-empty text).

**Checkpoint**: the reducer renders an ordered view model; a styled, empty shell mounts.

---

## Phase 3: User Story 1 - A conversation that feels like an agent (Priority: P1) 🎯 MVP

**Goal**: markdown assistant messages, inline collapsible tool cards (running→success/failure),
styled approval/question dialogs, and a run-end terminal marker — the core agent conversation.

**Independent Test**: with the demo backend, a reply renders as markdown, each tool call renders as
an inline status card, an approval/question renders as a dialog, and a run-end renders a terminal
marker (component tests + manual QA), with no backend change.

- [ ] T007 [P] [US1] Write tests FIRST (FAIL): `apps/web/src/__tests__/Markdown.test.tsx` (renders
  headings/list/code/table/link formatted; a raw `<script>`/HTML string is rendered **inert**, not
  injected) and `apps/web/src/__tests__/ToolCard.test.tsx` (running indicator with no outcome;
  success/failure when `outcome` set; toggles collapsed/expanded).
- [ ] T008 [P] [US1] Create `apps/web/src/components/Markdown.tsx`: a `react-markdown` + `remark-gfm`
  wrapper with **raw HTML disabled** (no `rehype-raw`) (FR-001). Make the Markdown test pass.
- [ ] T009 [P] [US1] Create `apps/web/src/components/ToolCard.tsx`: an inline **collapsible** card —
  tool name + status (running when `outcome === undefined`, else success/failure); consecutive cards
  group readably while each stays inspectable (FR-002/003). Make the ToolCard test pass.
- [ ] T010 [US1] Create `apps/web/src/components/MessageList.tsx`: render the ordered `entries` —
  `user` bubble (plain), `assistant` via `Markdown`, `tool` via `ToolCard`, `terminated` marker with
  its reason (FR-001/002/006). Add `apps/web/src/__tests__/MessageList.test.tsx` (interleave order;
  terminal marker). (Auto-scroll is added in US3 — T018.)
- [ ] T011 [P] [US1] Write tests FIRST (FAIL): `apps/web/src/__tests__/ApprovalDialog.test.tsx`
  (emits `{allow:true,scope:"once"}`, `{allow:false}`, `{allow:true,scope:"session"}`) and
  `apps/web/src/__tests__/QuestionDialog.test.tsx` (emits a single-element answer array).
- [ ] T012 [P] [US1] Create `apps/web/src/components/ApprovalDialog.tsx` (Allow / Deny / Always allow
  this session — FR-004) and `apps/web/src/components/QuestionDialog.tsx` (free-text single answer —
  FR-005). Make T011 pass.
- [ ] T013 [US1] Re-layout `apps/web/src/App.tsx` to render `AppShell` with `MessageList` +
  `ApprovalDialog`/`QuestionDialog` + `Composer` in the chat column; **reuse** all data logic
  (`send`/`ensureSession`/`readEvents`/`approve`/`answer`/`refreshSessions`/`fail`); widen `approve`
  to forward an optional `scope` to `client.answerApproval`. (Header/sidebar are minimal until
  US2/US3.)

**Checkpoint**: a signed-in user sees markdown + inline tool cards + styled dialogs + a terminal
marker — the MVP is demonstrable.

---

## Phase 4: User Story 2 - Light and dark theme (Priority: P2)

**Goal**: a light/dark toggle that restyles the whole UI, persists across reloads, and follows the
OS preference when unset.

**Independent Test**: toggle → the UI switches; reload → the choice persists; clear the stored
choice → it follows the OS preference.

- [ ] T014 [P] [US2] Write the test FIRST (FAIL): `apps/web/src/__tests__/theme.test.ts` — resolves
  to the stored value when present; falls back to `matchMedia` when unset; persists on toggle; a
  throwing storage/`matchMedia` falls back to light without throwing.
- [ ] T015 [US2] Create `apps/web/src/theme/theme.ts`: `Theme`/`StoredTheme`; read/resolve/persist
  (`localStorage["loopplane-theme"]` + `matchMedia("(prefers-color-scheme: dark)")`); apply via
  `document.documentElement.setAttribute("data-theme", …)`; all access wrapped in `try/catch`
  (data-model.md). Apply the initial theme in `apps/web/src/main.tsx`. Make T014 pass.
- [ ] T016 [US2] Create `apps/web/src/components/ThemeToggle.tsx` (flips light/dark via the theme
  module) + `apps/web/src/__tests__/ThemeToggle.test.tsx`; place it in the header slot.

**Checkpoint**: the theme toggles, persists, and defaults to the system preference.

---

## Phase 5: User Story 3 - Sessions, run control, and status (Priority: P3)

**Goal**: a sessions sidebar (list/recency/new-chat/open), a header status indicator + Stop, a
non-blocking error banner, and auto-scroll with jump-to-latest.

**Independent Test**: list/open sessions; Stop an in-flight run (existing cancel endpoint); force a
disconnect → error banner; scroll up during streaming → jump-to-latest.

- [ ] T017 [P] [US3] Create `apps/web/src/components/Sidebar.tsx`: list sessions (id + recency) with
  a **New chat** action and a clear **empty state**; `onOpen(id)` / `onNew()` (FR-008). Add
  `apps/web/src/__tests__/Sidebar.test.tsx` (empty + list states; fires onOpen/onNew).
- [ ] T018 [P] [US3] Create `apps/web/src/components/ChatHeader.tsx`: shows connection/run **status**
  (idle/running/terminated/error) and a **Stop** control visible while running (FR-009); hosts the
  `ThemeToggle`. Add `apps/web/src/__tests__/ChatHeader.test.tsx` (status text; Stop fires only while
  running).
- [ ] T019 [P] [US3] Create `apps/web/src/components/ErrorBanner.tsx`: a non-blocking banner shown on
  `status === "error"`, preserving the conversation (FR-010).
- [ ] T020 [US3] Add **auto-scroll + jump-to-latest** to `apps/web/src/components/MessageList.tsx`:
  track pinned-to-bottom; auto-scroll only when pinned; show a jump-to-latest affordance when
  scrolled up (FR-011). Extend `MessageList.test.tsx` (affordance appears when scroll metrics are
  stubbed off-bottom).
- [ ] T021 [US3] Wire US3 into `apps/web/src/App.tsx`: render `Sidebar` + `ChatHeader` +
  `ErrorBanner` in the shell; add `stop()` (→ `client.cancel(sessionId)`), `openSession(id)`
  (history replay through the reducer + live stream — R6), and `newChat()` (reset to `initialState`);
  refresh the session list on open.

**Checkpoint**: sessions list/open, Stop cancels, the error banner shows, and scrolling works.

---

## Phase 6: User Story 4 - A polished sign-in (Priority: P4)

**Goal**: a styled, centered, themed login card with a masked token field — the 023 behavior
unchanged.

**Independent Test**: no token → the themed centered login card; submit → the app loads; the token
stays masked; sessionStorage/logout/401-to-login unchanged.

- [ ] T022 [US4] Restyle `apps/web/src/components/Login.tsx` to a centered themed card (masked field;
  **behavior unchanged** — submit still calls `onSubmit(token)` for non-empty). Update
  `apps/web/src/__tests__/Login.test.tsx` if the markup changed (masked + submit + reject-empty
  preserved).

**Checkpoint**: the login matches the themed UI; auth behavior is unchanged.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Remove the replaced components + their tests: `apps/web/src/components/Conversation.tsx`,
  `Timeline.tsx`, `Prompts.tsx`, `SessionList.tsx` and `__tests__/{Conversation,Timeline,Prompts,
  SessionList}.test.tsx` (superseded by MessageList/ToolCard/dialogs/Sidebar).
- [ ] T024 Update `apps/web/src/__tests__/App.test.tsx` for the new shell: send → stream →
  approval/question → terminated; status reflects the run; **Stop** calls cancel; the 401 →
  `onUnauthorized` path is preserved — over a stubbed `client`.
- [ ] T025 [P] `docs/web-frontend.md`: add a **UI overhaul (025)** section (shell, markdown, tool
  cards, dialogs, status/Stop, sessions, scroll, theme, login).
- [ ] T026 [P] `CHANGELOG.md`: add a `025` entry under Added.
- [ ] T027 [P] `docs/loopplane-agent-board.md`: set **025 → Verified** with a status-evidence note;
  refresh §3/§4 to make **026** the active unit (next: plan).
- [ ] T028 Run the gates: in `apps/web` — `npm run typecheck`, `npm test`, `npm run build` — all
  green; confirm the **Python suite is unchanged** (`pytest` from the repo root); public-safety scan
  clean (no secret/path/internal name; **no legacy UI copied** — Constitution VII; `git diff` touches
  no `src/loopplane/**` or `openspec/`).
- [ ] T029 Final review: confirm **frontend-only** (no backend/contract change), the api-layer +
  `AppRoot` tests pass unchanged, and the rollback (revert the `apps/web` presentation diff) holds;
  commit (`feat: implement LoopPlane web-agent-ui`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T006)** precede all stories.
- **US1 (T007–T013)** is the MVP and depends only on Foundational (reducer + shell + composer).
- **US2 (T014–T016)** depends on the base tokens (T004); independent of US1/US3.
- **US3 (T017–T021)** depends on Foundational + the `MessageList` (T010 for the scroll work, T020);
  the Sidebar/Header/ErrorBanner are independent components wired by T021.
- **US4 (T022)** depends on the theme tokens (T004) for the card styling; 023 behavior unchanged.
- **Polish (T023–T029)** depends on all desired stories: old-component removal + the `App` test
  update + docs/board + the gates + final review.

### Within each story

- Tests are written first and must FAIL before implementation (T002, T007, T011, T014).
- Components before their `App` wiring (T013, T021 compose; T016 places the toggle).
- The web gate is green at the **implement commit** (intermediate red within the phase is fine).

### Parallel opportunities

- T001 is independent `[P]`.
- T002 (reducer test) and T004 (stylesheet) are independent `[P]`.
- Within US1: T007/T008/T009 (markdown + tool card) and T011/T012 (dialogs) are independent `[P]`
  until composed by T013.
- Within US3: T017/T018/T019 (sidebar / header / error banner) are independent `[P]`.
- Polish docs T025/T026/T027 are independent `[P]` files.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Setup (T001) → Foundational (T002–T006) → US1 (T007–T013).
2. **STOP and VALIDATE**: a signed-in user sees markdown + inline tool cards + styled dialogs + a
   terminal marker (SC-001/002).

### Incremental Delivery

- + US2 (theme) → + US3 (sessions/Stop/status/scroll) → + US4 (login) → Polish (cleanup, docs,
  board, gates). Each story adds value without breaking the previous ones.

---

## Notes

- The **api layer** (`api/client.ts`, `api/events.ts`, `api/types.ts`) and the **023 auth gate**
  (`AppRoot`) are reused **unchanged**; their tests stay green as-is.
- The only state change is **view-model shaping** (ordered `entries`) — a consumer-side adaptation
  the Event Bus principle (VI) allows; **no event schema change**.
- Markdown disables raw HTML, so model output cannot inject markup (FR-001 / VII).
- **Rollback**: revert the `apps/web` presentation diff (components, the reducer evolution, the
  stylesheet, the two deps) — the api layer, `AppRoot`, the backend, and the Python suite are
  untouched, so the unstyled-but-functional unit-018/023 app returns (Constitution X).
