# Feature Specification: LoopPlane CLI Host

**Feature Branch**: `017-loopplane-cli-host` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "LoopPlane interactive CLI host (roadmap unit 017, package loopplane.cli): a thin terminal host over the Host Application Interface (loopplane.host) — REPL/chat loop, run/session commands, normalized-event rendering, and an optional credential-gated real model provider behind an extra. Executes no tool itself and consumes the normalized event stream. Adds a console entry point; the runtime core is unchanged."

## Overview

LoopPlane is an embeddable library: to try it you must write a host program. This
unit adds a **terminal command** (`loopplane`) — a thin host over the public Host
Application Interface (`loopplane.host`) that lets a developer chat with the agent,
run one-shot prompts, and manage sessions from the shell. It renders the run from
the **normalized event stream**, executes no tool itself, and is **credential-free
by default**: the built-in scripted model runs with no API key or network. A real
model provider is an **optional, credential-gated extra** — used only when its extra
is installed and credentials are present, otherwise the scripted model is used. The
command is purely additive: installing the package without invoking the CLI changes
nothing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hold an interactive chat from the terminal (Priority: P1)

A developer runs `loopplane chat`, types a prompt, watches the agent's response
stream back, and continues the conversation — all with no credentials.

**Why this priority**: An interactive chat is the smallest viable way to *experience*
LoopPlane without writing a host; it exercises the whole CLI pipeline (input → host
run → event rendering → next turn).

**Independent Test**: Drive the chat loop with scripted input and the scripted model;
confirm each turn's prompt produces rendered output from the normalized event stream
and the loop continues until an exit signal.

**Acceptance Scenarios**:

1. **Given** `loopplane chat` with the scripted model, **When** the user enters a prompt, **Then** the agent's streamed output and a turn outcome are rendered to the terminal.
2. **Given** an active chat, **When** the user signals exit (EOF / quit), **Then** the session ends cleanly with a normal exit.

### User Story 2 - Run a one-shot prompt non-interactively (Priority: P1)

A developer (or a script) runs `loopplane run "<prompt>"` to get a single response
and a clear outcome, suitable for piping or CI.

**Why this priority**: Non-interactive run is the scriptable counterpart to chat and
is the most testable surface; it makes the CLI usable in automation.

**Independent Test**: Invoke the run command with a prompt and the scripted model;
assert the rendered response and a success exit status.

**Acceptance Scenarios**:

1. **Given** `loopplane run "<prompt>"` with the scripted model, **When** it completes, **Then** the agent's response and the termination outcome are printed and the process exits with a success status.

### User Story 3 - List and resume sessions (Priority: P2)

A developer who has configured durable storage lists prior sessions and resumes one
to continue where they left off.

**Why this priority**: Session continuity is valuable but secondary to running the
agent; it is only available when a durable session store is configured.

**Independent Test**: With a durable store configured, create a session, list it, and
resume it; confirm the resumed session reconstructs its prior conversation.

**Acceptance Scenarios**:

1. **Given** a configured durable store with a prior session, **When** the user lists sessions, **Then** each session's public-safe identity and recency are shown.
2. **Given** a listed session, **When** the user resumes it, **Then** the conversation continues from the reconstructed state.

### User Story 4 - Use a real model when configured (Priority: P2)

A developer who has installed the real-provider extra and set their credentials in the
environment runs the CLI against a real model; without those, the CLI runs on the
scripted model.

**Why this priority**: A real model is what makes the CLI genuinely useful, but it
must be strictly opt-in and credential-gated to keep the default credential-free.

**Independent Test**: With neither the extra nor credentials present, confirm the CLI
selects the scripted model; with the selection inputs present, confirm it selects the
real provider (the provider's network path is validated manually, not in CI).

**Acceptance Scenarios**:

1. **Given** no real-provider extra and no credentials, **When** the CLI starts, **Then** it uses the scripted model with no network access.
2. **Given** the real-provider extra installed and credentials set, **When** the CLI starts, **Then** it selects the real provider.

### User Story 5 - A safe, thin command (Priority: P3)

An operator wants assurance the CLI never leaks a secret and never becomes a second
place where tools run.

**Why this priority**: Public-safety and boundary integrity; the CLI is a host, not a
runtime.

**Independent Test**: Exercise the CLI's output and error paths and confirm none carry
a secret, credential, private path, or raw exception; confirm the CLI composes only the
public host interface and renders only normalized events.

**Acceptance Scenarios**:

1. **Given** any CLI command, including an error, **When** it produces output, **Then** the output carries no secret, credential, private path, or raw exception detail.
2. **Given** a run, **When** the agent uses a tool, **Then** the tool runs through the runtime's gateway (not the CLI), and the CLI only renders the normalized events.

### Edge Cases

- **No prompt given to `run`** → a public-safe usage message and a non-success exit.
- **Ctrl-C / interrupt during a run** → the run cancels cleanly and the CLI exits without a traceback.
- **EOF on chat input** → the chat ends cleanly.
- **Resume without a durable store** → a clear public-safe message, not a crash.
- **Real-provider extra present but credentials missing** → fall back to the scripted model (or a clear public-safe message), never a leaked or partial credential.
- **A tool fails during a run** → the failure is rendered as a normalized outcome, not a CLI traceback.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The package MUST install a console entry point `loopplane`.
- **FR-002**: The CLI MUST provide an interactive chat mode that reads a prompt, runs it through the host, renders the streamed output, and repeats until an exit signal.
- **FR-003**: The CLI MUST provide a one-shot `run` mode that executes a single prompt non-interactively and prints the response and outcome.
- **FR-004**: The CLI MUST render a run from the **normalized event stream** (assistant output, tool activity, termination) and MUST surface only metadata-safe information.
- **FR-005**: The CLI MUST be credential-free by default — the built-in scripted model runs with no credential and no network.
- **FR-006**: The CLI MUST select a real model provider only when its optional extra is installed **and** credentials are present in the environment; otherwise it MUST use the scripted model. The selection MUST never expose or partially print a credential.
- **FR-007**: The CLI MUST provide session list and resume when a durable session store is configured, and a clear public-safe message when it is not.
- **FR-008**: The CLI MUST execute no tool itself and drive no runtime internal — it composes only the public Host Application Interface and renders the normalized event stream (Constitution V & VI).
- **FR-009**: All CLI output and errors MUST be public-safe — no secret, credential, private path, or raw exception detail; failures render as public-safe messages.
- **FR-010**: The CLI MUST be additive — it adds the entry point and a `loopplane.cli` package without changing the runtime core or any prior unit's contract; installing the package without invoking the CLI changes nothing.
- **FR-011**: The CLI MUST exit cleanly on interrupt (Ctrl-C) and end-of-input (EOF), without a traceback.
- **FR-012**: The CLI MUST provide a usage/help surface for its commands.

### Key Entities

- **CLI command**: one of `chat`, `run`, or a session command, dispatched from the console entry point.
- **Event renderer**: turns the run's normalized events into terminal output (metadata-safe).
- **Provider selection**: the decision between the scripted model (default) and an optional, credential-gated real provider.
- **Session view**: the public-safe identity and recency of a durable session for list/resume.

### Out of Scope

- A full-screen TUI; the web frontend (unit 018) and desktop GUI (unit 019).
- A configuration-file format; multi-user or remote operation.
- The concrete network implementation of a specific model provider beyond the gated selection seam and a thin adapter (its network path is validated manually, like unit 001's real-model procedure).
- Any new runtime dependency for the core CLI (the entry point uses the standard library; a real provider lives behind an optional extra).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can hold an interactive chat with the agent from the terminal with no credentials and no network.
- **SC-002**: `loopplane run "<prompt>"` prints the agent's response and a clear termination outcome and exits with a success status.
- **SC-003**: With no real-provider extra or credentials, the CLI runs fully on the scripted model; with both present, it selects the real provider.
- **SC-004**: 100% of CLI output and error messages pass the repository public-safety scan.
- **SC-005**: Installing LoopPlane without invoking the CLI leaves runtime behavior unchanged (the full existing suite stays green).

## Assumptions

- **Thin host**: the CLI composes only `loopplane.host`; it adds no runtime behavior and re-implements nothing the host already provides.
- **Scripted default**: the credential-free scripted model is the default so the CLI is usable and testable offline; a real provider is an optional, credential-gated extra validated manually (consistent with unit 001's real-model validation).
- **Metadata-only rendering**: the renderer consumes the normalized event stream and prints only public-safe metadata and assistant text.
- **Testable core**: the command dispatch, one-shot run, rendering, and provider selection are exercised without real interactivity (scripted input + scripted model); the interactive REPL is a thin wrapper over the testable core.
- **Additive entry point**: adding `[project.scripts]` and the `loopplane.cli` package does not change packaging guarantees (py.typed, shipped subpackages) or any prior unit's API.
