# Feature Specification: Web Session Management

**Feature Branch**: `030-web-session-management` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Make the web app's sessions sidebar product-grade and let a
user manage their sessions: show each session by a meaningful **title** (not the raw
identifier), grouped by **recency** (Today / Yesterday / Earlier); let the user **rename** a
session (the title persists across reloads and restarts, on any device of the same user) and
**delete** a session (durably removed, guarded by a confirm). Delivered as an **additive,
full-stack** change (no ADR): the existing per-user session list is extended with a persisted
title and the ability to rename/delete, keeping every session **private to its owner**."

## Overview

After units 025–029 the web UI is a capable agent app, but the **sessions sidebar** is not
usable as a real product: it lists each session by its **raw identifier** with no title and no
grouping, and there is **no way to rename or delete** a session. At any real volume the list
becomes an undifferentiated wall of identifiers.

This unit makes session management product-grade. It is the sprint's **one full-stack** slice:
the existing per-user session record already carries a **title field** that is set once at
creation and never updated, and the listing already scopes sessions to their **owner** (unit
022). This unit **additively** extends that existing session contract so a title can be
**updated** and a session can be **deleted**, and surfaces titles + recency grouping + rename +
delete in the sidebar. It touches neither the **Tool Gateway** (Principle V) nor the **Runtime
Event Bus** (Principle VI) — it is **session-metadata management** over the durable session
store the host already owns — so it needs **no ADR**, matching the additive posture of units
027/028. The design is **written fresh**; no private or legacy UI/code is copied (Principle VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recognize sessions by title and recency (Priority: P1)

A user opens the app and sees their past sessions in the sidebar listed by a **readable title**
(not a raw identifier), **grouped by recency** (Today / Yesterday / Earlier). They can tell
sessions apart at a glance and find a recent one quickly.

**Why this priority**: This is the core usability fix — without it the list is unusable at any
real volume. It is the read-side foundation the other stories build on.

**Independent Test**: With several sessions of differing ages, the sidebar shows each by a title
(falling back to a short readable form when a session has no title yet) and groups them under
Today / Yesterday / Earlier; selecting one still opens it.

**Acceptance Scenarios**:

1. **Given** sessions exist, **When** the sidebar renders, **Then** each session shows a readable
   title (its set title, or a graceful fallback) rather than the raw identifier.
2. **Given** sessions of different ages, **When** the sidebar renders, **Then** they are grouped
   under **Today / Yesterday / Earlier** by their last activity, most-recent first.
3. **Given** a session with no title set, **When** it renders, **Then** a graceful fallback is
   shown (never a blank row), and the session is still openable.

---

### User Story 2 - Rename a session (Priority: P2)

A user gives a session a meaningful name. The new title is **saved on the server** and is shown
everywhere that session appears — and it is still there after a reload, after the server
restarts, and from another device signed in as the same user.

**Why this priority**: Renaming is the primary act that makes the list meaningful; it depends on
the read experience from US1 but delivers the durable, cross-device value the user asked for.

**Independent Test**: Rename a session; the sidebar shows the new title immediately; reload the
page and restart the backend — the new title is still shown.

**Acceptance Scenarios**:

1. **Given** a session, **When** the user renames it, **Then** the new title is shown immediately
   and persists across a page reload and a backend restart.
2. **Given** a rename with an empty or whitespace-only title, **When** submitted, **Then** it is
   rejected and the existing title is unchanged.
3. **Given** a session that is **not** owned by the current user, **When** a rename is attempted,
   **Then** it fails as **not found** — no rename occurs and the session's existence is not
   revealed.

---

### User Story 3 - Delete a session (Priority: P3)

A user removes a session they no longer want. After a confirmation, it is **durably deleted** and
disappears from the list — and stays gone after a reload and a restart.

**Why this priority**: Deletion completes session management and keeps the list clean; it is last
because it is the most destructive and the least frequent.

**Independent Test**: Delete a session (confirm the prompt); it disappears from the sidebar;
reload and restart the backend — it does not come back.

**Acceptance Scenarios**:

1. **Given** a session, **When** the user deletes it and confirms, **Then** it is removed from the
   list and does not reappear after a reload or backend restart.
2. **Given** the deletion of the **currently open** session, **When** it completes, **Then** the
   app returns to a sane empty/new state without error.
3. **Given** a session that is **not** owned by the current user, **When** a delete is attempted,
   **Then** it fails as **not found** — nothing is deleted and the session's existence is not
   revealed.
4. **Given** the delete is not confirmed, **When** the user dismisses the prompt, **Then** nothing
   is deleted.

---

### Edge Cases

- **No sessions** → the sidebar shows its existing empty state (unchanged).
- **A session with no title** → a graceful, readable fallback (never the raw identifier as the
  only label, never a blank row).
- **A very long title** → the sidebar truncates it for display without breaking the layout; the
  full title is preserved server-side.
- **Renaming the same session twice** → the latest title wins, consistently, in the list and when
  the session is later resumed.
- **Deleting a session that was already deleted** (double-click, stale list) → idempotent: no
  error, the list reflects the deletion.
- **A non-owner attempts rename or delete** → treated as **not found** (no existence or ownership
  leak), identical to how non-owners already cannot view another user's session.
- **Day-boundary / timezone** for grouping → grouping is by the viewer's local day; a session from
  late "yesterday" groups correctly relative to now.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The sidebar MUST display each session by a **readable title** rather than its raw
  identifier, with a **graceful fallback** when a session has no title (never a blank row).
- **FR-002**: The sidebar MUST **group sessions by recency** (**Today / Yesterday / Earlier**) by
  last activity, most-recent first.
- **FR-003**: A user MUST be able to **rename** a session; the new title MUST be **persisted on the
  server** and remain after a **page reload**, a **backend restart**, and when viewed from
  **another device** signed in as the same user.
- **FR-004**: A rename with an **empty or whitespace-only** title MUST be **rejected**, leaving the
  existing title unchanged.
- **FR-005**: A user MUST be able to **delete** a session; the deletion MUST be **durable** (it does
  not reappear after reload/restart) and MUST be **guarded by a confirmation**.
- **FR-006**: Deleting the **currently open** session MUST leave the app in a sane state (an empty /
  new-conversation state), without error.
- **FR-007**: Rename and delete MUST be **owner-scoped**: only the owning user may rename, delete, or
  see a session; a non-owner's attempt MUST fail as **not found**, revealing neither existence nor
  ownership (consistent with the existing per-user session scoping).
- **FR-008**: The change MUST be **additive and need no ADR**: it extends the **existing** session
  list/record contract additively to support an updatable title and deletion; it changes **neither
  the Tool Gateway execution path (V) nor the Runtime Event Bus (VI)**; the web/API layer's import
  boundary MUST be preserved; **rollback** is reverting the diff.
- **FR-009**: The behavior MUST be **covered by tests** end-to-end: the durable store (both storage
  backends), the host/controller methods, and the web/API routes — **including the non-owner
  not-found cases** — plus the frontend; the Python gate and the `apps/web` gate MUST stay green.
- **FR-010**: **No committed artifact** may contain a private path, internal name, IP, key, token, or
  secret, and **no private or legacy UI/code may be copied**.

### Key Entities

- **Session**: a saved conversation owned by one user, with a durable **identifier**, an updatable
  **title**, a **created** time, and a **last-active** time. Already private to its owner (022).
- **Session list**: the owner's sessions, most-recent-first, presented **grouped by recency** with a
  per-session **rename** and **delete** affordance.

### Out of Scope

- **Editing a prior user message** (re-running an edited turn) — needs conversation
  truncation/branching; a later unit.
- **In-session message search** — needs a search endpoint; a later unit.
- **Thumbs / feedback persistence** — needs a feedback sink; a later unit.
- **Visual / brand redesign** — a separate later thrust; this unit reuses the current visual tokens.
- **Restoring full conversation content when re-opening a past session** — a known pre-existing gap
  (session history is exposed as metadata only); out of scope here and flagged for a future unit.
- **Sharing or transferring a session across users** — sessions remain private to their owner.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can distinguish and locate sessions in the sidebar by **title** and **recency
  group**, with a graceful fallback for an untitled session.
- **SC-002**: A renamed session's title **persists** across a page reload **and** a backend restart,
  and is visible from another device of the same user.
- **SC-003**: A rename with an empty/whitespace title is rejected; the latest non-empty rename wins
  consistently in the list and on resume.
- **SC-004**: A deleted session is **durably removed** (absent after reload and restart); deleting the
  open session returns the app to a sane state; the delete is guarded by a confirm.
- **SC-005**: A **non-owner** rename or delete returns **not found** with no existence/ownership leak;
  the owner's sessions are unaffected.
- **SC-006**: The change is **additive with no ADR**: the **Python suite is green** (including new
  store/host/web tests and the non-owner cases), the **web/API import-boundary test stays green**, and
  the `apps/web` gate (type-check + tests + build) is **green**.
- **SC-007**: A **public-safety scan is clean** (no private path, internal name, IP, key, token, or
  secret), and **no private or legacy UI/code is copied**.

## Assumptions

- **Builds on 021 + 022**: reuses the interchangeable durable session storage (021) and the
  per-user session scoping (022); the session record already carries a **title field** and an
  **owner**, so this unit **updates** the title and **adds** deletion **additively** rather than
  inventing new storage.
- **Additive, no ADR**: persisting a title and deleting a session is **session-metadata management**
  over the store the host already owns; it crosses **no** runtime boundary (no Tool Gateway
  execution, no Event Bus), so — like 027/028 — it needs **no ADR**.
- **Owner-scoped by default**: rename/delete inherit the existing per-user scoping; a non-owner is
  answered exactly as today (not found), so no new authorization model is introduced.
- **Reversible (Principle X)**: reverting the diff restores the units-025–029 behavior (the sidebar
  falls back to its prior listing); already-saved titles become inert and deleted sessions stay
  deleted (a delete is intended to be durable).
- **Fresh design, public-safe (VII)**: the implementation is written fresh; no private or legacy UI
  or code is copied.
