# Feature Specification: LoopPlane Dynamic Subagents (model-driven one-shot spawning)

**Feature Branch**: `043-dynamic-subagents` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "A Tier-2 autonomy primitive: a model-driven `spawn_subagent`
gateway tool that runs a ONE-SHOT child subagent through the EXISTING unit-013 orchestration /
`run_loop` (do NOT rewrite the agent loop) and returns the child's final text to the parent. Additive,
reuse-first, and SAFE: a HARD recursion-depth cap (an additive `RunContext.subagent_depth` + a
configurable `RuntimeConfig.max_subagent_depth`; deny beyond it — fail-safe, no unbounded nesting); a
child failure is contained (the parent continues); the child's events reuse 013's metadata-only
aggregation and never corrupt the parent's live event bus (Constitution VI). Enforced at the Gateway
(Constitution V). Agent-to-agent messaging, Swarm / peer coordination, and persistent / named /
background subagents are OUT OF SCOPE (deferred). Deterministic, public-safe, offline,
in-process-testable, English."

## User Scenarios & Testing *(mandatory)*

Today LoopPlane orchestrates subagents only **host-driven** (unit 013: a registry + a coordinator the
**host** invokes). This unit adds the **model-driven** primitive both reference harnesses expose
(claude-code's `Agent`, orion's `SubAgentCreate`): the model itself decides to delegate a focused
sub-task, the runtime runs **one** bounded child agent to completion, and the child's final answer comes
back to the parent as a tool result. The child is **one-shot** — it runs and returns; there is no
persistent handle, no peer messaging, no swarm. It is additive over the public Phase-3 loop surface and
the existing Tool Gateway: it adds no agent-loop behavior of its own.

### User Story 1 - The model delegates a focused sub-task (Priority: P1)

While working a task, the parent agent calls `spawn_subagent` with a `task` prompt; the runtime runs
exactly one bounded child agent to completion through the existing Phase-3 entry point and returns the
child's final assistant text as the tool's result, so the parent can use it and continue.

**Why this priority**: A model-driven one-shot subagent is the whole feature; everything else (the
depth cap, failure containment, the restricted toolset) guards or scopes it.

**Independent Test**: Script a parent model that calls `spawn_subagent({"task": "..."})` then emits a
final answer; script the child model to produce a known text. Assert the parent's `spawn_subagent` tool
result carries the child's known text and the run completes naturally.

**Acceptance Scenarios**:

1. **Given** a runtime with subagent spawning enabled, **When** the model calls `spawn_subagent` with a
   `task`, **Then** exactly one child agent run is driven through the existing Phase-3 `run_loop` and the
   child's final assistant text is returned to the parent as a successful tool result.
2. **Given** the child completes naturally, **When** the parent receives the result, **Then** the result
   is the child's final assistant message text (not its intermediate steps, tool I/O, or events).
3. **Given** the call, **When** it runs, **Then** it traverses the **full Tool Gateway pipeline** like
   any other tool (resolve, validate, decide, execute-under-timeout, normalize) — there is no bypass.

### User Story 2 - Bounded recursion: a hard depth cap (Priority: P1)

A spawned child may itself try to spawn; the runtime caps the nesting depth so subagents can never
recurse without bound. At or beyond the configured maximum depth, `spawn_subagent` is **denied** with a
normalized error and **no child run is started**.

**Why this priority**: Unbounded self-spawning is the safety failure mode of this primitive (a fork
bomb of agent runs). The cap is non-negotiable and fail-safe (Constitution III — loop automation stays
bounded; X — testable, reversible).

**Independent Test**: Run a parent at `subagent_depth` equal to `max_subagent_depth`; script its model
to call `spawn_subagent`. Assert the tool result is a normalized error (a denial), assert no child loop
run was driven, and assert the parent run continues.

**Acceptance Scenarios**:

1. **Given** a run whose `subagent_depth >= max_subagent_depth`, **When** the model calls
   `spawn_subagent`, **Then** the call is denied with a normalized error result and **no** child agent
   run is started.
2. **Given** a child spawned from a parent at depth `d`, **When** the child runs, **Then** the child's
   run context has `subagent_depth == d + 1`, so its own spawn attempts are capped one level deeper.
3. **Given** a runtime with `max_subagent_depth = 1`, **When** a top-level run spawns a child, **Then**
   the child runs at depth 1 and cannot spawn a grandchild (one level only).

### User Story 3 - A failing child is contained (Priority: P2)

A child that errors, fails validation, over-runs its bound, or produces no answer does not crash the
parent: the parent receives a normalized error tool result and continues.

**Why this priority**: Real sub-tasks fail; an uncontained child failure would take down the parent
run. This mirrors unit 013's fail-safe coordinator.

**Independent Test**: Script a child whose model raises (or whose loop fails). Assert the parent's
`spawn_subagent` result is a normalized error, the parent run does not crash, and the parent can take a
subsequent turn.

**Acceptance Scenarios**:

1. **Given** a child whose loop run raises or terminates non-naturally, **When** the parent spawns it,
   **Then** the parent receives a normalized error result (a public-safe marker, never a raw exception
   or stack trace) and the parent run continues.
2. **Given** a child that completes but produces no assistant text, **When** the parent spawns it,
   **Then** the parent receives a clear normalized result, never a crash.
3. **Given** a child that over-runs, **When** it exceeds the bound, **Then** the gateway's existing
   per-call time limit and the loop's one-iteration bound contain it as a normalized error.

### User Story 4 - A restricted child toolset (Priority: P3)

The parent may optionally restrict the child's tools to a named allowlist, so a delegated sub-task runs
with least privilege (e.g. a read-only researcher).

**Why this priority**: Least-privilege delegation is a useful, additive safety affordance; it is
strictly optional and does not change the default behavior.

**Independent Test**: Spawn a child with `allowed_tools=["read_file"]`; assert the child's runtime
registers only the allowlisted tool(s) (plus `spawn_subagent` is **never** re-granted unless explicitly
allowed and depth permits), and an attempt by the child to use a non-allowlisted tool is denied at the
child's gateway.

**Acceptance Scenarios**:

1. **Given** a `spawn_subagent` call with `allowed_tools`, **When** the child runs, **Then** the child's
   tool set is the intersection of the parent's tools and the allowlist; tools outside the allowlist are
   absent from the child runtime.
2. **Given** no `allowed_tools`, **When** the child runs, **Then** the child inherits the parent's tool
   set (the default), still subject to the depth cap on its own `spawn_subagent`.

### Edge Cases

- **Depth at/over the cap**: denied with a normalized error; **no** child run started (US2).
- **Disabled (the default)**: `max_subagent_depth` defaults to `0`, so the tool is not registered at all
  and the model cannot call it — a runtime that does not opt in is byte-identical to today. A host sets
  `max_subagent_depth = 1` to enable exactly one level.
- **Child raises / fails validation / non-natural termination / empty answer**: a normalized error or a
  clear result to the parent, never a crash (US3).
- **Child over-runs**: bounded by the gateway per-call time limit and the one-iteration child loop.
- **Live event bus**: the child's events are **captured** in its loop outcome and surfaced as
  metadata-only aggregation; they are **never** re-emitted onto the parent's live event bus
  (Constitution VI).
- **Empty / missing `task`**: schema validation at the gateway rejects it before any run (a normalized
  validation error).

## Requirements *(mandatory)*

### Functional Requirements

**Model-driven one-shot spawn (US1)**

- **FR-001**: The runtime MUST expose a `spawn_subagent` tool through the Tool Gateway whose input is a
  required `task` string (a natural-language sub-task) and an optional `allowed_tools` array of tool
  names.
- **FR-002**: Invoking `spawn_subagent` MUST run exactly **one** bounded child agent run to completion
  through the **existing** public Phase-3 loop entry point (`loopplane.engineering.run_loop`); it MUST
  NOT re-implement, fork, or modify the agent loop, and MUST NOT reach past the public loop surface to a
  Phase-1 internal to drive the child.
- **FR-003**: On a child that completes naturally, the tool MUST return the child's **final assistant
  text** as a successful tool result (a `TextBlock`); intermediate steps, tool I/O, and events MUST NOT
  be returned.
- **FR-004**: The call MUST traverse the full Tool Gateway pipeline (resolve, validate, decide, execute
  under the per-call time limit, normalize, size-manage) like any other tool — there is no privileged
  bypass (Constitution V).

**Bounded recursion — the hard depth cap (US2)**

- **FR-010**: The run context MUST carry an additive `subagent_depth` (default `0` for a top-level run).
  A child run's context MUST have `subagent_depth = parent.subagent_depth + 1`.
- **FR-011**: The runtime MUST carry a configurable maximum subagent depth (`RuntimeConfig
  .max_subagent_depth`, default `0` = off; a host sets a small value like `1` to enable). When
  `context.subagent_depth >= max_subagent_depth`, `spawn_subagent` MUST **deny** the call with a
  normalized error and **MUST NOT** start any child run (fail-safe; no unbounded nesting).
- **FR-012**: With `max_subagent_depth = 0` the `spawn_subagent` tool MUST NOT be registered (the model
  cannot call it), so a runtime can opt out entirely; the default-off behavior for any runtime that does
  not set the field is unchanged from today (the tool is simply absent).

**Failure containment (US3)**

- **FR-020**: A child whose loop run raises, fails validation, terminates non-naturally, pauses for
  review, or produces no assistant text MUST be contained: the parent receives a **normalized** error or
  a clear result (a public-safe marker, never a raw exception, stack trace, secret, or private path) and
  the parent run continues. A child failure MUST NEVER crash the parent run.

**Events & artifacts (Constitution VI)**

- **FR-030**: The child's events MUST be **captured** from its loop outcome and surfaced only as
  metadata-only aggregation (reusing unit 013's `aggregate_events`); the child's events MUST NOT be
  re-emitted, wrapped, or replayed onto the parent's live event bus.

**Restricted child toolset (US4)**

- **FR-040**: When `allowed_tools` is supplied, the child's tool set MUST be the intersection of the
  parent's configured tools and the allowlist; tools outside the allowlist MUST be absent from the child
  runtime. When `allowed_tools` is omitted, the child inherits the parent's tool set.

### Non-Functional Requirements

- **NFR-001 (Reuse / no loop rewrite — Constitution IV)**: The child run MUST be driven only through the
  existing public Phase-3 `run_loop`; this unit adds **no** agent-loop, controller, or gateway behavior.
  The agent loop, the orchestration core (`loopplane.orchestration`), the gateway pipeline, the event
  schema, and the content model MUST be unchanged.
- **NFR-002 (Gateway ownership — Constitution V)**: `spawn_subagent` MUST be reachable only through the
  Tool Gateway, and every error crossing the boundary MUST be normalized into the gateway error model.
- **NFR-003 (Event-bus ownership — Constitution VI)**: The child's loop events MUST be consumed as
  captured metadata (no live sink passed to the child run); the parent's live event bus MUST be
  uncorrupted.
- **NFR-004 (Bounded automation — Constitution III)**: Spawning MUST stay a single bounded one-shot,
  opt-in primitive under a hard depth cap; it MUST NOT introduce autonomous multi-agent swarms, peer
  messaging, or background/persistent subagents.
- **NFR-005 (Fail-safe)**: A child failure, a denied (capped) spawn, an empty answer, or a malformed
  input MUST map to an explicit, safe, normalized result — never a crash, hang, or unbounded recursion.
- **NFR-006 (Public-safe / offline / deterministic)**: All results and tests MUST be English and
  public-safe (no secrets, private paths, internal names, IPs, or raw exceptions), produced offline; the
  tests run in-process with `ScriptedModel` for both parent and child.
- **NFR-007 (Additive config & rollback)**: Both new config knobs are additive with safe defaults;
  setting `max_subagent_depth = 0` (or simply not opting in) fully disables the feature, which is the
  rollback path.

### Key Entities *(include if data involved)*

- **`spawn_subagent` tool**: a gateway tool taking a `task` string and an optional `allowed_tools`
  list; it runs one bounded child and returns the child's final text.
- **Subagent depth**: an additive per-run integer on the run context (`subagent_depth`, default `0`),
  incremented by one for a child run; the cap (`max_subagent_depth`) is compared against it.
- **Child run**: a one-shot Phase-3 loop run (a single-iteration `LoopDefinition` over the parent's
  model and a depth-incremented child runtime), driven through `run_loop`, returning a captured outcome.
- **Child result**: the child's final assistant text on success, or a normalized error on failure /
  denial.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A scripted parent that calls `spawn_subagent` receives, as the tool result, the scripted
  child's final assistant text — entirely in-process, with the child driven through the existing
  `run_loop`.
- **SC-002**: A spawn at or beyond `max_subagent_depth` is denied with a normalized error and starts
  **zero** child runs; a test proves no unbounded nesting (the depth cap holds).
- **SC-003**: 100% of failing-child / denied-spawn / empty-answer / malformed-input cases return an
  explicit, normalized, public-safe result — never a crash, hang, or leaked exception/secret.
- **SC-004**: The agent loop, the orchestration core, the gateway pipeline, the event schema, and the
  content model are unchanged (no `SCHEMA_VERSION` bump); the only runtime additions are the additive
  `RunContext.subagent_depth`, `RuntimeConfig.max_subagent_depth`, the new tool adapter, and the
  controller's defaulted depth pass-through.
- **SC-005**: Across the test corpus, 0 child events are re-emitted onto the parent's live event bus;
  the child's events are surfaced only as metadata-only aggregation.

## Assumptions

- A **child run is one bounded Phase-3 loop run** built over the parent's model and a depth-incremented
  child runtime, driven through the public `run_loop` — the same entry point unit 013's coordinator
  composes. This unit adds no new public contract to Phase-3.
- The **final assistant text** is recovered from the child host's history snapshot for the child run's
  session (the public host surface), so no change to the Phase-3 `LoopOutcome` is needed.
- The depth guard is enforced **at the Tool Gateway boundary** (inside the `spawn_subagent` adapter,
  reading the per-run `RunContext.subagent_depth` the gateway already passes to every tool), consistent
  with how plan mode (038) and the permission DSL (039) enforce at the decide/tool boundary.
- The child's events are **consumed as captured metadata** (no live sink), exactly as unit 013 does, so
  the parent's live event bus is never touched.

### Reserved extension points (named, not built)

- Agent-to-agent messaging / a negotiation protocol between subagents.
- Swarm / peer coordination and load-balanced subagent pools.
- Persistent, named, or background subagents (a long-lived handle the parent can poll or resume).
- Streaming a child's live events to the parent (beyond the captured metadata-only aggregation).
- Distributed / cross-host subagent execution.
