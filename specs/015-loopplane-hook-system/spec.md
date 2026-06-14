# Feature Specification: LoopPlane Lifecycle Hook System

**Feature Branch**: `015-loopplane-hook-system` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "LoopPlane lifecycle hook system (roadmap unit 015, package loopplane.hooks): an in-process extensibility layer that lets host applications and plugins observe — and, at specific contracted points, gate or modify — the agent's behavior at well-defined lifecycle moments, without forking or monkey-patching the runtime."

## Overview

LoopPlane's runtime is currently closed: a caller who wants to record an audit
trail before every tool call, screen a user prompt before it reaches the model,
run follow-up work when the model stops, or react when a file is written has no
sanctioned seam — their only options are to fork the runtime or monkey-patch it.

This feature adds a **lifecycle hook system**: a small set of well-defined
moments in a run where the runtime invites caller-supplied callbacks to *observe*
the run and, at two contracted points, to *gate or modify* it. Hooks are an
additive, in-process extensibility layer. They are the foundation the later
plugin system (unit 016) uses to package and load behavior, but this unit ships
the hook mechanism alone.

Hooks are deliberately **distinct from the normalized Runtime Event Bus**: events
are fire-and-forget records that consumers read on their own side of the bus;
hooks are synchronous interception points that run inside the agent's control
flow and may, at gating points, change what happens next.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Observe every tool call for an audit trail (Priority: P1)

A platform engineer embedding LoopPlane needs a faithful record of every tool the
agent ran — which tool, whether it succeeded or failed — to satisfy an internal
audit requirement, without changing runtime source.

**Why this priority**: Observation is the smallest viable slice of the hook
system and the most common need. If only this works, the runtime is already
meaningfully more extensible, and it exercises the registry + firing mechanism
end to end.

**Independent Test**: Register an observer at the after-tool-use and
after-tool-failure points, run an agent that uses several tools (some failing),
and confirm the observer received one metadata-only record per tool outcome in
the order the tools ran — with no change to the run's results.

**Acceptance Scenarios**:

1. **Given** an observer registered at the after-tool-use point, **When** the agent completes a run that executes three tools, **Then** the observer is invoked exactly three times with metadata-only payloads identifying each tool and its outcome.
2. **Given** an observer registered at the after-tool-failure point, **When** a tool raises during the run, **Then** the observer is invoked once with sanitized failure metadata (no raw exception text), and the run continues exactly as it would without the observer.

### User Story 2 - Gate or rewrite a tool call before it runs (Priority: P1)

A security-conscious host wants to block the agent from running a specific class
of tool call (for example, any write outside an allowed area) — and, in other
cases, to adjust a call's inputs before it executes — without bypassing or
reimplementing the runtime's existing permission boundary.

**Why this priority**: Gating is the defining capability that separates hooks
from plain observation; it is what makes moderation, policy enforcement, and safe
automation possible. It is P1 because it is the highest-value differentiator.

**Independent Test**: Register a before-tool hook that denies calls matching a
rule, run an agent that attempts such a call, and confirm the call never executes
and is surfaced as a normalized denial; separately, register a hook that modifies
a call's inputs and confirm the tool runs with the modified inputs.

**Acceptance Scenarios**:

1. **Given** a before-tool hook that denies calls to a named tool, **When** the agent attempts that tool, **Then** the tool does not execute and the run surfaces a normalized denial carrying the hook's public-safe reason.
2. **Given** a before-tool hook that rewrites a call's inputs, **When** the agent issues the call, **Then** the tool executes with the rewritten inputs and downstream observers see the rewritten call.
3. **Given** the existing permission/approval boundary has already denied a call, **When** a before-tool hook would have allowed it, **Then** the call still does not execute (a hook cannot widen what approval denied).

### User Story 3 - Run follow-up work when the model stops (Priority: P2)

A CI integrator wants to trigger a follow-up action — for example, kick off a
test run or post a summary — at the moment the model naturally stops, so the
automation reacts without polling.

**Why this priority**: A common automation need, but secondary to the
tool-boundary stories; it depends on the same registry/firing machinery.

**Independent Test**: Register a stop hook, run an agent to natural completion,
and confirm the hook fires once at the stop moment with metadata about the run.

**Acceptance Scenarios**:

1. **Given** a stop hook is registered, **When** the model naturally stops, **Then** the hook is invoked exactly once with a metadata-only payload describing the stopped run.

### User Story 4 - Screen or annotate a user prompt before the model sees it (Priority: P2)

A host that fronts untrusted input wants to screen each user prompt before it
reaches the model — blocking disallowed prompts with a public-safe reason, or
annotating an allowed prompt with extra context.

**Why this priority**: Important for safety-sensitive hosts; it is the second
gating point and reuses the gating-decision contract from User Story 2.

**Independent Test**: Register a prompt-submit hook that blocks a prompt matching
a rule and confirm the model is never called for it; separately, register one
that annotates the prompt and confirm the annotation is present when the model is
called.

**Acceptance Scenarios**:

1. **Given** a prompt-submit hook that blocks disallowed prompts, **When** a disallowed prompt is submitted, **Then** the model is not invoked for it and the block is surfaced with a public-safe reason.
2. **Given** a prompt-submit hook that annotates the prompt, **When** an allowed prompt is submitted, **Then** the model receives the annotated prompt.

### User Story 5 - Observe session, subagent, and file lifecycle (Priority: P3)

A telemetry integrator wants to track the shape of a run — one-time process
setup, session start and end, subagent start and stop, and file changes — to feed
status displays and dashboards.

**Why this priority**: Valuable for observability but the least critical slice;
these are purely observational points layered on the same mechanism.

**Independent Test**: Register observers at the setup, session-start,
session-end, subagent-start, subagent-stop, and file-changed points; run a
session that includes a subagent and a file write; confirm each point fires at
the expected moment with metadata-only payloads.

**Acceptance Scenarios**:

1. **Given** a one-time setup observer, **When** more than one session is created in the same process, **Then** the setup observer is invoked at most once.
2. **Given** a file-changed observer, **When** a write/edit-class tool successfully writes a file, **Then** the observer fires once after the write with the file's identity, and it does not fire when such a tool fails.
3. **Given** subagent-start and subagent-stop observers, **When** the agent delegates to a subagent, **Then** start fires before the subagent runs and stop fires after it finishes (success or failure).

### Edge Cases

- **Point never reached**: A hook registered for a lifecycle point that does not occur in a given run simply never fires and produces no error.
- **Many hooks at one point**: All registered hooks fire in registration order; one hook failing does not prevent the others from firing.
- **Failing observational hook**: A hook that raises or misbehaves at an observational point is isolated — the run's outcome is unchanged and the failure is recorded as a public-safe, metadata-only signal.
- **Failing gating hook**: A hook that raises at a gating point abstains (the runtime proceeds with the decision it would have made without that hook) and the failure is recorded metadata-only; a broken hook never escalates privilege or crashes the run.
- **Invalid gating decision**: A gating hook that returns a malformed or unrecognized decision is treated as an abstention (no opinion).
- **Conflicting gating hooks**: When multiple gating hooks run at one point, any deny results in a deny; modifications compose in registration order (a later hook observes earlier modifications).
- **Slow/blocking hook**: A long-running hook delays the run at that point but never corrupts state or deadlocks; asynchronous hooks are awaited.
- **Boundary-violating hook**: A hook is given no path to resolve, authorize, or execute a tool itself, nor to re-emit or mutate the event stream.
- **Registration during a run**: Registering or unregistering a hook while a run is in flight takes effect on the next time that point fires; it never mutates an in-progress firing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a hook registry that lets a caller register, unregister, and clear callbacks for each supported lifecycle point.
- **FR-002**: The system MUST support these lifecycle points: before-tool-use, after-tool-use (success), after-tool-failure, user-prompt-submit, session-start, session-end, process-setup, subagent-start, subagent-stop, file-changed, and model-stop.
- **FR-003**: For a given lifecycle point, the system MUST invoke registered hooks in the order they were registered (FIFO), deterministically.
- **FR-004**: The system MUST support both synchronous and asynchronous hook callbacks.
- **FR-005**: At observational points, a hook that raises an error, returns an unexpected value, or otherwise misbehaves MUST NOT crash, corrupt, or alter the run; the failure MUST be isolated and surfaced as a public-safe, metadata-only signal.
- **FR-006**: At the before-tool-use point, a hook MUST be able to return a decision that allows the call, denies it with a public-safe reason, or modifies the call's inputs before execution.
- **FR-007**: At the user-prompt-submit point, a hook MUST be able to allow the prompt, block it with a public-safe reason, or annotate it before it reaches the model.
- **FR-008**: When a gating hook denies a tool call or blocks a prompt, the runtime MUST NOT execute the denied action and MUST surface the denial as a normalized outcome consistent with the runtime's existing deny semantics.
- **FR-009**: Before-tool-use and after-tool-use hooks MUST fire within the single Tool Gateway boundary; hooks MUST NOT resolve, authorize, or execute tools themselves and MUST NOT provide any path that bypasses the gateway (Constitution V).
- **FR-010**: The hook system MUST remain distinct from the normalized Runtime Event Bus — hooks are synchronous interception points that may gate/modify, while events stay fire-and-forget normalized records. Event emission MUST NOT depend on hooks, and hooks MUST NOT re-emit or mutate the event stream (Constitution VI).
- **FR-011**: With no hooks registered, the system MUST exhibit zero observable behavior change and MUST add no measurable latency to a run.
- **FR-012**: The before-tool-use hook MUST fire after the existing permission/approval decision and before tool execution, so a hook can never grant a call the approval boundary denied.
- **FR-013**: The file-changed point MUST fire only after a write/edit-class tool has completed successfully, and MUST NOT fire when such a tool fails.
- **FR-014**: The process-setup point MUST fire at most once per process/runtime lifetime.
- **FR-015**: Hook payloads and any denial or annotation reasons MUST be metadata-only and public-safe — containing no secrets, private paths, internal names, or raw exception detail.
- **FR-016**: A gating hook that raises an error or returns a malformed decision MUST resolve to the baseline decision (as if the hook were absent) — it MUST NOT auto-allow anything not already allowed, nor abort the run — and the failure MUST be recorded as a metadata-only signal.
- **FR-017**: When multiple gating hooks run at one point, the system MUST apply a defined resolution policy: any deny results in a deny, and modifications compose in registration order such that a later hook observes earlier modifications.
- **FR-018**: Registering or unregistering a hook MUST be safe at any time; a change made while a run is in flight MUST take effect on the next firing of that point and MUST NOT mutate an in-progress firing.
- **FR-019**: The subagent-start and subagent-stop points MUST fire around delegated subagent runs without the hook layer itself driving runs; when no subagent is used, these points simply never fire.
- **FR-020**: The hook system MUST be present but inert by default — the runtime registers no hooks of its own, and hosts or plugins opt in by registering.

### Key Entities

- **Lifecycle point**: A named, well-defined moment in a run (the eleven points in FR-002) at which the runtime invites registered callbacks.
- **Hook callback**: A caller-supplied function — synchronous or asynchronous — invoked at a lifecycle point with a metadata-only payload; at gating points it returns a gating decision.
- **Hook registry**: The collection that maps each lifecycle point to its ordered list of callbacks and exposes register, unregister, clear, and fire operations.
- **Hook payload**: The metadata-only data describing the moment — for example a tool's identity and sanitized input identity, a prompt reference, a session identifier, a subagent reference, or a changed file's identity.
- **Gating decision**: The result a gating hook returns — for before-tool-use: allow, deny (with public-safe reason), or modify (replacement inputs); for user-prompt-submit: allow, block (with public-safe reason), or annotate.

### Out of Scope

- Packaging or loading hooks via a plugin manifest (unit 016 — plugin system).
- Any CLI or GUI surface for managing hooks (units 017–019).
- Persisting or replaying hooks across sessions or process restarts.
- Using a model-stop hook to continue or resume the loop (model-stop is observational in this unit; loop-continuation is deferred).
- Distributed or remote hook execution.
- Adding any new third-party dependency; the feature is in-process Python only, with no network or GUI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can capture an audit record for 100% of a run's tool calls by registering a single observer, with no change to runtime source.
- **SC-002**: A before-tool gating hook prevents 100% of the tool calls it targets from executing, and each prevented call is surfaced as a normalized denial.
- **SC-003**: With no hooks registered, a run produces outcomes and normalized events identical to the pre-feature baseline — verified by the full existing test suite remaining green with zero changes to expected results.
- **SC-004**: In 100% of runs that include a deliberately failing observational hook, the run completes with the same outcome it would have had without the hook.
- **SC-005**: 100% of hook payloads and denial/annotation reasons pass the repository public-safety scan (zero secrets, private paths, internal names, or raw exception detail).
- **SC-006**: A user-prompt-submit hook can block or annotate 100% of submitted prompts before the model is invoked for them.
- **SC-007**: Hooks at a given point fire in registration order in 100% of cases, verifiable from a recorded firing sequence.
- **SC-008**: A failing or malformed gating hook never escalates privilege and never aborts a run — measured across the gating edge-case tests, 100% resolve to the baseline decision.

## Assumptions

- **Multi-hook gating policy**: Where several gating hooks run at one point, deny wins and modifications compose in registration order. This default is documented here and may be revisited during clarification.
- **Gating-hook failure mode**: A raising or malformed gating hook abstains (resolves to the baseline decision as if absent) rather than failing open or aborting; this preserves existing behavior and never widens privilege.
- **Model-stop semantics**: In this unit, the model-stop point is observational only; the ability to drive a continuation of the loop from a stop hook is intentionally deferred to a future unit.
- **Subagent integration**: Subagent-start/stop integrate with the existing multi-agent orchestration layer (unit 013); when subagents are not used, those points never fire.
- **Default-inert**: The runtime ships the hook system present but with no hooks registered; opting in is the host's or a plugin's explicit act, so existing embeddings see no behavior change.
- **Composition over the existing boundaries**: Hooks compose the already-public runtime boundaries (Tool Gateway, approval decision, loop lifecycle, subagent execution); this unit introduces no new tool source, transport, persistence, or third-party dependency.
- **Public-safe payloads**: All payloads are derived from already-public, metadata-only surfaces, consistent with the observability layer's metadata-only discipline.
