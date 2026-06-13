# Feature Specification: Host Integration Interface

**Feature Branch**: `002-loopplane-host-interface`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Define the minimal host interface that allows applications to embed
and run the LoopPlane Runtime Foundation implemented in `001-loopplane-runtime-foundation`. Turn the
runtime foundation into something usable by host applications — a Host Application Interface, a
minimal programmatic configuration contract, a reference runner with a scripted model substitute and
internal tool execution, a minimal developer-focused example runner for smoke testing, end-to-end
smoke tests, and public-safe embedding documentation — without becoming a full CLI, Web API, or
desktop host, and without a loop-engineering automation layer."

## Feature Overview

LoopPlane's first phase delivered an embeddable Agent Harness Runtime: thirteen bounded components
that drive a governed model-and-tools loop and make every step observable, controllable, and durable
(see [`../001-loopplane-runtime-foundation/spec.md`](../001-loopplane-runtime-foundation/spec.md)).
That phase shipped the runtime but no integration surface: to run anything, a host must construct and
hand-wire many collaborators in the right order and know every cross-dependency between them.

Phase 2 turns that foundation into something a host application can embed and run from one place. It
adds a thin **host-integration layer** over Phase 1 — it composes Phase-1 components through their
declared interfaces and adds **no runtime internals of its own**. The deliverable is five things:

1. A **Host Application Interface** — the single documented seam through which an external application
   assembles the runtime, starts a run, supplies the runtime's collaborators (user input, model
   provider, tools, memory, checkpoint store, artifact store, approval handler), and consumes the
   normalized runtime-event stream.
2. A **minimal Runtime Configuration contract** — a declarative, public-safe object that selects the
   model provider, the tool registry, the memory/checkpoint/artifact backends, and the approval
   behavior for a run.
3. A **Reference Runner** — a minimal assembly that wires the runtime together from a configuration,
   supports a scripted model substitute for deterministic runs, executes internal tools through the
   Tool Gateway, and emits runtime events.
4. A **minimal example runner** — a developer-focused local entry point that drives a scripted
   scenario through the interface for smoke testing. It is intentionally minimal and is not a product
   CLI.
5. **End-to-end smoke tests** and **public-safe embedding documentation** that prove and demonstrate
   the whole path deterministically.

Phase 2 deliberately ships no end-user product host (web, browser, desktop, or full CLI) and no
loop-engineering automation (scheduler, validator, evaluator, auto-iteration). It depends on the
Phase-1 foundation and does not duplicate its runtime internals.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Embed and start a run through one configured entry point (Priority: P1)

An application developer describes a run in a configuration object — a model provider and one or more
tools — hands it to the Host Application Interface, submits a user request, and the interface
assembles the Phase-1 runtime and drives the run to completion. The developer receives the run's
outcome and the ordered stream of normalized runtime events, without manually constructing or
connecting the Runtime Controller, Tool Gateway, event bus, or any store.

**Why this priority**: This is the point of the phase. Without a single configured entry point that
assembles and runs the foundation, the runtime stays unusable to anyone who has not memorized its
internal wiring. It is independently demonstrable with nothing but a scripted model and one test tool.

**Independent Test**: Can be fully tested by building a minimal configuration (scripted model + one
test tool), submitting a prompt through the interface, and asserting on the emitted event sequence and
the returned run outcome.

**Acceptance Scenarios**:

1. **Given** a configuration with a scripted model that answers in plain text and no tools, **When**
   the developer starts a run with a prompt through the interface, **Then** the interface assembles
   the runtime, the run completes with exactly one terminal event of reason "natural completion", and
   the developer obtains the ordered event stream and the final history without constructing any
   Phase-1 component directly.
2. **Given** a configuration with a scripted model that requests a test tool and one tool registered,
   **When** the run executes through the interface, **Then** the Tool Gateway executes the tool and
   the event stream shows the tool-call start and result between the reasoning turns.
3. **Given** the same configuration and prompt, **When** the run is started twice, **Then** the two
   runs produce identical ordered event sequences and identical outcomes (determinism).
4. **Given** one configured interface, **When** the developer starts two runs in sequence, **Then**
   each run is independent and deterministic, with no state from the first run leaking into the
   second.

---

### User Story 2 - Configure the runtime's collaborators through a minimal contract (Priority: P2)

An application developer selects, through one declarative configuration object, which model provider,
tools, memory backend, checkpoint store, artifact store, and approval behavior a run uses. Optional
backends that are omitted simply stay off, leaving runtime behavior identical to the bare Phase-1
loop. A configuration that is invalid or inconsistent is rejected before any run starts.

**Why this priority**: The configuration contract is what makes the interface usable without reading
the runtime's source. It builds on User Story 1 and is the documented shape every host depends on.

**Independent Test**: Can be fully tested by assembling runtimes from a range of configurations —
minimal, durable, approval-restricted, and invalid — and asserting on what gets wired, on
gating-equality, and on fail-fast rejection.

**Acceptance Scenarios**:

1. **Given** a configuration that selects a checkpoint backend and an artifact backend, **When** the
   runtime is assembled, **Then** durable recording and oversized-result offload are wired
   automatically and the developer never connects the artifact handoff to the Tool Gateway by hand.
2. **Given** a configuration whose approval behavior denies a specific tool, **When** the model
   requests that tool, **Then** the call is denied through the Phase-1 Human Approval boundary and the
   model receives an error-marked result, exactly as Phase 1 specifies.
3. **Given** a configuration that omits memory, skills, external tools, observability, and durable
   storage, **When** a scripted run executes, **Then** its event sequence is identical to the same
   scripted run driven against the bare Phase-1 runtime (zero behavior change from the integration
   layer).
4. **Given** a configuration that names no model, or names two tools under the same name, or selects
   an optional capability that is not available, **When** the host assembles the runtime, **Then**
   assembly fails fast with a clear, public-safe error before any run starts.

---

### User Story 3 - Drive and observe a run as a host (Priority: P3)

A host registers a consumer for the normalized event stream and receives every event for a run in
order. For interactive use, the host drives the round-trip — submitting input, answering an approval
or a question, and cancelling — through the runtime's abstract channels, without touching Agent Loop
internals.

**Why this priority**: Event consumption and the interactive round-trip are how any host actually
observes and steers a run. They build on User Story 1 and reuse the Phase-1 Dispatcher and event bus
rather than re-implementing them.

**Independent Test**: Can be fully tested by attaching a host event consumer and an approval handler,
driving a scripted run that asks for approval and is then cancelled, and asserting on event order, the
approval round-trip, and the cancelled terminal event.

**Acceptance Scenarios**:

1. **Given** a host-supplied event consumer, **When** a run executes, **Then** the consumer receives
   every runtime event in deterministic order, ending with exactly one terminal event.
2. **Given** an event consumer that does not recognize a future event type, **When** that event is
   delivered, **Then** the consumer skips it and continues, consistent with Phase-1 unknown-type
   tolerance.
3. **Given** a run in progress, **When** the host requests cancellation through the round-trip,
   **Then** the run stops promptly without raising and ends with a terminal event of reason
   "cancelled".
4. **Given** an approval policy that asks for a specific tool and a host-supplied approval handler,
   **When** the model requests that tool, **Then** a structured approval request reaches the handler,
   the call waits for the decision, and the decision resolves exactly one pending request through the
   Phase-1 Human Approval machinery.

---

### User Story 4 - Run the reference runner end-to-end as a deterministic smoke test (Priority: P4)

A developer runs the reference runner — or the minimal example runner that wraps it — against a
scripted scenario and gets a deterministic end-to-end result. A user request enters the Host
Application Interface, the Runtime Controller starts a run, the scripted model produces either
assistant text or a tool call, the Tool Gateway executes a test tool, the event bus emits ordered
events, and checkpoint and artifact behavior can be verified — all producing the same output every
time.

**Why this priority**: The reference runner is both the proof that the integration layer works and the
primary instrument for testing it. It depends on User Stories 1–3 producing the pieces it wires.

**Independent Test**: Can be fully tested by driving the reference runner against fixed scripted
scenarios and asserting on the deterministic event/outcome transcript, the recorded checkpoint, and
the retrievable artifact.

**Acceptance Scenarios**:

1. **Given** the reference runner and a scripted tool-using scenario, **When** the run executes,
   **Then** the full path — request, run start, model text or tool call, gateway tool execution,
   ordered events, single terminal event — completes and the transcript is identical on every run.
2. **Given** the reference runner configured with a checkpoint backend, **When** a run completes,
   **Then** the session's durable records can be inspected and assert the steps that occurred.
3. **Given** a test tool whose output exceeds the offload threshold, **When** the run records the
   result, **Then** the full output is preserved as an artifact and is retrievable by its reference,
   reusing the Phase-1 artifact guarantee.
4. **Given** the minimal example runner, **When** a developer runs it with the scripted model and no
   credentials or network access, **Then** it prints a deterministic event/outcome transcript suitable
   for an automated smoke test.

---

### User Story 5 - Embed LoopPlane from public-safe documentation and examples (Priority: P5)

A developer new to LoopPlane reads the embedding documentation and a runnable example, and embeds the
runtime in a host application using the configuration contract, the Host Application Interface, and
the reference runner — including consuming the event stream — with the scripted model and no
credentials. The documentation and example contain no references to private legacy material.

**Why this priority**: Documentation and a runnable example are what make the interface adoptable.
They depend on Stories 1–4 being real, and they are the last mile of "usable by host applications".

**Independent Test**: Can be fully tested by running the documented example as-is against the scripted
model and confirming it reproduces the documented output, and by scanning the example and docs for
private references.

**Acceptance Scenarios**:

1. **Given** the embedding documentation and example, **When** a developer follows them with the
   scripted model and no credentials, **Then** the example runs end-to-end and reproduces the
   documented event/outcome output.
2. **Given** the committed Phase-2 documentation and example, **When** an automated public-safety scan
   runs, **Then** it finds zero private references — internal paths, private project or repository
   names, network addresses, credentials — and zero raw reference-material excerpts.
3. **Given** the documentation, **When** a reader looks for the runtime internals, **Then** the docs
   point to the Phase-1 boundaries the integration layer depends on rather than restating them.

---

### Edge Cases

- A configuration selects a backend whose optional capability is not installed (for example external
  tool servers or the observability overlay): assembly fails fast with a clear, public-safe message
  naming the missing capability, never a raw import traceback, and a core run remains possible without
  it.
- A configuration registers two tools under the same name: assembly rejects the configuration with a
  deterministic naming-conflict error, consistent with the Phase-1 Tool Gateway naming rules.
- A configuration names no model provider: assembly rejects it — a model is mandatory for a run.
- A configuration selects a checkpoint backend but no artifact backend (or the reverse): the interface
  still wires consistently — artifact offload is enabled only when an artifact backend is present —
  without the host manually connecting the artifact handoff.
- A host-supplied event consumer raises while handling an event: the failure is isolated and surfaced
  as a diagnostic; session state and the ordering guarantees for well-behaved consumers are not
  corrupted.
- All optional subsystems are disabled in the configuration: the run's event sequence is identical to
  a run driven against the bare Phase-1 runtime, proving the integration layer adds zero behavior
  change.
- The minimal example runner is given an unknown argument or scenario: it exits with a clear,
  public-safe developer message rather than a stack trace, and remains a smoke-test tool rather than
  acquiring a product command surface.
- One configured interface is reused to start several sequential runs or sessions: each run is
  independent; no per-run state leaks across runs.
- A run is cancelled before the first model response arrives: it ends with a "cancelled" terminal
  event and leaves no stranded input, upholding the Phase-1 empty-turn guarantee.

## Requirements *(mandatory)*

### Functional Requirements

#### Host Application Interface

- **FR-001**: The runtime MUST expose a single documented Host Application Interface as the sanctioned
  way for an external application to assemble and run the Phase-1 runtime. The interface MUST be built
  on the Phase-1 public surface — session lifecycle, the Dispatcher round-trip channels, Tool Gateway
  registration, and the normalized Runtime Event Bus — and MUST NOT re-implement or offer a bypass of
  any Phase-1 runtime internal.
- **FR-002**: The interface MUST accept, from the host, the runtime's collaborators: user input, a
  model provider, a set of tools, and optionally a memory backend, a checkpoint store, an artifact
  store, and an approval handler. It MUST assemble these into a runnable runtime so that the host does
  not manually connect internal collaborators (for example, wiring the artifact handoff into the Tool
  Gateway).
- **FR-003**: The interface MUST let the host start a run from a user request and obtain that run's
  outcome — the terminal reason and a point-in-time history snapshot — through the interface, without
  reaching into Agent Loop internals.
- **FR-004**: The interface MUST let the host consume a run's normalized runtime events as an ordered
  stream through a host-supplied consumer, preserving the Phase-1 ordering guarantees; consumers MUST
  remain able to skip unknown or future event types (the Phase-1 tolerance rule is upheld, not
  redefined).
- **FR-005**: Assembly MUST validate the supplied configuration and fail fast — before any run starts
  — with a clear, public-safe error when the configuration is invalid, incomplete (for example, no
  model provider), or internally inconsistent (for example, duplicate tool names, or a selected
  capability that is unavailable).
- **FR-006**: One configured interface MUST support starting multiple independent runs or sessions in
  sequence with no state leakage between them; each run MUST remain independently deterministic.
- **FR-007**: A failure raised by a host-supplied event consumer MUST be isolated and surfaced as a
  diagnostic, without corrupting session state or the ordering guarantees seen by well-behaved
  consumers.
- **FR-008**: The Host Application Interface MUST NOT depend on any web, browser, desktop, or CLI host,
  transport, or UI framework, and MUST be usable from a plain host process (upholds Phase-1 portability).

#### Configuration Contract

- **FR-010**: The runtime MUST define a minimal, declarative Runtime Configuration that describes a
  run's composition: model provider selection, the tool registry, memory/checkpoint/artifact backend
  selection, and approval behavior.
- **FR-011**: The Runtime Configuration MUST be constructible programmatically in host code and from a
  plain in-memory mapping; no configuration-file format is required in this phase.
- **FR-012**: Every optional subsystem (memory, skills, external tools, observability, and durable
  checkpoint/artifact storage) MUST default to absent or off in the configuration, and a configuration
  that omits them MUST produce runtime behavior identical to the Phase-1 core loop (end-to-end
  zero-behavior-change gating).
- **FR-013**: The Runtime Configuration MUST be public-safe: it MUST carry no secrets, credentials,
  provider keys, or private paths. Credential material MUST be supplied out of band (for example, via
  the host-provided model provider object or the host's environment), never embedded in the
  configuration contract.
- **FR-014**: The configuration MUST express approval behavior at minimum sufficient to select
  allow / deny / ask per tool, delegating enforcement to the Phase-1 Human Approval boundary rather
  than re-implementing policy.
- **FR-015**: Invalid configuration values MUST be reported with a field-level, public-safe diagnostic.
  Where Phase-1 semantics already tolerate a malformed entry (for example, an individual tool or skill
  entry), a malformed optional entry MUST disable only that entry rather than failing the whole
  configuration.

#### Reference Runner

- **FR-020**: The phase MUST provide a Reference Runner that, given a Runtime Configuration, wires the
  Phase-1 runtime together, drives a run to completion, and emits the normalized event stream.
- **FR-021**: The Reference Runner MUST support the scripted model substitute as a first-class,
  credential-free model provider for deterministic runs.
- **FR-022**: The Reference Runner MUST support internal tool execution through the Phase-1 Tool
  Gateway, including at least one test tool sufficient to demonstrate a tool-calling run end-to-end.
- **FR-023**: Given identical scripted model behavior and identical tool outcomes, the Reference Runner
  MUST produce the same normalized event sequence and the same final outcome on every run, making it
  the primary smoke-test instrument (inherits Phase-1 determinism).
- **FR-024**: The Reference Runner MUST drive runs through the same assembly path as the Host
  Application Interface — it is a reference implementation and consumer of that interface, not a
  parallel wiring — so that smoke tests exercise the real embedding path.

#### Minimal Example Runner

- **FR-030**: The phase MUST provide a minimal, developer-focused local runner (an example entry point)
  that executes a scripted scenario through the Host Application Interface and reports the resulting
  event stream and outcome for smoke testing.
- **FR-031**: The minimal runner MUST stay developer-facing and intentionally minimal: it MUST NOT grow
  into a product CLI — no general command surface, packaging, configuration-file ingestion, or
  interactive product experience beyond what smoke testing requires.
- **FR-032**: The minimal runner MUST run with the scripted model and without credentials or network
  access, and MUST produce deterministic output suitable for an automated smoke test.
- **FR-033**: On invalid input or arguments, the minimal runner MUST fail with a clear, public-safe
  developer message rather than a raw traceback.

#### End-to-End Smoke Tests

- **FR-040**: An automated end-to-end smoke test MUST drive the full path: a user request enters the
  Host Application Interface, the Runtime Controller starts a run, the scripted model produces either
  assistant text or a tool call, the Tool Gateway executes a test tool, and the Runtime Event Bus emits
  ordered events ending with exactly one terminal event.
- **FR-041**: The smoke suite MUST assert deterministic output: the ordered event sequence and the
  final outcome are stable across repeated runs of the same scenario.
- **FR-042**: The smoke suite MUST verify checkpoint behavior (records appended for the run) and
  artifact behavior (an oversized tool result is offloaded and retrievable by reference) through the
  Host Application Interface, reusing the Phase-1 guarantees rather than re-testing Phase-1 internals.
- **FR-043**: The smoke suite MUST include a gating check: with all optional subsystems disabled, a run
  driven through the integration layer produces an event sequence identical to a run driven against the
  bare Phase-1 runtime.

#### Documentation & Examples

- **FR-050**: The phase MUST provide public-safe documentation showing how to embed LoopPlane in a host
  application using the Runtime Configuration, the Host Application Interface, and the Reference Runner,
  including how to consume the event stream.
- **FR-051**: At least one runnable example MUST demonstrate embedding end-to-end with the scripted
  model and no credentials.
- **FR-052**: All Phase-2 documentation and examples MUST be public-safe and MUST NOT reference raw
  private reference material, private legacy implementations, private paths or repository names,
  internal network addresses, or secrets.
- **FR-053**: The documentation MUST state that Phase 2 is a host-integration layer over the Phase-1
  foundation and MUST point to the Phase-1 boundaries it depends on, without duplicating Phase-1
  internal documentation.

#### Boundary & Non-Duplication

- **FR-060**: Phase 2 MUST NOT implement or duplicate any Phase-1 runtime internal — Agent Loop,
  Dispatcher round-trip mechanics, Tool Gateway pipeline, the event vocabulary, or the Memory,
  Checkpoint, Artifact Storage, Observability, and Human Approval internals. It MUST compose them only
  through their declared Phase-1 interfaces.
- **FR-061**: Phase 2 MUST NOT implement any out-of-scope host or automation layer — Web API host,
  browser frontend, desktop host, scheduler, validator, evaluator, auto-iteration loops, full
  human-in-the-loop workflow UI, plugin marketplace, multi-agent orchestration, sandbox execution,
  cost governance, or production deployment. Any such need discovered during implementation MUST be
  deferred to a future-phase specification.
- **FR-062**: Where Phase 2 needs a capability not present in Phase 1, it MUST add that capability as a
  host-side assembly or configuration concern above the Phase-1 boundaries, never by modifying Phase-1
  internal behavior.

### Non-Functional Requirements

- **NFR-001 (Phase-1 dependency)**: Phase 2 MUST build strictly on the completed Phase-1 runtime
  foundation and inherit its guarantees — deterministic event ordering, zero-overhead gating, privacy,
  portability, and lossless serialization — rather than re-stating or re-deriving them.
- **NFR-002 (Determinism)**: The Host Application Interface and Reference Runner MUST preserve Phase-1
  deterministic event ordering: identical scripted input yields an identical event sequence.
- **NFR-003 (Zero-behavior-change overlay)**: Adding the integration layer MUST NOT change Phase-1
  behavior when optional subsystems are off; a gated run through the interface MUST equal a bare
  Phase-1 run (operationalized by FR-012, FR-043, and SC-003).
- **NFR-004 (Public-safety)**: All committed Phase-2 artifacts — specification, configuration contract,
  runner, example, and documentation — MUST remain public-safe, and no secret MUST appear in any
  configuration object or committed file.
- **NFR-005 (Portability)**: The integration layer MUST remain free of any host, transport, or UI
  dependency and MUST run on mainstream desktop and server platforms, including Windows-style
  filesystem paths.
- **NFR-006 (Minimalism)**: The configuration contract and the minimal runner MUST stay minimal, with
  no speculative product surface, consistent with the constitution's "harness before loop automation"
  principle and surgical-scope discipline.

### Key Entities

- **Runtime Configuration**: The declarative, public-safe description of a run's composition — model
  provider selection, tool registry, optional memory/checkpoint/artifact backend selection, and
  approval behavior. Carries no secrets.
- **Host Application Interface**: The single documented seam an application uses to assemble, start,
  observe, and control a run over the Phase-1 runtime.
- **Reference Runner**: The minimal reference assembly that realizes the Host Application Interface,
  wiring Phase-1 components from a Runtime Configuration and driving runs with the scripted model and
  internal tools.
- **Event Consumer (host sink)**: The host-supplied receiver of the ordered normalized runtime-event
  stream for a run.
- **Approval Handler (host)**: The host-supplied responder to "ask" decisions, routed through the
  Phase-1 Human Approval boundary.
- **Run Outcome**: The terminal reason plus the final history snapshot returned to the host through the
  interface at the end of a run.
- **Minimal Example Runner**: The developer-focused local entry point that drives a scripted scenario
  through the interface for smoke testing.

These integration-layer entities reference Phase-1 entities — Session, Run Context, Runtime Event, Tool
Descriptor, Approval Request — without redefining them.

## Host Interface Boundaries

Component ownership for this phase (constitution Principle IV). The integration layer interacts with
the Phase-1 runtime only through its declared interfaces and normalized events — never through
reach-through internal access.

| Component | Owns | Must not |
|---|---|---|
| Host Application Interface | The documented embedding seam: assemble-from-configuration, start a run, expose the event stream, and offer the interactive round-trip | Re-implement or bypass any Phase-1 internal; depend on a web, browser, desktop, or CLI host or UI |
| Runtime Configuration | The minimal declarative composition contract and its validation | Carry secrets, credentials, or private paths; mandate a configuration-file format; encode provider internals |
| Reference Runner | Wiring Phase-1 components from a configuration; scripted-model and internal-tool runs; event emission | Provide a parallel wiring that diverges from the Host Application Interface; add product features |
| Minimal Example Runner | A developer smoke-test entry point over the interface | Become a product CLI (general commands, packaging, interactive product experience) |
| End-to-End Smoke Tests | Asserting the full deterministic path plus checkpoint/artifact behavior and gating equality | Re-test Phase-1 internals or assert against Agent Loop internals |
| Documentation & Examples | Public-safe embedding guidance and a runnable example | Reference raw private material or private legacy; duplicate Phase-1 internal documentation |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An external host application can assemble and run a complete tool-using conversation
  through the Host Application Interface with a single configured entry point and zero manual wiring of
  Phase-1 internal collaborators.
- **SC-002**: Running the same scripted scenario through the interface twice yields identical ordered
  event sequences and identical final outcomes (determinism), verified by the smoke suite.
- **SC-003**: With all optional subsystems disabled, a run through the interface produces an event
  sequence identical to a run against the bare Phase-1 runtime — proving the integration layer adds
  zero behavior change.
- **SC-004**: The end-to-end smoke test exercises request → interface → Runtime Controller → scripted
  model (both text and tool-call variants) → Tool Gateway test tool → ordered events → terminal event,
  and asserts checkpoint records and artifact retrieval — all through the interface.
- **SC-005**: 100% of invalid configurations in the test suite (missing model, duplicate tool names,
  unavailable capability) are rejected at assembly time with a clear, public-safe error before any run
  starts.
- **SC-006**: Automated public-safety scans of all committed Phase-2 artifacts (specification,
  configuration contract, runner, example, documentation) find zero private references — internal
  paths, private project or repository names, network addresses, credentials — and zero raw
  private-reference excerpts.
- **SC-007**: A developer new to LoopPlane can embed it end-to-end using only the Phase-2 example and
  documentation, with the scripted model and no credentials, and reproduce the documented output.
- **SC-008**: No Phase-2 artifact re-implements a Phase-1 runtime internal; a review confirms that
  Phase 2 composes Phase 1 only through its declared public surface (constitution Principles IV–VI
  upheld).

## In Scope *(this phase)*

- A Host Application Interface that assembles the Phase-1 runtime from a configuration, starts runs,
  supplies the runtime's collaborators, and exposes the event stream and interactive round-trip.
- A minimal, programmatic Runtime Configuration contract selecting model provider, tools, and
  memory/checkpoint/artifact backends plus approval behavior.
- A Reference Runner that wires the runtime from a configuration, supports the scripted model
  substitute and internal tool execution, and emits runtime events.
- A minimal developer-focused example runner for smoke testing.
- End-to-end smoke tests covering the full deterministic path, including checkpoint and artifact
  behavior and gating equality.
- Public-safe embedding documentation and a runnable example.

## Out of Scope *(this phase)*

- A full CLI product, a Web API host, a browser frontend, and a desktop host.
- A scheduler, validator, evaluator, auto-iteration loops, and any loop-engineering automation.
- A full human-in-the-loop workflow user interface, a plugin marketplace, multi-agent orchestration,
  sandboxed execution, cost governance, and production deployment.
- A configuration-file format and configuration loading from disk (the contract is a programmatic
  object this phase).
- Real model-provider integrations as a deliverable — the scripted model substitute is the phase-2
  instrument, consistent with Phase 1's separately validated real-model boundary.

## Assumptions

- Phase 2 depends on the completed Phase-1 runtime foundation
  ([`001-loopplane-runtime-foundation`](../001-loopplane-runtime-foundation/spec.md)) and consumes its
  public surface: session lifecycle, the Dispatcher round-trip channels, Tool Gateway registration, the
  normalized Runtime Event Bus, the checkpoint/artifact/memory backends, the Human Approval boundary,
  and the scripted model substitute.
- Phase-2 consumers are application and platform developers embedding the runtime programmatically; no
  end-user product host ships in this phase.
- The Runtime Configuration is a programmatic object constructible from a plain mapping; no
  configuration-file format is mandated this phase.
- Model credentials and real provider integrations are supplied out of band by the host; the scripted
  model substitute is the phase-2 deterministic instrument, consistent with Phase 1.
- The minimal example runner exists solely for smoke testing and developer demonstration; it is not a
  product CLI.
- The local filesystem storage from Phase 1 remains sufficient for the checkpoint and artifact backends
  a configuration may select; no external database is introduced.
- Specification and documentation artifacts are written in English, consistent with the Phase-1 specs.
- The local private reference directory remains untracked; it is not read, modified, or committed by
  this phase, and all Phase-2 artifacts contain only public-safe content (constitution Principles II
  and VII).
