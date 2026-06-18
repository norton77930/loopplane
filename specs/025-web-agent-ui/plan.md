# Implementation Plan: Web Agent UI

**Branch**: `025-web-agent-ui` (main-only) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/025-web-agent-ui/spec.md`

## Summary

A **frontend-only** visual + UX overhaul of the unit-018 SPA (`apps/web`) into a modern,
Claude-style agent UI, mapped entirely onto the **existing** unit-011 REST + SSE contract —
**no backend change**. The api layer (`api/client.ts`, `api/events.ts`, `api/types.ts`) and the
unit-023 auth gate (`AppRoot`) are **reused unchanged**. The chat reducer (`state/chat.ts`) is
evolved from two parallel arrays (`turns` + `timeline`) into a single **ordered `entries` list**
(a discriminated union: user message / assistant message / tool call / run-terminated marker) so
tool cards **interleave with messages in stream order** — the one piece of "view-model shaping"
the spec calls for (Assumptions; Constitution VI consumer-side adaptation).

On top, a presentation layer is added: a two-pane **app shell** (a sessions sidebar + a chat
column with a sticky header and a sticky composer); assistant **markdown** rendering (safe — no
raw HTML); **inline collapsible tool cards** (running → success/failure); styled **approval and
question dialogs**; a header **status indicator** + a **Stop** control (the existing cancel
endpoint); a non-blocking **error banner**; **auto-scroll** with a **jump-to-latest** affordance;
a styled **login**; and a **light/dark theme** (CSS custom properties; persisted in
`localStorage`; system-default fallback). Styling is plain CSS with custom properties — **no UI
framework**; markdown is `react-markdown` + `remark-gfm`, which render to React nodes (XSS-safe by
default; raw HTML disabled). Code-block **syntax highlighting**, a reasoning/thinking display,
multi-option questions, and token usage are **out of scope** (units 026 / 029). The web gate
(`tsc --noEmit` + `vitest run` + `vite build`) stays green; the Python suite and the backend
event/endpoint contract are **untouched**.

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (the existing `apps/web` toolchain).

**Primary Dependencies**: React + Vite + Vitest + jsdom + Testing Library (already in
`apps/web/package.json`). **New runtime deps**: `react-markdown` (^9) + `remark-gfm` (^4) for safe
assistant-output markdown. **No** UI/CSS framework (plain CSS custom properties), **no** Playwright,
**no** syntax-highlight library (deferred to unit 029).

**Storage**: `localStorage` holds the **theme preference** (persists across reloads and tabs;
system-default fallback when absent or blocked). The access token stays in `sessionStorage`
(unit 023, unchanged).

**Testing**: Vitest + jsdom (Testing Library). The api-layer tests (`events`, `client`) and the
`AppRoot` auth tests stay green **unchanged** (the api layer + auth gate are reused as-is); the
reducer test is rewritten for the ordered `entries` model; new component tests cover the new
presentation (a markdown assistant message; a tool card running → success/failure; the
approval/question dialogs incl. always-allow-session; status + Stop; the error banner;
jump-to-latest; the theme toggle + persistence; the sidebar empty/list states); the `App`
integration test is updated for the new shell while preserving the send / approval / question /
error / 401 flows.

**Target Platform**: a browser single-page app (the unit-018 web frontend) over the unit-011
`/v1` REST + SSE host.

**Project Type**: web frontend — **presentation + view-model shaping** under `apps/web/src/`. The
Python package and the backend are untouched.

**Performance Goals**: smooth streaming render; auto-scroll without layout thrash; markdown
re-render bounded to the streaming assistant entry. No hard numeric target (a local single-user UI).

**Constraints**: frontend-only; no backend or contract change; the api layer and `AppRoot` are
reused unchanged; the reducer stays a **pure** function over the **same** normalized events
(Constitution VI — consumer-side shaping, not a new event); markdown renders **without** raw-HTML
injection (FR-001 edge case); unknown events are still ignored (FR-016); no secret or legacy UI is
committed (FR-017 / Constitution VII); the web gate stays green and the Python suite is unchanged
(FR-015).

**Scale/Scope**: one reducer evolution, ~11 new presentation components (shell, sidebar, header,
message list, markdown, tool card, approval dialog, question dialog, composer, error banner, theme
toggle), a theme module + a stylesheet, a restyled login, the `App` re-layout, and a
docs/board/changelog touch. Four user stories P1–P4.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Every change traces to `spec.md` (FR-001–017; SC-001–006). | PASS |
| II — Greenfield | All new components/styles are written fresh; **no private or legacy UI is copied** (VII). | PASS |
| III — Harness before automation | A presentation overhaul; no loop automation introduced. | PASS |
| IV — Boundary Clarity | The UI still reaches the runtime only through the public web API via the reused `ApiClient`. | PASS |
| V — Tool Gateway Ownership | Untouched — the UI executes **no** tool; tool cards are a render of the existing started/completed events. | PASS |
| VI — Event Bus Ownership | The UI **consumes** the normalized SSE stream as before; the ordered-`entries` view model is **consumer-side adaptation** (VI explicitly allows consumers to adapt normalized events to their own needs). No event schema change. | PASS |
| VII — Public-Safe | No secret/path/internal name committed; the token (023) is untouched and never logged; markdown disables raw HTML so model output cannot inject markup; design written fresh. | PASS |
| VIII — No SDK Replacement | No runtime/framework swap; `react-markdown`/`remark-gfm` are presentation libraries inside the isolated `apps/web` toolchain, not the agent runtime. | PASS |
| IX — Reference, not clone | A modern "Claude-style" *aesthetic*; the implementation is derived for this app, not copied. | PASS |
| X — Testable Evolution | Reducer + component + updated integration tests; **rollback** = revert the `apps/web` presentation changes (api layer, `AppRoot`, backend, and the Python suite are unaffected — the unstyled-but-functional app returns). | PASS |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/025-web-agent-ui/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── view-model.md        # event → ordered ConversationEntry mapping; tool-card lifecycle; status; dialog/terminated edges
│   └── app-shell.md         # the presentation contract: two-pane shell, header status + Stop, composer, dialogs, theme, scroll, login
├── checklists/requirements.md
└── tasks.md                 # created by /speckit.tasks
```

### Source Code (repository root)

```text
apps/web/src/
├── api/                      # REUSED UNCHANGED — client.ts, events.ts, types.ts
├── state/
│   └── chat.ts               # EVOLVED — ordered `entries` (ConversationEntry[]) replaces parallel turns/timeline
├── theme/
│   └── theme.ts              # NEW — ThemePreference; read/resolve/persist (localStorage + matchMedia); apply to <html>
├── components/
│   ├── AppShell.tsx          # NEW — two-pane layout (sidebar | chat column)
│   ├── Sidebar.tsx           # NEW — session list (recency) + new-chat; replaces SessionList
│   ├── ChatHeader.tsx        # NEW — sticky header: connection/run status + Stop + theme toggle
│   ├── MessageList.tsx       # NEW — renders ordered entries; auto-scroll + jump-to-latest; replaces Conversation + Timeline
│   ├── Markdown.tsx          # NEW — react-markdown + remark-gfm wrapper (raw HTML disabled)
│   ├── ToolCard.tsx          # NEW — inline collapsible card; running → success/failure
│   ├── ApprovalDialog.tsx    # NEW — allow / deny / always-allow-this-session (existing decision scope)
│   ├── QuestionDialog.tsx    # NEW — free-text answer (single answer, current contract)
│   ├── Composer.tsx          # NEW — sticky growing textarea; disabled while running
│   ├── ErrorBanner.tsx       # NEW — non-blocking banner; preserves the conversation
│   ├── ThemeToggle.tsx       # NEW — light/dark toggle bound to the theme module
│   └── Login.tsx             # EDIT — restyled to the themed card (masked field; behavior unchanged)
├── App.tsx                   # EDIT — wire the shell; reuse send/ensureSession/readEvents/approve/answer/refreshSessions/fail; add stop (cancel) + open-session + theme
├── AppRoot.tsx               # REUSED UNCHANGED — the 023 auth gate
├── main.tsx                  # EDIT — import the stylesheet; apply the initial theme
└── styles.css                # NEW — theme tokens (light/dark custom properties) + component styles

apps/web/src/__tests__/
├── events.test.ts / client.test.ts / AppRoot.test.tsx   # REUSED UNCHANGED (api layer + auth gate)
├── chat.test.ts                                          # REWRITTEN — ordered entries + interleave + edges
├── MessageList.test.tsx / ToolCard.test.tsx / Markdown.test.tsx          # NEW
├── ApprovalDialog.test.tsx / QuestionDialog.test.tsx                     # NEW (replace Prompts.test.tsx)
├── Sidebar.test.tsx / ChatHeader.test.tsx / Composer.test.tsx            # NEW (Sidebar replaces SessionList.test.tsx)
├── theme.test.ts                                          # NEW
├── App.test.tsx                                           # UPDATED — new shell; send/approval/question/error/401 preserved
└── Login.test.tsx                                         # UPDATED — restyle; masked + submit behavior preserved
```

Removed (replaced by the components above): `components/Conversation.tsx`, `components/Timeline.tsx`,
`components/Prompts.tsx`, `components/SessionList.tsx` and their tests.

Edited (docs / drift):

```text
apps/web/package.json                # + react-markdown, remark-gfm
docs/web-frontend.md                 # + a "UI overhaul (025)" section
CHANGELOG.md                         # + a 025 entry
docs/loopplane-agent-board.md        # 025 → Verified; refresh §4 Active Feature
CLAUDE.md                            # SPECKIT marker → specs/025-web-agent-ui/plan.md
```

**Structure Decision**: The **api layer and the 023 auth gate are reused unchanged** — the seam
between the UI and the host does not move. The only state change is **view-model shaping**: the
reducer folds the same normalized events into one **ordered `entries` list** (instead of two
parallel arrays) so tool cards interleave with assistant messages in stream order — exactly the
adaptation Constitution VI grants a consumer. The presentation is rebuilt as a small set of
focused components under an `AppShell`, themed by CSS custom properties; the old four display
components are replaced. `App` keeps all of its data-flow logic and gains only `stop` (the
existing cancel endpoint), open-an-existing-session, and theme wiring. This keeps the change
**additive and reversible** (X): reverting the `apps/web` presentation diff restores the
unstyled-but-functional unit-018/023 app, with the backend and Python suite untouched.

## Phases

- **Phase 0 — Research** (`research.md`): the markdown library choice (`react-markdown` +
  `remark-gfm`, raw HTML disabled) and why a hand-rolled parser is rejected; the theming approach
  (CSS custom properties + `data-theme` + `localStorage` + `prefers-color-scheme`); the
  view-model-shaping decision (evolve the reducer to ordered `entries` vs. derive post-hoc — why
  derivation is impossible from parallel arrays); the always-allow-session mapping onto the
  existing `ApprovalDecision.scope`; the auto-scroll / jump-to-latest approach; the
  open-existing-session strategy (history replay through the same reducer); and the explicit
  deferral of syntax highlighting / reasoning / multi-option / usage.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the `ConversationEntry`
  union + the evolved `ChatState`; the `ThemePreference` model; the two contracts (the
  event → ordered-entries mapping with the tool-card lifecycle and the dialog/terminated edges;
  and the presentation contract for the shell, header/status/Stop, composer, dialogs, theme,
  scroll, and login); and a quickstart that drives the demo backend and runs the web gate.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD, **P1 → P4** — first the reducer (ordered entries)
  with its rewritten test; then the markdown message + tool card + message list; then the styled
  dialogs; then the shell + header (status + Stop) + composer + error banner + sidebar; then
  auto-scroll/jump-to-latest; then the theme module + toggle + stylesheet; then the restyled
  login; then the `App` re-layout and the updated `App` test; finally the styling pass, docs,
  changelog, and board. The web gate + the Python suite run before the commit.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
