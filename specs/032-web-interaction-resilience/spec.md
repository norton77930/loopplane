# Feature Specification: Web Interaction Resilience & States

**Feature Branch**: `032-web-interaction-resilience` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Make the web app's interactions feel robust and finished:
approval/question dialogs become **true modals** (a backdrop, focus trapped inside, **Esc** to
dismiss safely, options navigable by keyboard); a disconnect offers a **Retry** action and the
app uses brief **toast** notifications for transient feedback; and the app shows **loading
skeletons**, a **richer empty state**, and **first-run example prompts** to get started. All
**frontend-only**."

## Overview

The web UI works, but its interactions still feel unfinished: the approval and question
dialogs are **in-flow blocks** (no backdrop, no focus trap, **Esc** does nothing, options are
not keyboard-navigable — an accessibility gap); a disconnect shows a **passive** banner with no
way to recover; there are **no loading states**, so fetches feel like the app stalled; and a
first-time user meets a **blank** screen with no guidance.

This unit closes those gaps, **entirely on the frontend**: promote the dialogs to **true
modals** (backdrop, focus trap, Esc-to-dismiss-safely, keyboard-navigable options, focus
restored on close); add a **Retry** action to the connection-error banner plus brief **toasts**
for transient feedback; and add **loading skeletons**, a **richer empty state**, and **first-run
example prompts** that start a conversation. Nothing changes on the backend — the web/API host,
its event/endpoint contract, and the Python package are **untouched**, and the `apps/web`
toolchain and its isolated gate are reused. The design is **written fresh**; no private or legacy
UI is copied (Principle VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dialogs behave like real modals (Priority: P1)

When the agent asks for approval or a question, the dialog appears as a **true modal**: a
backdrop dims the page, focus is **trapped** inside, **Esc** dismisses it with the safe default
(deny / cancel), the options are **keyboard-navigable**, and focus **returns** to where it was
on close.

**Why this priority**: These dialogs gate the agent's progress and are an accessibility
must-fix; making them real modals is the highest-impact robustness item.

**Independent Test**: Trigger an approval/question — focus is trapped in the dialog, Tab/arrow
keys move between options, Esc dismisses with the safe default, and focus returns to the trigger
afterward.

**Acceptance Scenarios**:

1. **Given** an approval/question dialog is open, **When** the user presses **Tab**, **Then**
   focus cycles **within** the dialog and does not reach the page behind it.
2. **Given** an open dialog, **When** the user presses **Esc**, **Then** it is dismissed with the
   **safe default** (deny / cancel) and focus returns to the prior element.
3. **Given** an open dialog with options, **When** the user navigates by keyboard, **Then** the
   options are reachable and selectable without a mouse.

---

### User Story 2 - Recover from a disconnect (Priority: P2)

When the connection drops, the error banner offers a **Retry** that re-establishes the live
stream; transient outcomes (retry result, copy/rename success) appear as brief, auto-dismissing
**toasts**.

**Why this priority**: A passive "disconnected" message with no recovery path is a dead end;
Retry + lightweight feedback makes failures recoverable and the app communicative.

**Independent Test**: Simulate a disconnect — the banner shows a Retry; clicking it
re-establishes the stream and clears the error (or shows a toast if it fails again); transient
actions surface a brief toast that auto-dismisses.

**Acceptance Scenarios**:

1. **Given** a connection error, **When** the banner is shown, **Then** it offers a **Retry**
   action.
2. **Given** the Retry action, **When** clicked, **Then** the live stream is re-established and
   the error is cleared; **And** if it fails again, the user is informed (e.g., a toast) without
   losing the conversation.
3. **Given** a transient action (e.g., a successful copy/rename), **When** it completes, **Then** a
   brief **toast** confirms it and auto-dismisses.

---

### User Story 3 - Clear loading, empty, and first-run states (Priority: P3)

While data loads, the app shows **skeleton placeholders** instead of a blank gap; an empty
conversation shows a **richer empty state** with **example prompts** that start a conversation
when clicked.

**Why this priority**: Loading and empty states are what make an app feel responsive and
welcoming rather than broken; first-run prompts lower the blank-page barrier.

**Independent Test**: While sessions/history load, skeletons are shown; with an empty
conversation, example prompts appear and clicking one starts a conversation.

**Acceptance Scenarios**:

1. **Given** sessions or a conversation are loading, **When** the user waits, **Then** **skeleton
   placeholders** are shown (not a blank area), replaced by content when it arrives.
2. **Given** an empty conversation, **When** it renders, **Then** a **richer empty state** with
   **example prompts** is shown.
3. **Given** an example prompt, **When** clicked, **Then** it starts a conversation with that
   prompt.

---

### Edge Cases

- **Esc on an approval dialog** → resolves to the **safe default** (deny), never an implicit
  approval.
- **Focus restoration** → on dialog close, focus returns to the element that opened it.
- **Retry while still offline** → the error persists / a toast informs; the conversation is
  preserved (never cleared by a failed retry).
- **Many toasts at once** → they stack and each auto-dismisses; they never obscure the composer
  permanently.
- **Skeleton → content vs empty** → a finished load shows either content or the empty state, never
  a stuck skeleton.
- **Example prompt while a run is in flight** → respects the same in-flight rules as normal
  sending (disabled while running).
- **A modal on a small screen** → the dialog remains usable and dismissible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Approval and question dialogs MUST be **true modals**: a **backdrop**, **focus
  trapped** within, and **focus restored** to the prior element on close.
- **FR-002**: An open dialog MUST be dismissible with **Esc**, resolving to the **safe default**
  (deny / cancel) — never an implicit approval.
- **FR-003**: Dialog **options MUST be keyboard-navigable** and selectable without a mouse.
- **FR-004**: The connection-error banner MUST offer a **Retry** that **re-establishes the live
  stream** and clears the error; a failed retry MUST inform the user **without losing the
  conversation**.
- **FR-005**: The app MUST show brief, **auto-dismissing toast** notifications for transient
  outcomes (e.g., retry result, copy/rename success).
- **FR-006**: The app MUST show **loading skeleton** placeholders while sessions/history load
  (not a blank area), replaced by content or an empty state when the load finishes.
- **FR-007**: An empty conversation MUST show a **richer empty state** with **example prompts**;
  selecting a prompt MUST **start a conversation** with it (respecting the in-flight send rules).
- **FR-008**: Every change MUST be **frontend-only** — no change to the web/API host, its
  event/endpoint contract, or the Python package; the `apps/web` gate MUST stay green; each item
  **degrades gracefully** when its inputs are absent.
- **FR-009**: **No committed artifact** may contain a private path, internal name, IP, key, token,
  or secret, and **no private or legacy UI may be copied**.

### Key Entities

- **Modal dialog**: an approval or question dialog presented with a backdrop, a focus trap,
  Esc-to-dismiss-safely, keyboard-navigable options, and focus restoration.
- **Toast**: a brief, auto-dismissing notification for a transient outcome.
- **Loading skeleton**: a placeholder shown while a region's data loads.
- **Empty / first-run state**: a richer empty conversation view with example prompts that start a
  conversation.

### Out of Scope

- **A full accessibility audit** beyond modal focus management + keyboard navigation of these
  dialogs.
- **Restoring full conversation content when re-opening a past session** — a known pre-existing
  gap (history is exposed as metadata only); out of scope here and flagged for a future unit. The
  richer empty state is **not** a fix for it.
- **Visual / brand redesign** — a separate later thrust; this unit reuses the current visual
  tokens.
- **Any backend change** — the web/API host, its events/endpoints, and the Python package are
  unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Approval/question dialogs **trap focus**, are **dismissible by Esc** with the safe
  default, expose **keyboard-navigable** options, and **restore focus** on close.
- **SC-002**: A disconnect offers a **Retry** that re-establishes the stream and clears the error;
  a failed retry informs the user and preserves the conversation.
- **SC-003**: Transient outcomes surface a brief **toast** that auto-dismisses.
- **SC-004**: Loading regions show **skeletons**; an empty conversation shows a **richer empty
  state** with **example prompts** that start a conversation.
- **SC-005**: Every item is **frontend-only** — the `apps/web` gate (type-check + tests + build)
  is **green**, and the **Python suite and the backend contract are unchanged**.
- **SC-006**: A **public-safety scan is clean**, and **no private or legacy UI is copied**.

## Assumptions

- **Builds on 025/026**: reuses the unit-025/026 approval & question dialogs, the error banner,
  the message list, and the sidebar; sequenced last, independent of 030/031.
- **Frontend-only, no ADR**: modals, toasts, retry, skeletons, and empty states are
  presentational or re-use the existing stream-establishment path; nothing touches a runtime
  boundary.
- **Safe-by-default dialogs**: Esc resolves to deny/cancel so dismissal can never imply approval.
- **Additive, reversible (Principle X)**: removing these restores the prior in-flow dialogs and
  banner; the backend and Python suite are unaffected.
- **Fresh design, public-safe (VII)**: written fresh; no private or legacy UI is copied.
