# Feature Specification: Web Agent UI

**Feature Branch**: `025-web-agent-ui` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "The web frontend (unit 018) renders over the web/API host (unit 011, REST + SSE) but ships with no styling — classNames exist with no stylesheet — so it presents as unstyled black-on-white, a single vertical column, plain-text assistant output, and a flat text event timeline. It works, but it does not feel like a modern agent. Do a frontend-only visual and UX overhaul of the existing single-page app, mapped onto the backend's existing event stream: a professional two-pane app shell (sessions sidebar + a chat column with a sticky header and composer), assistant messages rendered as markdown, tool calls shown as inline collapsible cards with running/success/failure status, styled approval and question dialogs, connection/run status indicators and an error banner, a Stop control to cancel a run, auto-scroll with jump-to-latest, a styled login screen, and a light/dark theme toggle with a remembered preference. No backend change. Capabilities that would need new backend events or endpoints — thinking/reasoning display, model selection, file upload, question option lists, cost/usage, skills/MCP panels — are out of scope and recorded as a follow-up backlog. The visual target is a modern Claude-style aesthetic; the design is written fresh with no private or legacy UI copied."

## Overview

The web frontend (unit 018) is a from-scratch React single-page app under `apps/web/` that
runs over the unit-011 web/API host (REST + an SSE event stream). It is **functionally
complete** — login, streamed assistant output, a tool/run timeline, approval and question
prompts, a composer, and a session list — but it ships with **no stylesheet**: every
`className` is present yet unstyled, so the app renders as **browser-default black text on
white**, a **single vertical column**, **plain-text** assistant output, and a **flat
text-only event list**. It works, but it does not look or feel like a modern agent.

This unit is a **frontend-only visual and UX overhaul** of that existing SPA. It changes
**presentation and view-model shaping only**, mapped onto the backend's **existing**
normalized event stream (assistant output increments, tool-call started/completed, approval
requests, questions, run termination) and **existing** session endpoints (list, open,
cancel, history). It delivers: a **two-pane app shell** (a sessions sidebar plus a chat
column with a sticky header and a sticky composer); assistant messages rendered as
**formatted markdown**; tool calls shown **inline as collapsible cards** with a running →
success/failure status; **styled approval and question dialogs**; **connection/run status**
indicators and a non-blocking **error banner**; a **Stop** control that cancels an in-flight
run; **auto-scroll** with a **jump-to-latest** affordance; a **styled login** screen; and a
**light/dark theme** toggle with a remembered preference.

It is **frontend-only**: the web/API host, its event and endpoint contract, and the Python
package are **untouched**, and the `apps/web` toolchain and its **isolated CI gate** are
reused. Capabilities that would require **new backend events or endpoints** — a
thinking/reasoning display, model selection, file upload, multi-option questions, cost/usage,
and skills/MCP panels — are **explicitly out of scope** for this unit and recorded as a
**follow-up backlog** (the next unit). The visual target is a modern Claude-style aesthetic;
the design is **written fresh** — **no private or legacy UI is copied** (Constitution VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A conversation that feels like an agent (Priority: P1)

A signed-in user sends a prompt and watches the agent work: the streamed assistant reply
renders as **formatted markdown** (headings, lists, tables, code blocks, links); each tool
the agent calls appears **inline as a collapsible card** showing the tool name and a status
that moves from **running** to **success** or **failure**; when the agent needs a decision,
a **styled approval or question dialog** appears in the flow; and when the run ends, the
conversation shows a clear **terminal marker**.

**Why this priority**: This is the entire point of the unit — turning a plain-text dump into
a legible, trustworthy agent conversation where the user can follow the model's output and
its tool-execution trail. It delivers the core value on its own.

**Independent Test**: With the demo backend, send a prompt; the reply renders as markdown,
each tool call renders as an inline status card, an approval/question renders as a dialog,
and a run-end renders a terminal marker — verifiable by the component tests plus manual QA,
with no backend change.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** the assistant streams text, **Then** it renders as formatted markdown, not raw characters.
2. **Given** a `tool-call-started` event, **When** it arrives, **Then** an inline card shows the tool name with a running indicator; **When** the matching `tool-call-completed` arrives, **Then** the card shows success or failure.
3. **Given** consecutive tool calls in one turn, **When** they render, **Then** they are grouped readably while each tool's status stays inspectable.
4. **Given** an `approval-requested` event, **When** it arrives, **Then** a styled dialog offers allow and deny (and an "always allow for this session" choice).
5. **Given** a `question-asked` event, **When** it arrives, **Then** a styled dialog accepts a free-text answer.
6. **Given** a `run-terminated` event, **When** it arrives, **Then** a clear terminal marker shows the reason.

### User Story 2 - Light and dark theme (Priority: P2)

A user switches between a light and a dark appearance; the whole UI follows, and the choice
is remembered across reloads. With no stored choice, the app follows the operating system
preference.

**Why this priority**: A theme toggle is a baseline expectation for a modern agent UI and is
low-risk and self-contained; it materially improves the "professional" feel and comfort.

**Independent Test**: Toggle the theme — the whole UI switches; reload — the choice persists;
clear the stored choice — the initial theme follows the OS preference.

**Acceptance Scenarios**:

1. **Given** the app, **When** the user toggles the theme, **Then** the entire UI switches appearance and the choice persists across a reload.
2. **Given** no stored preference, **When** the app first loads, **Then** the theme follows the OS preference.

### User Story 3 - Sessions, run control, and status (Priority: P3)

A user manages work from the shell: a sidebar lists existing sessions and starts a new chat;
the header shows connection/run status; a **Stop** control cancels an in-flight run; failures
show as an **error banner**; and the message area auto-scrolls, offering a **jump-to-latest**
affordance after the user scrolls up.

**Why this priority**: These controls make the overhaul a usable workspace rather than a
single scrolling pane; they reuse existing endpoints (session list, cancel) and existing
state, so they are additive.

**Independent Test**: List/open sessions from the sidebar; start an in-flight run and Stop
it (existing cancel endpoint); force a disconnect and see the error banner; scroll up during
streaming and use jump-to-latest.

**Acceptance Scenarios**:

1. **Given** sessions exist, **When** the user views the sidebar, **Then** sessions are listed with recency and a new-chat affordance is available.
2. **Given** an in-flight run, **When** the user activates Stop, **Then** the run is cancelled via the existing cancel endpoint and status reflects it.
3. **Given** a connection or stream failure, **When** it occurs, **Then** a non-blocking error banner appears and the conversation already shown is preserved.
4. **Given** the user has scrolled up, **When** new content streams, **Then** a jump-to-latest affordance appears; **When** the user is at the bottom, **Then** the view auto-scrolls.

### User Story 4 - A polished sign-in (Priority: P4)

A signed-out user sees a styled, centered login card (a masked token field) consistent with
the themed UI; submitting a token loads the app.

**Why this priority**: The login is the first impression; styling it to match removes the
last unstyled surface. It is the smallest slice and depends on the theme work.

**Independent Test**: With no token, the centered themed login card is shown; submitting a
token loads the app; the token stays masked. The existing token-gate behavior is unchanged.

**Acceptance Scenarios**:

1. **Given** no stored token, **When** the app loads, **Then** a centered, themed login card with a masked token field is shown.
2. **Given** a submitted token, **When** it is accepted, **Then** the themed app loads; the existing sessionStorage / logout / 401-to-login behavior is unchanged.

### Edge Cases

- **Markdown content** (code blocks, tables, links) → rendered formatted and safely (no raw-HTML injection from model output).
- **A `tool-call-completed` with no matching `started`, or duplicate events** → handled without breaking the view (the existing forward-compatible reducer behavior is preserved).
- **A run that ends while a dialog is pending** → the pending approval/question is cleared/resolved.
- **Long replies / many tool calls** → the message area scrolls; the composer stays reachable (sticky).
- **Unknown event types** → ignored without crashing (existing forward-compatibility preserved).
- **Narrow viewport** → the two-pane shell stays usable (the sidebar collapses or stacks).
- **Theme storage blocked/unavailable** → falls back to a sensible default without error.
- **No sessions yet** → the sidebar shows a clear empty state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Assistant messages MUST render as **formatted markdown** (headings, lists, tables, code blocks, links), not raw text.
- **FR-002**: Each tool call MUST appear **inline in the conversation** as a **collapsible card** showing the tool name and a status that progresses from **running** to **success** or **failure**, derived from the existing tool-call started/completed events.
- **FR-003**: Consecutive tool calls SHOULD be **visually grouped** so a multi-tool turn stays readable, while each tool's individual status remains inspectable.
- **FR-004**: An approval request MUST be presented as a **styled in-flow dialog** offering **allow** and **deny**; it SHOULD also offer an **"always allow for this session"** choice using the existing approval-decision scope.
- **FR-005**: A question MUST be presented as a **styled in-flow dialog** that accepts a **free-text answer** (a single answer, matching the current event contract).
- **FR-006**: A run termination MUST be shown as a clear **terminal marker** (with its reason) in the conversation.
- **FR-007**: The UI MUST present a **two-pane app shell** — a sessions sidebar and a chat column with a **sticky header** and a **sticky composer**.
- **FR-008**: The sessions sidebar MUST **list existing sessions** (with recency) and offer **starting a new chat**.
- **FR-009**: The header MUST show **connection/run status** (e.g., idle, running, terminated, error) and MUST offer a **Stop** control that **cancels an in-flight run** via the existing cancel endpoint.
- **FR-010**: A connection or stream failure MUST surface as a **non-blocking error banner** (preserving the existing disconnected behavior) without discarding the conversation already shown.
- **FR-011**: The message area MUST **auto-scroll** to the latest content when the user is at the bottom and MUST offer a **jump-to-latest** affordance when the user has scrolled up.
- **FR-012**: The composer MUST be a **sticky input** that grows with multi-line content and **disables sending while a run is in flight**.
- **FR-013**: The UI MUST support a **light and a dark theme**, let the user **toggle** between them, **remember** the choice, and **default to the system preference** when no choice is stored.
- **FR-014**: The login screen MUST be a **styled, centered card** with a **masked token field**, consistent with the themed UI; the existing token-gate behavior (sessionStorage, logout, 401-to-login) is **unchanged**.
- **FR-015**: The overhaul MUST be **frontend-only** — no change to the web/API host, its event/endpoint contract, or the Python package; the existing `apps/web` toolchain and its isolated CI gate are reused and MUST stay green.
- **FR-016**: The UI MUST preserve **forward-compatibility** with the event stream — unknown event types are ignored without breaking rendering.
- **FR-017**: **No committed artifact** may contain a private path, internal name, IP, key, token, or secret, and **no private or legacy UI may be copied** — the design is written fresh.

### Key Entities

- **Conversation entry**: an ordered item in the chat flow — a user message, an assistant (markdown) message, a tool call (with status), or a run-termination marker — derived from the existing event stream.
- **Tool call card**: the inline representation of one tool invocation — tool name plus a running/success/failure status, collapsible to reveal detail.
- **Decision dialog**: the in-flow human prompt — an approval (allow / deny / always-allow-for-session) or a question (free-text answer).
- **Theme preference**: the remembered light/dark selection, with a system-default fallback.
- **Session summary**: a sidebar list entry — identifier and recency.

### Out of Scope

The following need **new backend events or endpoints** and are deferred to a **follow-up
backlog (the next unit)**; they are recorded here so the scope is explicit:

- **Thinking / reasoning display** — no such event exists in the stream today.
- **Model selection / switching** — no model catalog or per-session model selection exists.
- **File upload / attachments** — no upload endpoint exists.
- **Multi-option questions** (single/multi-select) — the question event carries only prompt text today.
- **Cost / token-usage panels** — no cost endpoint exists.
- **Skills / MCP / memory side panels** — no corresponding endpoints exist.
- **Transport change** — the existing REST + SSE transport is reused; no move to WebSockets.
- **Any backend change** — the web/API host, its events/endpoints, and the Python package are unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in user who sends a prompt sees the assistant reply rendered as **formatted markdown** and **each tool call as an inline status card** — not raw text or a flat list.
- **SC-002**: An **approval** and a **question** each appear as a **styled in-flow dialog** the user can act on, and a **run end** shows a clear **terminal marker**.
- **SC-003**: The user can switch between a **light and a dark theme** and the choice **persists across reloads**.
- **SC-004**: The user can **see run/connection status**, **cancel** an in-flight run, and **return to the latest message** after scrolling up.
- **SC-005**: The `apps/web` gate (**type check + component tests + build**) is **green**, and the **Python suite and the backend event/endpoint contract are unchanged**.
- **SC-006**: **No committed artifact** contains a private path, internal name, IP, key, token, or secret (a **clean scan**), and **no private or legacy UI is copied**.

## Assumptions

- **Reuse, not rewrite**: the unit-018 SPA — its API client, event parser, and chat reducer — and the unit-011 REST + SSE contract are reused; only presentation and the view-model shaping (ordering entries so tool cards interleave with messages) change.
- **Existing toolchain**: the `apps/web` frontend toolchain and its isolated CI gate are reused; styling and markdown rendering are added **within** that toolchain — the specific libraries are a **planning decision**, kept out of the requirements (behavior-level).
- **Existing capabilities only**: the overhaul maps onto events and endpoints that **already exist** (assistant increments, tool started/completed, approval, question, termination, session list/open, cancel, history); **no new backend capability is assumed**.
- **Frontend-only, additive, reversible**: removing the new styling/components restores the unstyled-but-functional app; the backend and the Python suite are unaffected (Constitution X rollback).
- **Fresh design**: a modern Claude-style aesthetic is the visual target; the implementation is **written fresh** with **no private or legacy UI copied** (Constitution VII).
