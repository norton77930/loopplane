# Feature Specification: Web Parity Foundation

**Feature Branch**: `[074-web-parity-foundation]`

**Created**: 2026-06-29

**Status**: Draft

**Input**: User description: "Start the parity roadmap with web parity foundation: add the live web transport and session-management groundwork needed to align LoopPlane's web experience with modern agent app behavior, while preserving existing REST/SSE behavior and public contracts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resilient Live Chat Channel (Priority: P1)

A web user can keep a session open through a bidirectional live channel that carries assistant output, tool progress, approval prompts, user answers, aborts, and reconnect recovery without losing conversation state.

**Why this priority**: This is the foundation for web parity. Later capability-management and agent-control screens depend on a reliable live session mechanism that can carry both server events and user responses.

**Independent Test**: Start a web session, send a prompt, receive streamed assistant/tool events, answer an approval or question, abort an in-flight turn, simulate a transient disconnect, reconnect, and verify the conversation is replayed without duplicate or missing visible entries.

**Acceptance Scenarios**:

1. **Given** an authenticated web user with an active session, **When** the user sends a message through the live channel, **Then** the assistant output, reasoning, tool status, usage, approval prompts, and question prompts appear in the same order as the normalized session history.
2. **Given** a pending approval or user question, **When** the user responds through the live channel, **Then** the pending prompt clears and the session continues without requiring a page reload.
3. **Given** an in-flight turn, **When** the user requests abort, **Then** the run stops through the same session boundary used by existing cancellation flows and the UI shows a stable stopped or idle state.
4. **Given** a temporary connection loss, **When** the browser reconnects, **Then** the user sees the full current conversation state exactly once and can continue sending messages.

---

### User Story 2 - Agent-Style Session Management (Priority: P2)

A web user can manage sessions with modern agent-app affordances: create a draft chat before the first send, remember the preferred model choice, star important sessions, fork a session from a selected point, search prior sessions, and bulk-delete unwanted sessions safely.

**Why this priority**: Session operations are the main navigation and recovery workflow for a long-running agent UI. They can be delivered after the live channel while remaining independently useful.

**Independent Test**: Use only session-management controls to create a draft, commit it on first send, change and retain model preference, star and unstar sessions, fork a session, search by session content or title, bulk-delete selected sessions, and verify the active session selection stays predictable.

**Acceptance Scenarios**:

1. **Given** a user starts a new chat but has not sent a message, **When** they select a model and type the first prompt, **Then** the session is created only when the prompt is submitted and uses the selected model.
2. **Given** a user marks a session as starred, **When** the session list refreshes or the page reloads, **Then** the starred state remains visible and does not change session ownership.
3. **Given** a user forks a session, **When** the fork is created, **Then** the new session contains the selected conversation context and the original session remains unchanged.
4. **Given** a user searches sessions, **When** matches exist in title or retained conversation text, **Then** the matching sessions are shown with enough context for selection.
5. **Given** a user selects multiple sessions for deletion, **When** they confirm bulk delete, **Then** only owned selected sessions are removed and the UI selects a remaining session or a new-chat state.

---

### User Story 3 - Contract-Safe Type Alignment (Priority: P3)

A maintainer can verify that the web client's session event and API types match the backend contracts, and that the new parity transport does not break existing REST/SSE clients or the desktop shell.

**Why this priority**: The feature expands web-facing contracts. Type drift would create hidden frontend/backend mismatch and make later parity phases fragile.

**Independent Test**: Regenerate or validate the web-facing contract artifacts, run the existing REST/SSE flows, run the new live-channel flows, and confirm both client surfaces consume the same normalized session meanings.

**Acceptance Scenarios**:

1. **Given** the backend event and API contract definitions, **When** the web-facing type artifacts are refreshed or checked, **Then** the generated or validated client types match the current backend contract.
2. **Given** an existing client using current REST/SSE session endpoints, **When** this feature is enabled, **Then** the existing client workflow continues to pass unchanged.
3. **Given** the desktop shell depends on the existing web state model, **When** this feature is delivered, **Then** desktop behavior remains compatible until a later desktop parity unit intentionally changes it.

---

### Edge Cases

- Connection drops after the server accepts a user message but before the browser receives the first response frame.
- Reconnect history contains events already rendered by the browser.
- A pending approval or question is cancelled by run termination before the user answers.
- A user tries to fork, star, search, or bulk-delete sessions they do not own.
- Bulk delete includes the active session, all visible sessions, or sessions that were already removed in another tab.
- Draft-session model preference references a model that is no longer available.
- Generated or validated type artifacts detect an event field that the UI does not understand.
- Existing REST/SSE clients and desktop tests run while the new live channel is also available.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an additive bidirectional live session channel for authenticated web users that can send user messages and receive normalized session output without replacing the existing streaming endpoints.
- **FR-002**: The live channel MUST carry all user-visible session signals currently supported by the web UI, including assistant output, reasoning output, tool start/completion, usage updates, run termination, approval requests, and user questions.
- **FR-003**: Users MUST be able to answer approval requests and user questions through the live channel, and the system MUST correlate each answer to the correct pending request.
- **FR-004**: Users MUST be able to abort an in-flight turn through the live channel, and abort behavior MUST remain consistent with the existing cancel flow.
- **FR-005**: The live channel MUST support reconnect recovery by replaying current session state without duplicating events that were already accepted by the client.
- **FR-006**: The existing REST/SSE session creation, submit, event stream, history, approval, question, cancel, model, and upload flows MUST remain available and behavior-compatible.
- **FR-007**: The web client MUST isolate transport-specific behavior behind a transport boundary so chat state, rendering, approvals, questions, usage, and message actions can work over either supported transport.
- **FR-008**: Users MUST be able to start a draft chat without immediately creating a persisted session, and the system MUST create the session when the first message is submitted.
- **FR-009**: Users MUST be able to retain a preferred model choice for future draft chats while still allowing each committed session to show its actual selected model.
- **FR-010**: Users MUST be able to star and unstar owned sessions, and starred state MUST survive list refresh and page reload.
- **FR-011**: Users MUST be able to fork an owned session from a selected conversation point, and the original session MUST remain unchanged.
- **FR-012**: Users MUST be able to search owned sessions by title and retained conversation text.
- **FR-013**: Users MUST be able to bulk-delete owned sessions only after an explicit confirmation, and the active-session fallback MUST be deterministic after deletion.
- **FR-014**: Session operations MUST preserve principal scoping: non-owned sessions MUST NOT be visible, mutable, forkable, searchable, or deletable.
- **FR-015**: The project MUST include a repeatable way to refresh or validate web-facing API and session-event type artifacts against the backend contracts.
- **FR-016**: Type validation MUST fail clearly when a backend event or response field used by the web client drifts from the declared contract.
- **FR-017**: The feature MUST NOT introduce provider secret collection in the browser UI.
- **FR-018**: The feature MUST NOT copy implementation code, private paths, private names, credentials, tokens, or raw legacy/reference material from any reference repository.
- **FR-019**: The feature MUST include rollback guidance that allows disabling or reverting the new live channel while preserving the existing REST/SSE session behavior.

### Key Entities

- **Live Session Channel**: The authenticated browser-to-session communication path that sends user actions and receives normalized session updates.
- **Session Summary**: A list item representing an owned session with title, timestamps, model identity, star state, and fork relationship metadata.
- **Draft Chat**: A local pre-session state that stores the user's first prompt and preferred model until the session is committed.
- **Session Fork**: A new owned session derived from a selected point in an existing session without mutating the source.
- **Contract Type Artifact**: A generated or validated web-facing representation of backend API and session-event contracts.
- **Transport Boundary**: The web-client seam that hides live-channel versus existing streaming details from rendering and chat state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A web user can complete a live-channel chat turn, including one approval or question response, without page reload in 100% of automated acceptance scenarios.
- **SC-002**: After a simulated transient disconnect, the web UI restores the conversation with no duplicate visible entries and no missing accepted entries in 100% of reconnect tests.
- **SC-003**: Existing REST/SSE web session tests and existing desktop tests continue to pass unchanged after the new live channel is added.
- **SC-004**: Session management acceptance tests cover draft creation, preferred model retention, star/unstar, fork, search, and bulk delete with owner scoping.
- **SC-005**: Contract/type validation catches intentional drift in at least one representative API response and one representative session event fixture.
- **SC-006**: Public-safety scans over all changed files report no private paths, raw reference material, credentials, tokens, or secret-like values.

## Assumptions

- Existing authentication, principal ownership, checkpoint, event replay, model catalog, upload, approval, question, and cancellation boundaries are reused.
- Existing REST/SSE behavior remains the compatibility baseline and cannot be removed in this unit.
- Browser-side provider secret management is out of scope for this unit and remains deferred unless explicitly authorized later.
- Desktop cowork parity is out of scope for this unit except for compatibility preservation; it is planned for a later roadmap unit.
- Capability-management UI, plan mode UI, permission-mode UI, budget controls, projects/workspaces, schedules, and backup/restore are out of scope for this unit and are planned for later units.
- Claude Code and Orion are behavior references only; implementation is re-derived through LoopPlane specs and tests.
