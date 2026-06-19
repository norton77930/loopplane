# Feature Specification: Web Message Actions

**Feature Branch**: `031-web-message-actions` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Give each message in the web chat the actions a modern agent app
has: **copy** a message's text with one click, **regenerate** the latest assistant response
(re-run the last user turn), and a **copy button on code blocks**. All **frontend-only** — it
re-uses the existing send path and changes nothing on the backend."

## Overview

In the current web UI a message, once shown, is **inert** — there is no way to copy it,
re-run it, or copy a code snippet without manually selecting text. These per-message actions
are table-stakes in a modern agent app.

This unit adds them, **entirely on the frontend**. **Copy** puts a message's text on the
clipboard; **Regenerate** re-runs the **last user turn** through the **existing send path**
to produce a fresh response; a **copy button** on fenced **code blocks** copies the exact
code. Nothing changes on the backend — the web/API host, its event/endpoint contract, and the
Python package are **untouched**, and the `apps/web` toolchain and its isolated gate are
reused. The design is **written fresh**; no private or legacy UI is copied (Principle VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Copy a message (Priority: P1)

A user hovers a message and clicks **Copy**; the message's text is placed on the clipboard,
with brief confirmation. This works for both their own messages and the assistant's.

**Why this priority**: Copying output is the single most-used message action and is purely
presentational — high value, no risk, no backend.

**Independent Test**: Hover a message, click Copy — the clipboard holds the message text and a
brief confirmation is shown; works on user and assistant messages.

**Acceptance Scenarios**:

1. **Given** any message, **When** the user clicks its Copy action, **Then** the message's text
   is placed on the clipboard and a brief confirmation is shown.
2. **Given** the clipboard is unavailable, **When** Copy is used, **Then** it falls back
   gracefully (an alternate copy path) without error.

---

### User Story 2 - Regenerate the latest response (Priority: P2)

A user wants a different answer; they click **Regenerate**, and the app re-runs the **last user
turn** to produce a fresh assistant response.

**Why this priority**: Regenerate is the second core action and turns a one-shot reply into an
iterable one; it re-uses the existing send path, so it is still frontend-only.

**Independent Test**: After a completed turn, click Regenerate — the last user prompt is
re-sent and a new response streams; Regenerate is unavailable while a run is in flight and when
there is no prior user turn.

**Acceptance Scenarios**:

1. **Given** a completed turn with a prior user message, **When** the user clicks Regenerate,
   **Then** the last user prompt is re-sent and a new response streams in.
2. **Given** a run is currently in flight, **When** the user looks for Regenerate, **Then** it
   is disabled (no concurrent re-run).
3. **Given** no user turn has been sent yet, **When** the conversation is empty, **Then**
   Regenerate is not offered.

---

### User Story 3 - Copy a code block (Priority: P3)

A user reading a fenced code block clicks a **copy button** on it; the exact code is placed on
the clipboard.

**Why this priority**: Copying code is a frequent, friction-heavy task (manual selection is
error-prone); it is a self-contained addition to the existing code rendering.

**Independent Test**: An assistant message with a fenced code block shows a copy button;
clicking it places the block's exact text (not surrounding prose) on the clipboard.

**Acceptance Scenarios**:

1. **Given** a fenced code block, **When** it renders, **Then** it shows a copy button.
2. **Given** the copy button, **When** clicked, **Then** the block's **exact** code is copied
   (no prose, no decoration) with brief confirmation.

---

### Edge Cases

- **Clipboard API unavailable / permission denied** → a graceful fallback copy path; never an
  unhandled error.
- **Regenerate while a run is in flight** → disabled (no concurrent re-run).
- **Regenerate with no prior user turn** → not offered.
- **Copy on a still-streaming message** → copies what is present at click time (no error).
- **A very long message / code block** → copy still works; the action affordance does not break
  the layout.
- **Code block copy** → copies the raw code text exactly, excluding the surrounding markdown.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each message MUST offer a **Copy** action that places the message's text on the
  clipboard, with brief confirmation; it MUST work for both user and assistant messages.
- **FR-002**: Copy MUST **degrade gracefully** when the clipboard API is unavailable (an
  alternate copy path), never raising an unhandled error.
- **FR-003**: The UI MUST offer **Regenerate** for the latest response, which **re-runs the last
  user turn** through the existing send path to produce a fresh response.
- **FR-004**: Regenerate MUST be **unavailable while a run is in flight** and **when there is no
  prior user turn**.
- **FR-005**: Fenced **code blocks** MUST show a **copy button** that copies the block's **exact**
  code (excluding surrounding prose/markdown), with brief confirmation.
- **FR-006**: Every action MUST be **frontend-only** — no change to the web/API host, its
  event/endpoint contract, or the Python package; the `apps/web` gate MUST stay green; each action
  **degrades gracefully** when its preconditions are absent.
- **FR-007**: **No committed artifact** may contain a private path, internal name, IP, key, token,
  or secret, and **no private or legacy UI may be copied**.

### Key Entities

- **Message action**: a per-message affordance — **Copy** (message text) or **Regenerate** (re-run
  the last user turn), shown contextually (e.g., on hover).
- **Code-block action**: a **copy** affordance on a fenced code block that copies the exact code.

### Out of Scope

- **Editing a prior user message** (re-running an edited turn) — needs backend
  truncation/branching; a later unit.
- **Thumbs / feedback persistence** — needs a backend sink; a later unit.
- **Any backend change** — the web/API host, its events/endpoints, and the Python package are
  unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can **copy** any message's text in one click (with a graceful fallback when
  the clipboard API is unavailable).
- **SC-002**: A user can **regenerate** the latest response, which re-runs the last user turn;
  Regenerate is disabled during a run and absent when there is no prior user turn.
- **SC-003**: A user can **copy a code block's exact text** in one click.
- **SC-004**: Every action is **frontend-only** — the `apps/web` gate (type-check + tests + build)
  is **green**, and the **Python suite and the backend contract are unchanged**.
- **SC-005**: A **public-safety scan is clean**, and **no private or legacy UI is copied**.

## Assumptions

- **Builds on 025**: reuses the unit-025 message list + markdown rendering and the existing send
  path; sequenced after the session-management unit but independent of it.
- **Regenerate re-uses the existing send path**: re-running the last user turn is the existing
  submit action with a remembered prompt — **no backend change** and no new event/endpoint.
- **Frontend-only, no ADR**: every action is presentational or re-uses an existing path; nothing
  touches a runtime boundary.
- **Additive, reversible (Principle X)**: removing these restores the prior message list; the
  backend and Python suite are unaffected.
- **Fresh design, public-safe (VII)**: written fresh; no private or legacy UI is copied.
