# Contract: App Shell & Presentation

The presentation contract for the overhaul — the structure and behavior the component layer
guarantees, all driven by the reused `ApiClient` and the ordered view model
([view-model.md](./view-model.md)). UI copy is illustrative; the **behavior** is the contract.

## Layout — two-pane shell (`AppShell`)

```text
+--------------+-------------------------------------------------+
|  Sidebar     |  ChatHeader (sticky)   status . Stop . theme    |
|              +-------------------------------------------------+
|  + New chat  |  MessageList (scrolls)                          |
|  session ... |    user / assistant(markdown) / ToolCard /      |
|  session ... |    terminated   + jump-to-latest                |
|  (empty)     |    [ErrorBanner overlays, non-blocking]         |
|              +-------------------------------------------------+
|              |  Composer (sticky)   textarea + Send            |
+--------------+-------------------------------------------------+
```

- **Sidebar** lists sessions (id + recency) and a **New chat** action; an empty list shows a clear
  empty state (FR-008 / edge case). On a narrow viewport the sidebar collapses or stacks so the
  shell stays usable (edge case). Selecting a session opens it (history replay + live stream, R6);
  New chat resets to `initialState`.
- **ChatHeader** is **sticky**, shows the connection/run **status** (idle / running / terminated /
  error), a **Stop** control that calls `client.cancel(sessionId)` while a run is in flight
  (FR-009), and the **theme toggle**.
- **MessageList** renders the ordered `entries` (FR-001/002/006); auto-scrolls when pinned to the
  bottom and shows **jump-to-latest** when scrolled up (FR-011).
- **Composer** is **sticky**, a textarea that grows with multi-line content and is **disabled while
  `status === "running"`** (FR-012).

## Entry rendering

| Entry | Component | Behavior |
|---|---|---|
| `user` | message bubble | plain text, user-aligned |
| `assistant` | `Markdown` | `react-markdown` + `remark-gfm`; **raw HTML disabled** -> no injection (FR-001) |
| `tool` | `ToolCard` | collapsible; running -> success/failure; grouped when consecutive (FR-002/003) |
| `terminated` | terminal marker | shows the reason (FR-006) |

## Dialogs (in-flow, styled)

- **ApprovalDialog** (when `pendingApproval`): **Allow** (`{allow:true, scope:"once"}`), **Deny**
  (`{allow:false}`), **Always allow this session** (`{allow:true, scope:"session"}`) -> `App.approve`
  -> `client.answerApproval` (FR-004).
- **QuestionDialog** (when `pendingQuestion`): a **free-text** field -> `App.answer` ->
  `client.answerQuestion(id, reqId, [text])` (FR-005, single answer per the current contract).

A dialog appears in the conversation flow; a `run-terminated` while one is pending clears it
(view-model.md section 4).

## Theme (FR-013)

`ThemeToggle` flips `light`/`dark` via the theme module (data-model.md): apply `data-theme` on
`<html>`, persist to `localStorage`, default to the OS preference when unset; storage failure falls
back to light without error. The whole UI restyles from CSS custom properties.

## Login (FR-014)

`Login` (unit 023, restyled) is a centered, themed card with a **masked** token field; submit loads
the app. The **023 behavior is unchanged**: `sessionStorage` token, logout, and 401-to-login are
owned by `AppRoot`/`App` and are not modified here.

## Status & error (FR-009 / FR-010)

| `status` | Header shows | Composer | Notes |
|---|---|---|---|
| `idle` | "Idle" | enabled | ready |
| `running` | "Running" + **Stop** | disabled send | Stop -> cancel |
| `terminated` | "Ended" | enabled | terminal marker in the list |
| `error` | "Disconnected" | enabled | **ErrorBanner** (non-blocking) over the intact conversation |

## Frontend-only guarantee (FR-015)

No web/API host, event/endpoint contract, or Python change. The `apps/web` toolchain + its isolated
CI gate (`tsc --noEmit` + `vitest run` + `vite build`) are reused and stay green; the Python suite
is unchanged. Reverting the `apps/web` presentation diff restores the unstyled-but-functional app
(Constitution X rollback).

## Verification

Component tests (jsdom + Testing Library): a markdown assistant message renders formatted (and raw
HTML stays inert); a `ToolCard` shows running then success/failure and toggles collapse; the
approval dialog emits the three decisions incl. session scope; the question dialog emits a
single-element answer; the header reflects status and Stop calls cancel; the composer disables
while running; jump-to-latest appears when scrolled up; the theme toggle flips + persists; the
sidebar shows empty + list states. The `App` integration test exercises send -> stream ->
approval/question -> terminated and the 401 -> onUnauthorized path over a stubbed client.
