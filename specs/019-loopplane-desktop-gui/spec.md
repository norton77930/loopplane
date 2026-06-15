# Feature Specification: LoopPlane Desktop GUI

**Feature Branch**: `019-loopplane-desktop-gui` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "LoopPlane desktop GUI (roadmap unit 019): a local desktop application (Electron) over the 012 studio sidecar contract — a packaged shell embedding the 018 web frontend, driving an in-process/sidecar host with no server. No private legacy UI copy; reuses 018; packaging + launch only, runtime unchanged."

## Overview

LoopPlane has a web UI (unit 018) that runs against a web/API host over HTTP. This
unit adds a **local desktop application**: a window the user launches that runs the
agent with **no server** — it starts a **local sidecar host** (the runtime spoken to
over a local process bridge) and **reuses the unit-018 UI** as its renderer. The
result is a native-feeling desktop app to chat with the agent, watch runs, answer
approvals and questions, and browse sessions, entirely on the user's machine. The
desktop toolchain is isolated under `apps/`; the runtime is unchanged; and packaging
a distributable, signed installer is a reserved, maintainer-initiated step — this
unit ships the shell, its launch/host wiring, and its tests.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch the desktop app and chat (Priority: P1)

A user opens the LoopPlane desktop app; it starts a local host and presents the chat
UI; the user types a prompt and watches the agent respond — all locally, no server.

**Why this priority**: Launching into a working chat is the whole point of a desktop
app and exercises the full path (launch → sidecar host → UI → streamed response).

**Independent Test**: Drive the sidecar host with the scripted model over the bridge
and confirm a submitted prompt produces a streamed response delivered to the renderer.

**Acceptance Scenarios**:

1. **Given** the desktop app launched with a local sidecar host, **When** the user submits a prompt, **Then** the agent's streamed response is delivered to and rendered by the UI.
2. **Given** the app, **When** it closes, **Then** the local host shuts down cleanly.

### User Story 2 - The sidecar bridge (no server) (Priority: P1)

The renderer talks to the local host over a **sidecar transport** (a local process
bridge), not an HTTP server, streaming the normalized event stream.

**Why this priority**: The serverless local bridge is what distinguishes the desktop
app from the web host; it is the foundation the UI runs on.

**Independent Test**: Send a run request across the bridge and confirm the normalized
events come back in order, with no network listener opened.

**Acceptance Scenarios**:

1. **Given** the sidecar host, **When** a prompt is sent over the bridge, **Then** the normalized events are streamed back over the bridge in order.
2. **Given** the sidecar host, **When** it runs, **Then** it opens no network server/port.

### User Story 3 - Reuse the web UI (Priority: P2)

The desktop renderer reuses the unit-018 conversation, timeline, and prompts — there
is no second UI and no legacy UI is copied.

**Why this priority**: Reuse keeps one UI to maintain and honors the no-copy rule.

**Independent Test**: Confirm the desktop renderer renders a streamed run using the
unit-018 view model (the same reducer/components), driven by the sidecar transport.

**Acceptance Scenarios**:

1. **Given** the desktop renderer, **When** it renders a run, **Then** it uses the unit-018 view model (the same conversation/timeline), differing only in the transport (sidecar instead of HTTP).

### User Story 4 - Approvals and questions in the desktop (Priority: P2)

When the agent requests approval or asks a question, the desktop UI surfaces it and
the user's response is delivered back over the sidecar bridge.

**Why this priority**: The interactive round-trip makes guarded actions usable in the
desktop, over the same bridge.

**Independent Test**: Drive a run that requests an approval/question over the bridge;
confirm the UI surfaces it and the response is delivered to the host.

**Acceptance Scenarios**:

1. **Given** a run requesting approval, **When** the user allows or denies in the UI, **Then** the decision is delivered to the host over the bridge and the run proceeds.

### User Story 5 - A safe, local, packaged shell (Priority: P3)

An operator wants the desktop app to leak no secret, to run no tool itself, to launch
and shut down cleanly, and to keep its toolchain isolated.

**Why this priority**: Public-safety, boundary integrity, and a clean local lifecycle.

**Independent Test**: Inspect the app's sources and the sidecar: confirm no secret is
embedded, the renderer runs no tool (the host does), and launch/shutdown are clean.

**Acceptance Scenarios**:

1. **Given** the app's sources, **When** inspected, **Then** they contain no secret or credential.
2. **Given** a run, **When** the agent uses a tool, **Then** the tool runs in the host (behind the gateway), and the renderer only displays the normalized events.

### Edge Cases

- **Sidecar fails to start / exits** → a clear error state in the window, not a crash.
- **The bridge drops mid-run** → the UI shows a clear disconnected state.
- **App closes during a run** → the host cancels and shuts down cleanly, no orphan process.
- **A run fails** → the failure renders as a normalized outcome, not a stack trace.
- **No model configured** → the credential-free scripted/demo model runs locally.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST launch a desktop window and start a **local sidecar host** — the runtime spoken to over a local process bridge — with **no network server/port**.
- **FR-002**: The renderer MUST send prompts and receive the **normalized event stream** over the sidecar bridge, rendering the run incrementally.
- **FR-003**: The renderer MUST **reuse the unit-018 UI** (the same view model / components) — no second UI is written and **no legacy UI is copied** (Constitution VII).
- **FR-004**: The app MUST support the interactive round-trip — approval requests and questions are surfaced and the user's response is delivered to the host over the bridge.
- **FR-005**: The app MUST be credential-free by default — a local scripted/demo model runs with no credential and no network.
- **FR-006**: The renderer MUST execute **no tool** itself and the app MUST drive no runtime internal — tools run in the host behind the gateway, and the renderer consumes the normalized event stream (Constitution V & VI).
- **FR-007**: The app's sources MUST be public-safe — no secret, credential, private path, or raw exception in the app or its rendered output.
- **FR-008**: The app MUST launch and shut down cleanly — closing the window cancels the run and stops the local host with no orphan process; a sidecar that fails to start renders a clear error state, not a crash.
- **FR-009**: The desktop toolchain MUST be isolated under `apps/` with its own build and test gate, and MUST NOT change the Python package, the web API, the unit-018 app's contract, or the runtime.
- **FR-010**: The sidecar bridge and the renderer transport MUST be covered by automated tests (the Python sidecar in the Python gate; the renderer transport in the JS gate); the Electron shell's launch wiring is typechecked and verified by a manual smoke (packaging an installer is out of scope).

### Key Entities

- **Sidecar host**: the local process that runs the runtime over a bridge, exposing the same run/session/event operations the web host does, but over a local transport with no server.
- **Bridge transport**: the local message channel (process stdio / IPC) carrying prompts, responses, the event stream, and approval/question answers.
- **Desktop renderer**: the unit-018 UI wired to the bridge transport instead of HTTP.
- **Shell**: the desktop window/process that launches the sidecar, hosts the renderer, and manages the lifecycle.

### Out of Scope

- Packaging a distributable or signed installer (electron-builder, code signing, auto-update) — a reserved, maintainer-initiated step.
- Any change to the Python package, the web API (unit 011), the unit-018 app, or the runtime; this unit composes them.
- A new UI: the desktop reuses unit 018.
- Multi-window, OS-native menus beyond a minimal shell, and mobile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A prompt sent over the sidecar bridge produces the normalized event stream back in order, with no network server opened.
- **SC-002**: The desktop renderer renders a streamed run using the unit-018 view model over the bridge transport.
- **SC-003**: An approval/question is surfaced in the UI and the response is delivered to the host over the bridge.
- **SC-004**: The app's sources contain zero secret or credential, and the renderer runs no tool.
- **SC-005**: Closing the app cancels the run and stops the local host cleanly with no orphan process.
- **SC-006**: The Python sidecar and the renderer transport pass their respective test gates; the Python suite and the unit-018 JS gate stay green.

## Assumptions

- **Composes 018 + the host**: the desktop reuses the unit-018 renderer and drives the runtime through a local sidecar (the unit-012 studio sidecar contract), changing nothing in those units.
- **Serverless local**: the sidecar speaks a local process protocol (stdio / IPC), not HTTP — no port is opened.
- **Testable core, manual GUI smoke**: the Python sidecar bridge (Python gate) and the renderer transport (JS gate) are automated; the Electron shell's launch wiring is typechecked and smoke-tested manually, consistent with unit 001's manual real-model validation and the reserved packaging step.
- **Credential-free default**: the local scripted/demo model is the default, so the app runs offline and the gates are deterministic.
- **Reserved packaging**: shipping a signed, distributable installer is out of scope and reserved for a maintainer.
