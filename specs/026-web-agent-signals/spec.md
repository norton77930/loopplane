# Feature Specification: Web Agent Signals

**Feature Branch**: `026-web-agent-signals` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Surface the agent signals that the backend already emits but the web UI ignores — frontend-only, building on the unit-025 overhaul. Three signals: (1) reasoning/thinking display — the runtime already streams reasoning increments (the Anthropic adapter maps thinking deltas), so render them as a distinct, de-emphasized, collapsible thinking block separate from the final answer; (2) multi-option questions — the question payload already carries an options list, so render options as selectable choices and submit the selection, falling back to the existing free-text field when there are none; (3) token usage — each completed turn already reports token usage (input/output/cached/reasoning), so show a per-turn indicator and a session total. No backend change: these consume events/fields the backend already produces over the existing stream. Out of scope (later units, some needing an ADR): cost/pricing estimation, streaming reasoning for providers that do not emit it, model selection/switching, file upload, and skills/MCP/memory inspection panels."

## Overview

The unit-025 overhaul restyled the web frontend (`apps/web`) into a professional agent UI,
but it only renders the **subset** of the event stream the unit-018 app already modeled:
assistant text, tool calls, approvals, plain-text questions, and run termination. A backend
capability audit found that the runtime **already produces three richer signals** that the
frontend simply **does not yet consume**:

1. **Reasoning / thinking** — the runtime emits **reasoning increments** as a first-class
   event (the Anthropic model adapter maps streamed thinking deltas into them), and the
   web/API host forwards them over the existing stream. The UI currently ignores them.
2. **Question options** — the question payload **already carries an options list**; the UI
   currently renders only a free-text answer field.
3. **Token usage** — each **completed turn already reports token usage** (input / output /
   cached / reasoning); the UI currently shows none of it.

This unit is a **frontend-only** extension that surfaces those three signals, **building on
the unit-025 UI**: a distinct, de-emphasized, collapsible **thinking block** streamed
separately from the answer; **selectable option choices** in the question dialog (with the
free-text field as the fallback); and a **token-usage indicator** per turn plus a session
total. It changes **only the frontend** — it consumes events/fields the backend **already
emits**, so the web/API host, its event/endpoint contract, and the Python package are
**untouched**, and the `apps/web` toolchain and its isolated CI gate are reused. Each signal
**degrades gracefully** when its data is absent (a model that emits no reasoning, a question
with no options, a turn with no usage). The design is **written fresh** — **no private or
legacy UI is copied** (Constitution VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the agent's reasoning (Priority: P1)

A signed-in user sends a prompt to a model that produces reasoning; the UI shows that
reasoning as a **distinct, de-emphasized thinking block** in the conversation — streamed as
it arrives, visually separate from the final answer, and **collapsible** — so the user can
follow the agent's chain of thought.

**Why this priority**: A visible reasoning trail is one of the most "agent-like" signals, and
the backend **already emits it** — the highest value for the lowest cost (frontend-only).

**Independent Test**: With a backend/model that emits reasoning increments, send a prompt — a
thinking block streams and renders distinctly from the answer and can be collapsed; with a
model that emits none, no thinking block appears (graceful).

**Acceptance Scenarios**:

1. **Given** reasoning increments stream for a turn, **When** they arrive, **Then** a distinct, de-emphasized thinking block renders separately from the final assistant message and updates as it streams.
2. **Given** a rendered thinking block, **When** the user collapses it, **Then** it hides without affecting the final answer.
3. **Given** a turn that produces no reasoning, **When** it renders, **Then** no thinking block appears.

### User Story 2 - Answer a question with options (Priority: P2)

When the agent asks a question that carries options, the dialog presents those options as
**selectable choices** and submits the selection as the answer; when the question carries no
options, the dialog falls back to the **free-text field** (the unit-025 behavior).

**Why this priority**: It completes the question UX from unit 025, and the backend **already
carries options** in the payload — a small, self-contained frontend change.

**Independent Test**: A question event with options renders selectable choices and selecting
one submits that answer; a question with no options renders the free-text field unchanged.

**Acceptance Scenarios**:

1. **Given** a question that carries options, **When** it renders, **Then** each option is a selectable choice and choosing one submits it as the answer.
2. **Given** a question that allows multiple selections, **When** it renders, **Then** more than one option can be selected and submitted together.
3. **Given** a question with no options, **When** it renders, **Then** the existing free-text answer field is shown.

### User Story 3 - See token usage (Priority: P3)

After a turn completes, the UI surfaces the **token usage** the backend already reports
(input / output, plus cached / reasoning when present) as a compact **per-turn indicator**,
and keeps a **session-level running total**, so the user sees the run's token footprint.

**Why this priority**: Usage transparency is valuable and the backend **already reports it**
per completed turn; it is additive and self-contained.

**Independent Test**: Complete a turn — its token usage is shown; across turns — a session
total accrues; a turn with no usage data shows no indicator (graceful).

**Acceptance Scenarios**:

1. **Given** a turn completes with usage data, **When** it arrives, **Then** the UI shows the turn's token usage (at least input/output; cached/reasoning when present).
2. **Given** multiple completed turns, **When** they accrue, **Then** a session-level token total is available.
3. **Given** a turn with no usage data, **When** it renders, **Then** no usage indicator is shown.

### Edge Cases

- **A provider that does not stream reasoning** → no thinking block appears (graceful); a reasoning-token count may still surface via usage.
- **Reasoning interleaved with the answer** → the thinking block stays visually separate and correctly ordered within the turn.
- **A question payload with an empty options list** → the free-text fallback is used.
- **Partial usage fields** (e.g., no cached/reasoning tokens) → only the present fields are shown.
- **Very large reasoning output** → the thinking block scrolls/collapses and does not overwhelm the conversation.
- **Unknown event types or extra fields** → ignored without breaking rendering (forward-compatibility preserved).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the backend streams reasoning/thinking increments for a turn, the UI MUST render them as a **distinct, de-emphasized thinking block** in the conversation, updated as it streams and **visually separate** from the final assistant answer.
- **FR-002**: The thinking block MUST be **collapsible** and MUST **not appear** when a turn produces no reasoning.
- **FR-003**: When a question carries **options**, the UI MUST present them as **selectable choices** and submit the selection as the answer.
- **FR-004**: When a question indicates that **multiple selections** are allowed, the UI MUST allow selecting and submitting more than one option.
- **FR-005**: When a question carries **no options**, the UI MUST fall back to the existing **free-text** answer field (the unit-025 behavior).
- **FR-006**: After a turn completes, the UI MUST surface the **token usage** the backend reports (input / output, plus cached / reasoning when present) as a **per-turn** indicator.
- **FR-007**: The UI MUST provide a **session-level token-usage total** across completed turns.
- **FR-008**: Each signal MUST **degrade gracefully** when its data is absent — no thinking block, no option choices, no usage indicator — without errors or empty placeholders.
- **FR-009**: This unit MUST be **frontend-only** — it consumes events/fields the backend **already emits**; **no change** to the web/API host, its event/endpoint contract, or the Python package; the existing `apps/web` toolchain and its isolated CI gate are reused and MUST stay green.
- **FR-010**: The UI MUST preserve **forward-compatibility** — unknown event types or extra fields are ignored without breaking rendering.
- **FR-011**: **No committed artifact** may contain a private path, internal name, IP, key, token, or secret, and **no private or legacy UI may be copied** — the design is written fresh.

### Key Entities

- **Thinking block**: the de-emphasized, collapsible, streamed reasoning view for a turn, rendered distinctly from the final answer.
- **Option choice**: a selectable answer rendered from a question's options (single- or multi-select), with a free-text fallback when there are none.
- **Usage indicator**: the per-turn and session-total token-usage display (input / output / cached / reasoning, as available).

### Out of Scope

Deferred to later units (some require an ADR before they can proceed):

- **Cost / pricing estimation** — turning token counts into a monetary estimate needs a backend pricing lookup; this unit shows **counts only**.
- **Streaming reasoning for providers that do not emit it** — e.g., enhancing a model adapter to stream reasoning deltas is a **backend** change.
- **Model selection / switching** — needs runtime + host-interface changes and a constitution ADR (Principle III / VIII).
- **File upload / attachments** — needs a content-model + storage + endpoint change and a constitution ADR (Principle IV).
- **Skills / MCP / memory inspection panels** — needs new additive web/API inspection endpoints (a separate unit).
- **Any backend change** — the web/API host, its events/endpoints, and the Python package are unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a model that emits reasoning, a user sees a **distinct, streamed, collapsible thinking block** separate from the answer; with a model that does not, **none appears**.
- **SC-002**: A question **with options** is answerable by selecting a choice; a question **without options** still uses the free-text field.
- **SC-003**: The user sees **per-turn token usage** and a **session total**.
- **SC-004**: All three signals **degrade gracefully** when their data is absent.
- **SC-005**: The `apps/web` gate (**type check + component tests + build**) is **green**, and the **Python suite and the backend event/endpoint contract are unchanged**.
- **SC-006**: **No committed artifact** contains a private path, internal name, IP, key, token, or secret (a **clean scan**), and **no private or legacy UI is copied**.

## Assumptions

- **Builds on unit 025**: this unit reuses the unit-025 conversation flow, dialogs, and styling, and extends the frontend to **model and render** the additional signals; it is sequenced after 025.
- **Existing events/fields**: reasoning increments, question options, and per-turn token usage are **already produced** by the backend and forwarded over the existing stream; only the frontend is extended to consume them (confirmed by a backend capability audit).
- **Provider-dependent reasoning**: a thinking display depends on the model **surfacing** reasoning (available today via the Anthropic adapter); a provider that does not stream reasoning simply shows **no thinking block** — **no backend change** is made here.
- **Frontend-only, additive, reversible**: removing the new rendering restores the unit-025 app; the backend and the Python suite are unaffected (Constitution X rollback).
- **Fresh design**: the implementation is **written fresh** with **no private or legacy UI copied** (Constitution VII).
