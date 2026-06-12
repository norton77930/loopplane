# Feature Specification: Agent Harness Runtime Foundation

**Feature Branch**: `001-loopplane-runtime-foundation`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Establish LoopPlane's first phase: a clean Agent Harness
Runtime foundation — Agent Loop boundary, Runtime Controller/Dispatcher, Tool Gateway with
MCP and internal tool adapters, Skill Execution Profile, Runtime Event Bus, Memory,
Checkpoint, Artifact Storage, Observability, Human Approval boundary, and extension points
for a future scheduler/validator/loop-engineering layer. Architecture intent is extracted,
public-safe, from a private local reference baseline (see
[reference-analysis.md](./reference-analysis.md))."

## Feature Overview

LoopPlane's first phase delivers an embeddable Agent Harness Runtime: the governed core that
drives a model-and-tools conversation loop and makes every step observable, controllable, and
durable. The harness owns thirteen bounded components — Agent Loop, Runtime Controller,
Dispatcher, Tool Gateway, the Internal and MCP tool adapters, Skill Execution Profile, Runtime
Event Bus, Memory, Checkpoint, Artifact Storage, Observability, and the Human Approval
boundary — and exposes a sanctioned extension surface where future loop-engineering layers
(scheduler, validator, evaluator, auto-iteration) will attach. No end-user host ships in this
phase: the deliverable is the runtime that every future host and automation layer builds on.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drive a complete agent run through the harness (Priority: P1)

An agent developer embeds the LoopPlane runtime, submits a user prompt to a session, and the
harness drives the full conversation turn — model reasoning, tool calls, tool results, and
follow-up reasoning — until the run ends for an explicit reason. Every step the runtime takes
is visible to the developer as an ordered stream of normalized runtime events.

**Why this priority**: This is the core of the product. Without a working, observable agent
loop there is nothing for any other component or future layer to govern. It is independently
demonstrable with nothing but a scripted model and one echo-style tool.

**Independent Test**: Can be fully tested by running one tool-using conversation against a
scripted model substitute and asserting on the emitted event sequence and final history.

**Acceptance Scenarios**:

1. **Given** a session with a scripted model that answers in plain text, **When** the
   developer submits a prompt, **Then** the event stream contains assistant output
   increments followed by a turn-completion event and exactly one terminal event with reason
   "natural completion" and the recorded history contains the user and assistant messages.
2. **Given** a scripted model that first requests a tool call and then answers, **When** the
   run executes, **Then** the event stream shows tool-call start and tool-call result events
   between the two reasoning turns, and the final history interleaves user, assistant,
   tool-result, and assistant entries coherently.
3. **Given** a run in progress, **When** the developer requests cancellation while model
   output is still streaming, **Then** the run stops promptly without raising an error and
   ends with a terminal event with reason "cancelled", and the session is left in a
   consistent, resumable state.
4. **Given** a session configured with a maximum turn budget, **When** the model keeps
   requesting tools past that budget, **Then** the run ends with a terminal event with
   reason "turn budget exhausted" instead of running forever.
5. **Given** the model requests a tool name that does not exist, **When** the runtime
   processes the request, **Then** the model receives an error-marked tool result naming the
   unknown tool and the run continues rather than crashing.

---

### User Story 2 - Govern every tool call through one gateway (Priority: P2)

A platform operator configures tools from two sources — built-in tools and external MCP tool
servers — and a human-approval policy. Every tool call the agent makes, regardless of
source, passes through the same gateway: it is resolved, validated, permission-checked,
executed with a time limit, and its outcome is normalized. Sensitive calls pause for human
approval before executing.

**Why this priority**: Tool governance is the control plane's first safety promise. It builds
directly on User Story 1 and is required before the runtime can be trusted with real tools.

**Independent Test**: Can be fully tested by registering one internal tool and one external
MCP server, configuring allow/deny/ask policies, and asserting on gateway decisions, approval
round-trips, and normalized results.

**Acceptance Scenarios**:

1. **Given** a policy that denies a specific tool, **When** the model requests that tool,
   **Then** the tool never executes, the model receives an error-marked result carrying the
   denial reason, and the run continues.
2. **Given** a policy that requires asking for a specific tool, **When** the model requests
   it, **Then** a structured approval request reaches the human reviewer, the call waits for
   the decision, an approval of "always for this session" is remembered so the same tool is
   not re-asked in that session, and the call then executes.
3. **Given** an external MCP server is configured, **When** the model calls one of its
   tools, **Then** the call passes the same permission check and produces the same normalized
   result shape as an internal tool.
4. **Given** one of two configured MCP servers fails to connect, **When** the session
   starts, **Then** tools from the healthy server and all internal tools remain available
   and the failure is reported without aborting the session.
5. **Given** a tool that runs longer than its time limit, **When** the limit expires,
   **Then** the model receives a normalized timeout error result and the runtime remains
   healthy.
6. **Given** a tool input containing a parameter the tool never declared, **When** the
   gateway validates the call, **Then** the call is rejected before execution with a
   validation error result.

---

### User Story 3 - Suspend, resume, and audit a session (Priority: P3)

An agent developer runs a long task, the process is interrupted partway through, and they
later resume the same session. The runtime restores the conversation from its durable
checkpoint records — repairing any tool call that was interrupted mid-flight — and oversized
tool outputs are preserved in full as artifacts that can be inspected after the run.

**Why this priority**: Durability is what makes long, loop-engineered work possible. It
depends on User Stories 1–2 producing the steps to record.

**Independent Test**: Can be fully tested by recording a session, terminating the process at
chosen points, resuming from records alone, and comparing reconstructed state.

**Acceptance Scenarios**:

1. **Given** a session whose process was stopped after several completed turns, **When** the
   developer resumes the session, **Then** the restored history matches all completed steps
   exactly and the next prompt continues the conversation coherently.
2. **Given** a session interrupted between a tool-call request and its result, **When** the
   session is resumed, **Then** the incomplete call is repaired with an error-marked
   synthetic result, the repair is surfaced as a warning, and the conversation remains
   valid.
3. **Given** a tool produced output larger than the configured threshold, **When** the run
   records the result, **Then** the full output is stored as an artifact, the conversation
   carries a bounded preview plus a stable reference, and the artifact can be retrieved by
   that reference after the run.
4. **Given** one corrupted record inside a session's checkpoint data, **When** the session
   loads, **Then** the corrupted record is skipped with a warning and all remaining records
   still load.

---

### User Story 4 - Recall memory and execute skills under a profile (Priority: P4)

An agent developer gives the runtime durable memory entries and a set of declarative skills.
During a run, relevant memory is injected into the model's working context without altering
the user's recorded words, available skills are advertised to the model incrementally, and
each skill executes only within the bounds its execution profile declares.

**Why this priority**: Memory and skills make the harness useful for real work, but the
runtime is already valuable for plain tool-using agents without them.

**Independent Test**: Can be fully tested by seeding memory entries and skill definitions,
running scripted conversations, and asserting on prompt assembly, advertisement behavior,
and profile enforcement.

**Acceptance Scenarios**:

1. **Given** stored memory entries relevant to the user's prompt, **When** the run begins,
   **Then** the model's working context contains the selected entries while the durable
   history records the user's prompt verbatim, with no injected content.
2. **Given** a set of registered skills, **When** two turns run in the same session,
   **Then** each skill is advertised to the model once (newly available skills only on
   later turns) and the advertisement stays within its prompt budget.
3. **Given** a skill whose execution profile forbids autonomous invocation, **When** the
   model attempts to invoke it on its own, **Then** the invocation is refused and reported
   as unavailable for autonomous use.
4. **Given** a malformed skill definition and a malformed memory entry, **When** the runtime
   loads them, **Then** each is skipped with a diagnostic and the run proceeds with the
   valid remainder.

---

### User Story 5 - Operate with metadata-only observability (Priority: P5)

A platform operator enables observability and, for any run, can see what steps happened, how
long each took, how many tokens were used, and what failed — while provably seeing none of
the conversation content. With observability disabled (the default), runtime behavior is
unchanged.

**Why this priority**: Observability is essential for operating the control plane but is an
overlay: every signal it consumes already exists as runtime events from Stories 1–4.

**Independent Test**: Can be fully tested by running identical scripted sessions with
observability off and on, comparing behavior, and scanning exported telemetry for planted
sentinel content.

**Acceptance Scenarios**:

1. **Given** observability is disabled, **When** a scripted session runs, **Then** the
   emitted event sequence is identical to the same session with observability enabled
   (zero behavior change).
2. **Given** observability is enabled, **When** a tool-using run completes, **Then** the
   trace shows the run with nested timed steps for each turn, each model call, and each
   tool call.
3. **Given** conversation content seeded with a unique sentinel string, **When** the run's
   telemetry is exported, **Then** the sentinel appears nowhere in any span, metric, or
   error record.
4. **Given** a tool fails during execution, **When** telemetry records the failure, **Then**
   only the error's type is recorded — never its message or stack trace — and a call blocked
   by policy is not counted as an execution failure.

---

### Edge Cases

- Model requests several tool calls in one turn where only some are declared safe to run
  concurrently: safe calls may run in parallel, the rest run sequentially, and emitted
  events keep a deterministic per-call order.
- The human approver disconnects while approval requests are pending: every pending request
  resolves as denied, in-flight work is cancelled cleanly, and nothing hangs.
- A run is cancelled before the first model response: the run ends with a "cancelled"
  terminal event and the triggering user input is not left stranded in durable history in a
  way that would corrupt the next turn's role alternation.
- Conversation history grows past the model's context capacity: older history is compacted
  into a summary marker without separating a tool call from its result; if the model still
  rejects the prompt for length, the runtime retries once after compaction and then surfaces
  the failure.
- History is compacted while skills have already been advertised or invoked: the runtime
  re-establishes the augmentations the model still needs after compaction, and re-established
  skills are neither treated as newly available nor double-counted against the prompt budget.
- A consumer reattaches to an existing session: durable history — including the user's past
  prompts — replays as events so the visible conversation can be fully reconstructed.
- An event consumer receives an event type it does not recognize: it skips the event and
  continues.
- The checkpoint storage location does not exist yet on first use: it is created; absence of
  prior sessions yields an empty listing, not an error.
- Two tool results are recorded concurrently in one session: records never interleave or
  corrupt.

## Requirements *(mandatory)*

### Functional Requirements

#### Agent Loop

- **FR-001**: The Agent Loop MUST drive a run as a cycle of model reasoning and tool
  execution that ends with exactly one terminal event whose reason is one of an enumerated
  set: natural completion, turn budget exhausted, cancelled, or unrecoverable error, along
  with the count of turns taken.
- **FR-002**: The Agent Loop MUST emit a normalized runtime event for every observable step
  (assistant output increment, turn completion, tool call start, tool call result,
  termination) in a deterministic order consistent with execution.
- **FR-003**: Cancellation MUST take effect both before a turn starts and while model output
  is streaming, MUST NOT raise an error to the caller, and MUST end the run with a
  "cancelled" terminal event leaving session state consistent.
- **FR-004**: When the model requests an unknown tool or a tool invocation fails, the Agent
  Loop MUST return an error-marked tool result to the model and continue the run.
- **FR-005**: Tool calls in a turn MUST be partitioned so calls declared concurrency-safe may
  execute in parallel while all others execute sequentially; emitted events MUST preserve a
  deterministic per-call order regardless of completion timing.
- **FR-006**: Conversation state MUST persist across turns within a session, and consumers
  MUST be able to obtain a point-in-time history snapshot that cannot mutate internal state.
- **FR-007**: A turn that produces no assistant response (cancelled before output, or a zero
  turn budget) MUST NOT leave the triggering user input stranded in durable history in a way
  that breaks role alternation on the next turn.
- **FR-008**: When history approaches the model's context capacity, the runtime MUST compact
  older history into a summary marker without separating a tool call from its result; on a
  context-overflow error it MUST compact and retry exactly once before surfacing the
  failure.

#### Runtime Controller / Dispatcher

- **FR-010**: The Runtime Controller MUST own session lifecycle — create, attach, drive,
  detach, resume, terminate — independent of any transport, host, or frontend.
- **FR-011**: The Dispatcher MUST drive the complete session round-trip using only abstract
  send/receive channels, so the same driver serves any future host without modification.
- **FR-012**: The Dispatcher MUST manage pending human interactions (approval requests and
  questions to the user) keyed by request identifier, matching each response to exactly one
  pending request.
- **FR-013**: When a consumer channel closes mid-run, the Dispatcher MUST stop cleanly:
  cancel in-flight work, resolve every pending approval as denied, clear per-connection
  callbacks, and never hang.
- **FR-014**: On reattachment to an existing session, the Dispatcher MUST replay durable
  history as events — including past user prompts — sufficient to reconstruct the visible
  conversation.
- **FR-015**: The Dispatcher MAY batch rapid output increments for delivery efficiency but
  MUST NOT reorder events: any non-incremental event forces buffered increments to flush
  first.

#### Tool Gateway

- **FR-020**: All tool resolution, authorization, and execution MUST flow through the Tool
  Gateway; the runtime MUST offer no alternative path by which a tool can execute.
- **FR-021**: The Gateway MUST maintain a registry of available tools from all sources and
  resolve calls by name; an unknown name yields an error result, never a crash.
- **FR-022**: The Gateway MUST validate tool input against the tool's declared schema before
  execution and reject inputs containing undeclared parameters.
- **FR-023**: The Gateway MUST obtain a policy decision (see Human Approval) before executing
  each call and convert denials into error-marked results carrying the denial reason.
- **FR-024**: The Gateway MUST enforce a per-call execution time limit; expiry produces a
  normalized timeout error result.
- **FR-025**: The Gateway MUST normalize every failure mode (validation failure, policy
  denial, execution error, timeout, adapter fault) into one error-result shape; raw adapter
  or internal errors MUST NOT leak to the model or to consumers.
- **FR-026**: The Gateway MUST apply output-size management: oversized results are reduced
  for the model and, where artifact storage applies, preserved in full as artifacts with an
  in-result reference marker.

#### Internal Tool Adapter

- **FR-030**: Internal tools MUST conform to one tool contract: declared name, description,
  and input schema, plus a streaming invocation that can yield text, image, and error
  outputs.
- **FR-031**: A tool's concurrency-safety and read-only declarations MUST default to the
  conservative value (not concurrency-safe, not read-only) when unspecified.
- **FR-032**: An error output from a tool MUST mark that call's result as failed while
  leaving the run alive.
- **FR-033**: The runtime MUST ship a baseline internal tool set sufficient to demonstrate
  the harness end-to-end — at minimum file reading, file writing/editing, content search,
  command execution, and asking the user a question — each available only through the
  Gateway.
- **FR-034**: File-modifying baseline tools MUST guard against stale writes: editing or
  overwriting an existing file requires that the file was read in the current session and has
  not changed since that read; otherwise the call fails with a validation-class error result.
  Creating a new file is exempt.

#### MCP Tool Adapter

- **FR-040**: The MCP adapter MUST load external tool-server definitions from layered
  configuration where more specific scopes override broader ones; a malformed entry disables
  only that entry, reports a diagnostic, and never crashes the runtime.
- **FR-041**: The adapter MUST manage each server's connection lifecycle: connect, discover
  available tools, invoke tools, and shut down cleanly.
- **FR-042**: Tools discovered from external servers MUST register under source-qualified
  names so they cannot collide with internal tools or with other servers' tools.
- **FR-043**: Failure to connect to or invoke one external server MUST be isolated: other
  servers' tools and internal tools remain available.
- **FR-044**: External tool schemas MUST be translated into the runtime's input-validation
  model, with a safe fallback for constructs that cannot be translated.
- **FR-045**: External tools MUST be subject to the same Gateway authorization, timeout,
  error normalization, and artifact rules as internal tools.

#### Skill Execution Profile

- **FR-050**: A skill MUST be a declarative package of instructions plus metadata that
  includes an execution profile stating how the skill may be invoked and what execution
  constraints apply.
- **FR-051**: Skill loading MUST validate structure and size; a malformed or oversize skill
  is skipped with a diagnostic — never crashed on, never partially loaded.
- **FR-052**: Skills from multiple sources MUST merge deterministically, with the more
  specific source winning on name conflicts.
- **FR-053**: The runtime MUST advertise available skills to the model incrementally — only
  skills not yet advertised in the session — within a bounded prompt budget. Advertisement
  and injection state MUST survive history compaction: content the model still needs (such
  as advertised or invoked skills) is re-established after compaction without being treated
  as newly available and without double-counting against the budget.
- **FR-054**: Skill content MUST support substitution of a closed list of runtime-provided
  variables (such as invocation arguments and session identifiers); variables outside the
  list pass through literally.
- **FR-055**: The execution profile MUST at minimum control whether the model may invoke the
  skill autonomously and whether invocation requires human approval; the Gateway and Human
  Approval boundary MUST honor these controls.

#### Runtime Event Bus

- **FR-060**: The runtime MUST define a closed, versioned vocabulary of normalized runtime
  events covering the full session lifecycle: user input (live and replayed), assistant
  output and reasoning increments, turn completion carrying token-usage metadata, tool call
  lifecycle, approval and question round-trips, history replay, non-fatal diagnostics, and
  termination.
- **FR-061**: The Agent Loop MUST emit only normalized runtime events and MUST NOT produce
  frontend- or transport-specific formats.
- **FR-062**: All consumers — streaming, history, replay, step display, trace, observability
  — MUST consume the normalized stream and perform any adaptation on their own side of the
  bus.
- **FR-063**: Event consumers MUST tolerate unknown event types by skipping them without
  failure.
- **FR-064**: Events MUST serialize and deserialize losslessly across a process boundary.
- **FR-065**: Any change to the event vocabulary MUST be treated as a contract change:
  versioned, specified, and tested before adoption.

#### Memory

- **FR-070**: The runtime MUST support durable memory entries with a declared type, name,
  and description, stored independently of any single session.
- **FR-071**: Memory scanning and indexing MUST skip malformed entries with a diagnostic and
  never fail the run.
- **FR-072**: Memory injection MUST select entries by relevance to the current prompt, with
  a deterministic fallback ordering when relevance scoring is unavailable or fails.
- **FR-073**: Injected memory (and any other prompt augmentation such as skill listings)
  MUST appear only in the assembled model context; durable history MUST retain the user's
  original input verbatim.
- **FR-074**: The agent MUST be able to create and update memory entries during a run
  through a Gateway-governed tool.

#### Checkpoint

- **FR-080**: Every accepted user input, assistant message, tool result, and termination
  MUST be appended to the session's durable, append-only record as it occurs, not batched at
  run end.
- **FR-081**: A session MUST be resumable from its durable records alone, reconstructing
  conversation state without any in-process state from the prior run.
- **FR-082**: Resume MUST repair an incomplete tool interaction (a recorded call without a
  recorded result) by inserting an error-marked synthetic result and MUST surface a warning
  identifying the repaired call.
- **FR-083**: A corrupted record MUST be skipped with a warning while all remaining records
  load.
- **FR-084**: Concurrent record writes within one session MUST NOT interleave or corrupt the
  record stream.
- **FR-085**: Sessions MUST be listable with identity and recency metadata, ordered most
  recent first; a missing storage location yields an empty listing.

#### Artifact Storage

- **FR-090**: Tool results exceeding a configurable size threshold MUST be persisted in full
  as artifacts associated with the session and the originating call.
- **FR-091**: The in-conversation representation of an offloaded result MUST carry a bounded
  preview plus a stable reference to the artifact.
- **FR-092**: When the aggregate size of retained tool results exceeds a configurable
  budget, the runtime MUST replace the largest eligible results first, and replacement
  decisions MUST remain stable ("frozen") across resume.
- **FR-093**: Artifacts MUST be retrievable by their reference after the run for inspection.
- **FR-094**: Replacement decisions MUST be recorded through the same durable session-record
  boundary as other history; the Agent Loop itself MUST NOT own persistence.

#### Observability

- **FR-100**: Observability MUST be disabled by default; when disabled it MUST impose zero
  behavior change and negligible overhead.
- **FR-101**: When enabled, each run MUST produce a trace of nested timed steps — run and
  turns, with each model call and tool call inside them — including durations.
- **FR-102**: Token usage and step counts MUST be exported as metrics with low-cardinality
  labels (no per-session label values).
- **FR-103**: Telemetry MUST be metadata-only: no conversation content, no tool arguments or
  results, and no exception messages or stack traces; failures are recorded by error type
  only.
- **FR-104**: Only genuine execution failures count as tool errors in metrics; calls blocked
  by policy MUST NOT count as execution failures.

#### Human Approval

- **FR-110**: Every tool execution MUST receive a policy decision — allow, deny, or ask —
  before running.
- **FR-111**: A denial MUST produce an error-marked result carrying the denial reason (with
  a default reason supplied when none is given) returned to the model; the run continues.
- **FR-112**: An "ask" decision MUST escalate to a human reviewer as a structured approval
  request and hold that call until a decision arrives or the reviewer channel closes.
- **FR-113**: Approval decisions MUST support single-use and session-scoped variants;
  session-scoped decisions are remembered for the remainder of the session and not re-asked.
- **FR-114**: Persistent permission rules MUST be supported with deterministic precedence:
  a more local scope overrides a broader scope, and within one scope deny overrides allow.
- **FR-115**: If the reviewer channel closes while requests are pending, all pending requests
  MUST resolve as denied.
- **FR-116**: The runtime MUST also support structured non-permission questions from the
  agent to the user, using the same request/response matching machinery as approvals.

#### Future-Layer Extension Points

- **FR-120**: The runtime MUST expose its normalized event stream and session lifecycle
  (start, attach, resume, terminate) as the sanctioned extension surface for future
  scheduler, validator, evaluator, and loop-engineering layers.
- **FR-121**: This phase MUST NOT implement scheduling, validation, evaluation, or
  auto-iteration logic; any such need discovered during implementation MUST be deferred to a
  future-phase specification.
- **FR-122**: A passive demonstration consumer (for example, a run-summary listener) MUST be
  able to attach using only the public extension surface, proving that future layers need no
  access to Agent Loop internals.

### Non-Functional Requirements

- **NFR-001 (Determinism)**: Given identical scripted model behavior and tool outcomes, a run
  MUST produce the same normalized event sequence every time; the ordering rules of FR-002,
  FR-005, and FR-015 are the basis of replay and golden-sequence testing.
- **NFR-002 (Zero-overhead gating)**: Optional subsystems (observability, memory, skills,
  external tools) MUST default to off, and when disabled MUST cause zero behavior change and
  negligible overhead (operationalized by FR-100 and SC-007).
- **NFR-003 (Crash consistency)**: Interrupting the process at any point MUST NOT lose
  completed steps or corrupt a session beyond what FR-082/FR-083 repair and surface as
  warnings.
- **NFR-004 (Privacy)**: Exported telemetry MUST remain metadata-only (FR-103), and every
  committed project document MUST remain public-safe (SC-006).
- **NFR-005 (Portability)**: The runtime core MUST NOT depend on any host, transport, or UI,
  and MUST run on mainstream desktop and server platforms, including Windows-style
  filesystem paths.
- **NFR-006 (Lossless serialization)**: Runtime events and checkpoint records MUST round-trip
  losslessly across a process boundary (FR-064).
- **NFR-007 (Bounded resources)**: Prompt budgets (FR-053), output-size management (FR-026),
  and artifact budgets (FR-092) MUST keep per-session context and storage consumption
  bounded.
- **NFR-008 (Scale target)**: This phase targets a single process driving one session at a
  time per consumer, with many resumable sessions on disk; multi-tenant and
  concurrent-observer scale is out of scope.

### Key Entities

- **Session**: One governed conversation run — identity, accumulated history, lifecycle
  state, and links to its records and artifacts.
- **Run Context**: The per-run execution scope handed to tools and policies — session
  identity, working scope, cancellation signal, turn budget, and session-scoped approval
  memory.
- **Runtime Event**: The normalized, versioned unit of observable runtime behavior; the only
  vocabulary the Agent Loop speaks to the outside world.
- **Checkpoint Record**: One append-only durable entry in a session's history (user input,
  assistant message, tool result, replacement decision, or termination).
- **Tool Descriptor**: The registered identity of a tool — name, description, input schema,
  safety declarations, and source (internal or external server).
- **Tool Invocation / Tool Result**: One requested call with validated input, and its
  outcome marked success or failure with normalized error information.
- **Approval Request / Approval Decision**: A structured escalation of a pending call to a
  human, and the human's answer with scope (single-use or session) and optional reason.
- **Permission Rule**: A persistent allow/deny matcher with a scope that participates in
  deterministic precedence.
- **Skill / Execution Profile**: A declarative instruction package and the constraints
  governing how it may be invoked and executed.
- **Memory Entry**: A typed, durable knowledge item with name and description used for
  relevance selection.
- **Artifact / Replacement Record**: The full content of an oversized tool result stored
  outside the conversation, and the frozen durable note that a history item now carries a
  preview plus reference in its place.
- **Trace Step**: A metadata-only timed record of one run step, nested run → turn → call.

## Runtime Boundaries

Component ownership for this phase (constitution Principle IV). Cross-component interaction
happens only through declared interfaces or normalized runtime events — never through
reach-through internal access.

| Component | Owns | Must not |
|---|---|---|
| Agent Loop | The reasoning ↔ tool-execution cycle, turn sequencing, history compaction, and emission of normalized runtime events | Persist anything directly; format events for any frontend; execute tools itself |
| Runtime Controller | Session lifecycle: create, attach, drive, detach, resume, terminate | Depend on any transport, host, or frontend |
| Dispatcher | The session round-trip over abstract send/receive channels; the pending approval/question registry; history replay; increment batching | Reorder events; expose Agent Loop internals to consumers |
| Tool Gateway | Tool registry, resolution, input validation, policy decision, execution, timeout, error normalization, and output-size management | Allow any tool to execute via another path; leak raw adapter errors |
| Internal Tool Adapter | The internal tool contract and the baseline tool set | Bypass Gateway governance |
| MCP Tool Adapter | External server configuration, connection lifecycle, discovery, and schema translation | Register unqualified tool names; let one server's failure disable others |
| Skill Execution Profile | Skill loading, merging, advertisement, variable substitution, and invocation constraints | Execute outside Gateway and approval enforcement |
| Runtime Event Bus | The closed, versioned event vocabulary and its delivery to consumers | Carry frontend- or transport-specific formats |
| Memory | Durable entries, relevance selection, and assembly-time injection | Mutate durable history |
| Checkpoint | Append-only session records, resume, repair, and session listing | Accept writes that bypass the recording boundary |
| Artifact Storage | Oversized-result persistence, stable references, and the replacement budget | Change frozen replacement decisions across resume |
| Observability | Metadata-only traces and metrics derived from runtime events | Observe or export conversation content; change behavior when enabled |
| Human Approval | Policy decisions, ask escalation, decision scopes, and persistent rules | Hold a run forever (reviewer disconnect resolves pending requests as denied) |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete tool-using conversation run can be driven end-to-end through the
  harness with a single programmatic entry point, and its emitted event history alone is
  sufficient to reconstruct the full step sequence (verified by replay comparison).
- **SC-002**: 100% of tool executions — internal and external — traverse the Tool Gateway;
  no test or audit can demonstrate a tool executing by any other path.
- **SC-003**: A session interrupted at any point resumes with zero loss of completed steps,
  and 100% of interrupted tool calls are repaired and flagged rather than silently dropped.
- **SC-004**: With observability enabled, an operator can answer "what steps ran, how long
  each took, and what failed" for any run; content-sentinel scans of exported telemetry find
  zero occurrences across the full test suite.
- **SC-005**: 100% of policy-gated tool calls are decided before execution; every denied
  call yields an explained, non-fatal result to the model.
- **SC-006**: Automated public-safety scans of committed project files find zero private
  references (internal paths, private project names, network addresses, credentials).
- **SC-007**: With all optional subsystems disabled (observability, memory, skills, external
  tools), scripted runs produce event sequences identical to the core loop alone — proving
  zero-behavior-change gating.
- **SC-008**: 100% of cancellation requests in the test suite end the run with a "cancelled"
  terminal event without external process termination, including cancellations issued
  mid-stream.
- **SC-009**: A future-layer stub consumer attaches and produces a per-run summary using
  only the public extension surface, with zero references to Agent Loop internals.

## In Scope *(this phase)*

- The thirteen runtime components listed under Runtime Boundaries, embeddable as a library
  behind a single programmatic entry point.
- A baseline internal tool set (file reading, file writing/editing, content search, command
  execution, asking the user a question) sufficient to demonstrate the harness end-to-end.
- External tool integration through configured MCP servers, governed identically to internal
  tools.
- A scripted model substitute as a first-class test fixture, plus a minimal real-model
  boundary validated separately.
- A passive demonstration consumer proving the future-layer extension surface (FR-122).
- Public-safe specification, plan, contract, and task documentation for all of the above.

## Out of Scope *(this phase)*

- CLI, web/API, and desktop hosts, and any user-facing frontend.
- Scheduler, validator, evaluator, auto-iteration, and loop-engineering automation
  (extension points only — see FR-120 to FR-122).
- Sandboxed or containerized isolation of tool execution.
- Lifecycle hook system, plugin packaging/distribution, multi-agent orchestration,
  conversation knowledge indexing/search, and cost/budget governance.
- Multi-tenant hosting concerns (per-user isolation, authentication, quotas).
- Replacing the runtime core with any external agent framework (constitution Principle
  VIII).

## Assumptions

- Phase-1 consumers are agent/platform developers embedding the runtime programmatically and
  operators reviewing runs; no end-user-facing host ships in this phase.
- One driving consumer per session at a time; concurrent live observers are deferred
  (reference-analysis ambiguity A8).
- Model access sits behind a normalized streaming boundary; automated tests run against a
  scripted model substitute, and at least one real model integration is validated
  separately.
- Besides streamed output, the model boundary exposes per-turn token usage and a
  context-capacity figure; compaction (FR-008) and usage metrics (FR-102) consume these
  rather than measuring independently.
- Local durable storage is sufficient for checkpoints and artifacts in this phase; no
  external database is required. The runtime owns a default storage location that a host can
  override (ambiguity A10).
- Artifact thresholds and aggregate budgets are configurable with sane defaults; exact
  values are a planning decision (ambiguity A3).
- The skill execution profile starts minimal — autonomous-invocation control and approval
  requirement (FR-055) — with richer constraint fields deferred (ambiguity A1).
- The local `openspec/` directory remains a private, untracked reference; all knowledge from
  it enters this repository only as rewritten public-safe content (constitution Principles
  II and VII), with traceability recorded in
  [reference-analysis.md](./reference-analysis.md).
- Specifications and documentation are written in English.
