# Feature Specification: LoopPlane Desktop / Studio Host

**Feature Branch**: `012-loopplane-desktop-or-studio-host`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Expose LoopPlane through a LOCAL desktop/studio host on top of the
completed Host Application Interface (002): a local session manager, a developer console (command →
public-safe metadata-only view model), and a sidecar host contract (an abstraction for running the
host as a local sidecar, with an in-process implementation). It is an ADDITIVE host layer — it embeds
the public host, drives no runtime internals, executes no tool itself, and re-emits no live event
bus; it consumes the normalized event stream as a host consumer (Constitution V & VI). No GUI / UI
shell, no network (that is unit 011), no real process spawning, and no private legacy UI copy — those
are reserved extension points. Public-safe, metadata-only, deterministic, offline, in-process
testable, English."

## User Scenarios & Testing *(mandatory)*

The desktop/studio host turns the embedded Host Application Interface (unit 002) into a **local
developer experience**: a developer drives runs and interactive sessions from a console, manages local
sessions, inspects them, and embeds the host as a local sidecar — all in-process, offline, and
metadata-only. The "console" is a **command-and-view-model core** (a real terminal or UI shell would
render it); this unit ships the core, not a GUI. Every story is a thin, public-safe seam over the
**public** host surface.

### User Story 1 - Run a prompt from the local console (Priority: P1)

A developer issues a "run" command with a prompt; the console drives one run on the embedded host and
returns a public-safe, metadata-only **result view** — the terminal reason, the turns taken, and a
history-metadata summary — with no runtime internals touched. This is the minimum viable product: a
local, scriptable way to drive a LoopPlane run.

**Why this priority**: Driving a run locally is the reason this layer exists; the session manager,
interactivity, inspection, and sidecar all decorate it.

**Independent Test**: Build a console over a fake-model host, issue a run command, and assert the
returned result view carries the expected terminal reason, turn count, and metadata-only history.

**Acceptance Scenarios**:

1. **Given** a console over an embedded host, **When** the developer runs a prompt, **Then** exactly
   one run executes through the public host surface and a public-safe result view is returned.
2. **Given** a run is already active, **When** a second run command arrives, **Then** the console
   returns an explicit, public-safe conflict result rather than corrupting state or hanging.
3. **Given** a malformed or empty command, **When** it is processed, **Then** the console returns an
   explicit, public-safe error view with no stack trace, path, or internal name.

---

### User Story 2 - Manage local sessions (Priority: P2)

A developer opens a session, lists known sessions, selects an active one, and closes it. The local
**session manager** tracks sessions over the embedded host and keeps them addressable by their public
session id.

**Why this priority**: Local session management is what makes a studio more than a one-shot runner; it
builds directly on US1.

**Independent Test**: Open a session, list sessions (the new one appears), select it, close it, and
assert the manager's state transitions are correct and addressed by public id only.

**Acceptance Scenarios**:

1. **Given** a console, **When** the developer opens a session, **Then** it is tracked and addressable
   by its public session id.
2. **Given** one or more sessions, **When** the developer lists them, **Then** public-safe summaries
   are returned; selecting an unknown id yields an explicit not-found result.
3. **Given** an open session, **When** the developer closes it, **Then** it is closed and frees the
   embedded host (which is sequential per instance); closing an unknown id is an explicit no-op.

---

### User Story 3 - Conduct an interactive session from the console (Priority: P3)

A developer submits input to the active session, answers a pending approval request and a pending
question, and cancels — all in-process (no network), the console mediating the embedded session
round-trip and surfacing approval/question requests as console view models.

**Why this priority**: Interactivity (approvals, questions, multi-turn submit) is the human-in-the-loop
capability that separates a studio from a fire-and-forget runner. Because it is in-process, it is
exercised directly (unlike a network transport).

**Independent Test**: Open a session, submit input that triggers an approval, answer it, and assert the
session reaches the expected outcome — in-process, deterministically.

**Acceptance Scenarios**:

1. **Given** an open session, **When** the developer submits input, **Then** the console drives the
   embedded session and returns the resulting public-safe outcome view.
2. **Given** a session parked on a pending approval or question, **When** the developer answers it by
   request id, **Then** the embedded session resolves and the run proceeds; an unknown id yields an
   explicit negative result, never a crash.
3. **Given** an open session, **When** the developer cancels it, **Then** it is cancelled and never
   hangs on a pending approval or question.

---

### User Story 4 - Inspect a session locally (Priority: P4)

A developer renders metadata-only **views** of a session — its outcome, a history-metadata view, and
the sessions list — for the console / UI shell to display. All read-only, metadata-only.

**Why this priority**: After-the-fact inspection rounds out the studio but is not required to drive a
run; it is strictly additive to US1–US3.

**Independent Test**: After a run, request the outcome view, the history-metadata view, and the
sessions list, and assert each returns public-safe metadata, with unknown ids returning an explicit
not-found.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** the developer requests its outcome view, **Then** a
   public-safe, metadata-only view is returned.
2. **Given** a session, **When** the developer requests its history-metadata view, **Then** roles and
   counts are returned — never the conversation content; an unknown session yields a not-found result.
3. **Given** known sessions, **When** the developer lists them, **Then** public-safe summaries are
   returned.

---

### User Story 5 - Embed the host as a local sidecar (Priority: P5)

A developer runs/embeds the host as a local **sidecar** via an abstraction with a start/stop lifecycle;
the console drives the host through the sidecar contract. An in-process sidecar implementation ships;
spawning a real OS process is a reserved extension point.

**Why this priority**: The sidecar contract is the seam a future real desktop app uses to host the
runtime out-of-line; it is the most infrastructural and least user-facing story, so it is specified
last while remaining in scope.

**Independent Test**: Start an in-process sidecar, drive a run through it, and stop it; assert the
lifecycle is clean (idempotent stop, no orphaned run) and the console reaches the host only through the
contract.

**Acceptance Scenarios**:

1. **Given** the sidecar contract, **When** the in-process sidecar is started, **Then** the console can
   drive runs through it.
2. **Given** a started sidecar, **When** it is stopped, **Then** the lifecycle is clean and stopping
   again is an explicit no-op (idempotent); no run is orphaned.
3. **Given** a stopped sidecar, **When** a command arrives, **Then** an explicit, public-safe
   not-available result is returned rather than a crash.

---

### Edge Cases

- **Concurrent run**: a run command while a run is active → an explicit, public-safe conflict result
  (the embedded host is sequential per instance); no corruption, no hang.
- **Unknown ids**: selecting / closing / inspecting / answering for an unknown session or request id →
  an explicit not-found / negative result, never a crash.
- **Malformed command**: an unparseable or incomplete command → an explicit public-safe error view; no
  stack trace, path, internal name, or secret.
- **Raising injected callable**: a raising approval handler or event consumer is contained — the
  console records and stays up (fail-safe posture inherited from unit 002).
- **Stopped sidecar**: a command to a stopped sidecar → an explicit not-available result.

## Requirements *(mandatory)*

### Functional Requirements

**Run from the console (US1)**

- **FR-001**: The console MUST accept a run command carrying a prompt and drive a single run on the
  embedded host, returning a public-safe metadata-only result view (terminal reason, turns taken,
  history-metadata summary).
- **FR-002**: The console MUST drive runs only through the public Host Application Interface and MUST
  NOT reach runtime internals, execute a tool itself, or re-implement the loop.
- **FR-003**: While a run is active, a second concurrent run command MUST return an explicit,
  public-safe conflict result rather than corrupting state or blocking indefinitely.

**Session manager (US2)**

- **FR-010**: The session manager MUST open sessions over the embedded host, track them by their
  public session id, and list public-safe summaries.
- **FR-011**: The session manager MUST select an active session by id (unknown id → an explicit
  not-found result) and close a session (freeing the sequential host; closing an unknown id → an
  explicit no-op).

**Interactive session (US3)**

- **FR-020**: The console MUST submit input to the active session and return the resulting public-safe
  outcome view.
- **FR-021**: The console MUST answer a pending approval and a pending question for a session, mapping
  to the embedded session's answer operations; an unknown or stale request id MUST yield an explicit
  negative result, never a crash.
- **FR-022**: The console MUST cancel a session such that a cancelled session never hangs on a pending
  approval or question.

**Inspection (US4)**

- **FR-030**: The console MUST render metadata-only views of a session — its outcome, a
  history-metadata view (roles + counts, never conversation content), and the sessions list; an
  unknown session id MUST yield an explicit not-found result.

**Sidecar host contract (US5)**

- **FR-040**: The layer MUST define a sidecar host contract with a start/stop lifecycle and ship an
  in-process implementation; the console MUST reach the host only through the contract.
- **FR-041**: Stopping the sidecar MUST be idempotent and leave no orphaned run; a command to a stopped
  sidecar MUST return an explicit, public-safe not-available result.

**Error handling (cross-cutting)**

- **FR-050**: A malformed or invalid command MUST yield an explicit, public-safe error view; the layer
  MUST NOT surface stack traces, file system paths, internal type names, or secrets in any view.
- **FR-051**: The layer MUST originate no network egress and spawn no OS process of its own; it embeds
  a local host.

### Non-Functional Requirements

- **NFR-001 (Boundary)**: The layer MUST compose only the public `loopplane.host` surface; it MUST NOT
  import the controller, gateway, runtime internals, or a sibling layer. An import-boundary audit MUST
  enforce this (0 violations).
- **NFR-002 (Constitution V — Tool Gateway Ownership)**: The layer MUST execute no tool itself; tool
  execution remains the gateway's, reached only through the embedded host.
- **NFR-003 (Constitution VI — Runtime Event Bus Ownership)**: When the layer observes events it MUST
  consume the normalized stream as a host consumer and MUST NOT re-emit, wrap, or compete with the
  live event bus.
- **NFR-004 (Determinism)**: A console command's mapping to a view model MUST be a pure function of the
  command and the host's outputs; the same command sequence over the same scripted host yields the
  same views every run.
- **NFR-005 (Fail-safe)**: Empty / malformed input MUST map to an explicit safe view; a raising
  consumer or handler MUST never crash the console; unknown ids MUST yield explicit negative results.
- **NFR-006 (Public-safe / offline)**: All views and artifacts MUST be English and public-safe (no
  secrets, private paths, internal names, or IPs), metadata-only, and produced offline (no network, no
  process spawn); tests run in-process.
- **NFR-007 (Testability)**: The console, session manager, and in-process sidecar MUST be exercised by
  in-process tests over a scripted fake-model host — no GUI, no network, no real process.

### Key Entities *(include if feature involves data)*

- **Console command**: a public-safe, structured request (run a prompt, open/list/select/close a
  session, submit, answer approval/question, cancel, inspect). Metadata-only.
- **View model**: a public-safe, metadata-only result the console returns for a UI shell to render — a
  run result view, a session summary, a history-metadata view, an outcome view, or an error view.
- **Session manager state**: the set of locally-tracked sessions, addressed by public session id;
  carries id + lifecycle state, never internal handles.
- **Sidecar host**: the start/stop lifecycle contract over an embedded host, with an in-process
  implementation; never spawns a real process this phase.
- **Error / conflict view**: an explicit, public-safe envelope describing a client error, conflict,
  not-found, or not-available without internal detail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can drive a run from the console and receive a public-safe outcome view
  entirely in-process, with zero direct references to runtime internals.
- **SC-002**: Given the same command sequence over the same scripted host, the console returns
  identical views on every run (deterministic).
- **SC-003**: Across the full test corpus, 0 views leak a secret, private path, internal type name, IP,
  or stack trace; history views carry no conversation content.
- **SC-004**: 100% of unknown-id / malformed / stopped-sidecar commands return an explicit, public-safe
  negative result — never a crash or hang.
- **SC-005**: An import-boundary audit confirms the layer composes only the public `loopplane.host`
  surface with 0 violations, executes no tool, and re-emits no live bus event.
- **SC-006**: A cancelled session and an idempotent sidecar stop never hang or orphan a run (100% of
  such cases).

## Assumptions

- "Desktop / studio host" is scoped to the **local developer-console core**: a command → metadata-only
  view-model layer plus a local session manager and an in-process sidecar contract. A real **GUI / UI
  shell**, **OS process spawning** for the sidecar, **network** exposure (that is unit 011), and any
  **persistent studio state** are reserved extension points, named but not built. The specification is
  framework-agnostic; no GUI or console framework is in scope.
- The console drives the interactive session **in-process** (no network transport), so the approval /
  question round-trip is exercised directly, unlike a remote transport.
- The host preserves its sequential-run-per-instance guarantee; concurrent multi-run execution and
  multi-host pools are out of scope this phase.
- The unit depends on unit 002 (Host Application Interface) for the embedded host surface; it adds no
  new public contract to it and copies no private legacy UI.
- This unit ships the console core, the session manager, the in-process sidecar, in-process tests, a
  public-safe example, and a docs guide only.

### Reserved extension points (named, not built)

- A real GUI / desktop UI shell / studio frontend.
- OS process spawning for the sidecar (a real out-of-line host process) and inter-process transport.
- Network exposure of the studio (that is unit 011 — the web/API host).
- Persistent studio / workspace state, layouts, and developer preferences.
- Multi-host pools / concurrent multi-run orchestration.
- Any copy of a private or legacy UI.
