# Feature Specification: LoopPlane Web Frontend

**Feature Branch**: `018-loopplane-web-frontend` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "LoopPlane web frontend (roadmap unit 018): a from-scratch single-page web UI over the 011 web/API host (REST + SSE) — chat/run view, event timeline, approvals/questions, session list. No private legacy UI copy; written fresh; the JS toolchain is isolated under apps/ with its own CI gate."

## Overview

LoopPlane has a web/API host (unit 011) that exposes runs over REST and a live
Server-Sent-Events stream of normalized events, behind an auth boundary. This unit
adds the **single-page web UI** that sits on top of it: a browser app that lets a
user chat with the agent, watch the run stream live, answer approvals and questions,
and browse sessions — talking **only to the public web API**, never to the runtime
directly. The UI is **written from scratch** (no legacy UI is copied), and its
JavaScript toolchain lives isolated under `apps/` with its own build and test gate,
separate from the Python package.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chat with the agent in the browser (Priority: P1)

A user opens the web app, types a prompt, and watches the agent's response stream
in live as it is produced.

**Why this priority**: A streamed browser chat is the smallest viable, highest-value
slice — it exercises the whole path (input → API call → live event stream → render).

**Independent Test**: With a stubbed web API that streams a scripted run, enter a
prompt and confirm the assistant's output renders incrementally and the input clears
for the next turn.

**Acceptance Scenarios**:

1. **Given** the app connected to the web API, **When** the user submits a prompt, **Then** the assistant's streamed output appears incrementally in the conversation.
2. **Given** a completed run, **When** it terminates, **Then** the conversation shows the finished turn and is ready for the next prompt.

### User Story 2 - See the run timeline (Priority: P1)

A user watches a structured timeline of the run — assistant turns, tool activity,
and the termination — built from the normalized event stream.

**Why this priority**: Observability of the run is core to the product's value and
reuses the same event stream as the chat.

**Independent Test**: Stream a run that uses a tool and confirm the timeline shows the
tool start/finish (name + outcome only) and the run's termination, in order.

**Acceptance Scenarios**:

1. **Given** a streaming run that uses a tool, **When** events arrive, **Then** the timeline shows the tool's name and outcome (metadata only) and the terminal outcome, in sequence.

### User Story 3 - Answer approvals and questions (Priority: P2)

When the agent requests approval for a tool call or asks the user a question, the UI
prompts the user and sends the answer back through the API.

**Why this priority**: The interactive round-trip is what makes the agent usable for
guarded actions; it builds on the same connection.

**Independent Test**: Stream a run that requests an approval and a question; confirm
the UI surfaces each, and submitting a decision/answer sends it to the API and the run
continues.

**Acceptance Scenarios**:

1. **Given** a run that requests approval, **When** the prompt appears and the user allows or denies, **Then** the decision is sent to the API and the run proceeds accordingly.
2. **Given** a run that asks a question, **When** the user answers, **Then** the answer is sent and the run continues.

### User Story 4 - Browse sessions (Priority: P2)

A user lists prior sessions and opens one to review its conversation.

**Why this priority**: Continuity and review; secondary to running the agent.

**Independent Test**: With a stubbed API returning a session list, confirm the UI lists
sessions (public-safe identity + recency) and opening one shows its conversation.

**Acceptance Scenarios**:

1. **Given** sessions exist, **When** the user opens the session list, **Then** each session's public-safe identity and recency are shown.
2. **Given** a listed session, **When** the user opens it, **Then** its conversation is shown.

### User Story 5 - A safe, resilient UI (Priority: P3)

An operator wants the UI to leak no secret, to handle the auth boundary, and to
degrade gracefully on errors.

**Why this priority**: Public-safety, security, and resilience.

**Independent Test**: Inspect the built client bundle and the running UI: confirm no
secret is embedded, authentication is carried per the API's boundary, and API errors
and lost connections render clear states rather than crashing.

**Acceptance Scenarios**:

1. **Given** the built app, **When** the bundle is inspected, **Then** it contains no secret or credential.
2. **Given** an API error or a dropped stream, **When** it occurs, **Then** the UI shows a clear error/reconnect state and does not crash.

### Edge Cases

- **API unreachable / stream drops** → a clear "disconnected" state with a retry, not a crash.
- **Unauthorized** → a clear sign-in/authorization prompt per the API's boundary, no secret exposed.
- **Empty prompt** → submission is prevented or no-ops.
- **A run that fails** → the failure renders as a normalized outcome in the timeline, not a stack trace.
- **No sessions** → an empty-state message.
- **Long output** → the conversation scrolls and stays responsive.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST be a single-page web application served as static assets, talking **only** to the public web API — it MUST NOT access the runtime directly.
- **FR-002**: The UI MUST submit a prompt and render the agent's response **incrementally** from the live event stream.
- **FR-003**: The UI MUST render a run timeline from the normalized event stream — assistant turns, tool activity (name + outcome only), and termination — in order.
- **FR-004**: The UI MUST surface approval requests and questions and send the user's decision/answer back through the API, after which the run continues.
- **FR-005**: The UI MUST list sessions (public-safe identity + recency) and open one to show its conversation.
- **FR-006**: The UI MUST carry authentication per the web API's auth boundary and MUST NOT embed any secret or credential in the client bundle.
- **FR-007**: The UI MUST render metadata-safe content only — it MUST NOT display raw tool input/output, secrets, private paths, or raw exceptions.
- **FR-008**: The UI MUST handle API errors and dropped streams with clear error/reconnect states and never crash the page.
- **FR-009**: The UI MUST be written from scratch — no legacy/private UI is copied (Constitution VII).
- **FR-010**: The UI's toolchain MUST be isolated under `apps/` with its own build and test gate, separate from the Python package, and MUST NOT change the Python package or any prior unit's contract.
- **FR-011**: The UI MUST build to static assets and its component behavior MUST be covered by automated tests that run in the JS test gate.

### Key Entities

- **Conversation view**: the chat transcript of user prompts and streamed assistant output.
- **Run timeline**: the ordered, metadata-only view of a run's normalized events.
- **Approval / question prompt**: an interactive request surfaced to the user with a response sent back to the API.
- **Session list**: the public-safe list of prior sessions and the selected session's conversation.
- **API client**: the single seam that talks to the web API (REST + event stream) and carries auth.

### Out of Scope

- The desktop GUI shell (unit 019), which reuses this UI.
- Server-side rendering, a public design system/component library beyond what the app needs, mobile-native apps, and internationalization.
- Any change to the Python package, the web API contract, or the runtime; this unit only **consumes** the existing web API.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can hold a live, streamed chat with the agent in the browser against the web API.
- **SC-002**: The timeline reflects a run's assistant turns, tool activity (metadata only), and termination, in order.
- **SC-003**: A user can answer an approval and a question from the UI and the run continues.
- **SC-004**: A user can list sessions and open one to review its conversation.
- **SC-005**: The built client bundle contains zero secret or credential, and 100% of rendered content is metadata-safe.
- **SC-006**: The app builds to static assets and 100% of its component tests pass in the JS test gate, with the Python suite unchanged.

## Assumptions

- **Consumes the existing API**: the UI talks only to the unit-011 web/API host (REST + the SSE event stream) and changes nothing server-side.
- **From scratch**: the UI is authored fresh from this spec; no legacy UI is copied (VII).
- **Isolated toolchain**: the JS app lives under `apps/` with its own package manifest, build, and test runner; the Python package, its build, and its CI gates are untouched, and a separate JS gate covers the app.
- **Metadata-only rendering**: the UI renders only the public-safe, metadata-only content the web API already exposes (assistant text, tool name + outcome, normalized termination, public-safe session identity).
- **Stubbed API in tests**: component tests run against a stubbed web API / event stream, so the JS test gate is deterministic and credential-free.
