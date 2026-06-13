# Phase 0 Research: Loop Engineering Layer

**Feature**: `003-loopplane-loop-engineering-layer` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md)

This phase has **no `[NEEDS CLARIFICATION]` markers** — the spec resolved every open question before
authoring (see [checklists/requirements.md](./checklists/requirements.md) notes). Phase 0 therefore
records the *design decisions* that turn the spec's contracts into an implementable layer, plus the
best-practice patterns inherited from Phases 1 and 2. Each decision cites the spec requirements it
satisfies and the alternatives rejected.

## Inherited context (no re-derivation — NFR-001)

The layer builds strictly on the merged Phase-1 runtime foundation and Phase-2 Host Interface. The
**only** Phase-2 surface the loop layer consumes:

| Phase-2 public surface | How the loop layer uses it |
|---|---|
| `LoopPlaneHost(config, *, working_scope=)` | The host facade a Loop Definition references; the Loop Controller owns one instance per Loop Run and starts every Agent Run through it (FR-002, FR-080). |
| `await host.run(prompt, on_event, *, on_approval=, working_scope=) -> RunOutcome` | The single call that starts one Agent Run for an iteration and returns its terminal outcome (FR-011, FR-080). |
| `RunOutcome(session_id, termination_reason, turns_taken, history, consumer_failures)` | The opaque per-iteration runtime outcome; the loop reads `session_id` (run reference) and `termination_reason` (terminal reason) only (FR-012, FR-083). |
| `EventSink = Callable[[RuntimeEvent], Awaitable[None]]` (the `on_event` arg) | The normalized event stream the loop subscribes to *through the host*; it never attaches to the Phase-1 bus (FR-012, FR-081). |
| `loopplane.events.RuntimeEvent` + `TerminationReason` + `RunTerminatedEvent` | The terminal Runtime Event whose reason drives the iteration outcome mapping (FR-016). |
| `host.history_snapshot(session_id)` / `host.retrieve_artifact(session_id, ref)` | Reference-only access to run history and artifacts for Loop State and repair reuse (FR-061, FR-053, FR-083). |
| `ApprovalRequestedPayload` / `ApprovalDecision` / `on_approval` | In-run tool approval stays on the Phase-1 boundary, surfaced by the host; the loop does not re-implement it (FR-082). |

**Non-duplication (FR-090)**: every Agent Loop / Runtime Controller / Dispatcher / Tool Gateway / Event
Bus / Memory / Checkpoint / Artifact / Observability / Approval concern is reused verbatim through the
host. The loop layer adds only outer-loop control above that boundary.

---

## Decision 1 — Run invocation goes exclusively through `LoopPlaneHost`

- **Decision**: The Loop Controller starts each Agent Run with `await host.run(prompt, on_event, ...)`
  and treats the returned `RunOutcome` as the iteration's runtime outcome. The host is supplied by the
  **host runtime profile** on the Loop Definition (a Phase-2 `RuntimeConfig` or a host-resolvable
  selector that builds a `LoopPlaneHost`).
- **Rationale**: Satisfies FR-002, FR-011, FR-080–FR-083, NFR-003, SC-002 directly: there is exactly
  one path to start, drive, and observe a run, and it is auditable. Reusing `RunOutcome` means the loop
  never reaches into Agent Loop internals to learn the result (FR-003 reuse).
- **Alternatives rejected**:
  - *Call `RuntimeController` directly* — violates FR-080/FR-090 and the boundary audit (SC-002).
  - *Use the interactive `host.session(...)` round-trip per iteration* — heavier than needed; one-shot
    `host.run` is the minimal call for a single Agent Run. `session` remains available for hosts that
    drive human-review resume, but the loop's default path is `run`.

## Decision 2 — Loop Event stream is a separate, in-process emitter

- **Decision**: Loop Events are emitted on a dedicated `LoopEventSink =
  Callable[[LoopEvent], Awaitable[None]]`, structurally parallel to the Phase-1 `EventSink` but a
  **distinct stream**. Loop Events reference Agent Runs by `session_id` and never wrap, re-emit, or
  replace Runtime Events (FR-070). A monotonically increasing per-loop `sequence` field plus a frozen
  event dataclass family give deterministic ordering (FR-073, NFR-002).
- **Rationale**: Mirrors the Phase-1 Runtime Event Bus discipline (Constitution VI) without coupling the
  two streams. Keeping the emitter in-process matches "single in-process Loop Run" scope (FR-091) and
  the default-off observation policy (FR-009, NFR-005): when observation is off, no sink is attached and
  decisions are identical (SC-009).
- **Alternatives rejected**:
  - *Re-use the Phase-1 `EventEmitter`/bus for loop events* — would blur the inner/outer boundary
    (distinction 3) and risk re-emitting Runtime Events. Rejected per FR-070.
  - *Synchronous callbacks* — the host event path is async; an async sink keeps one concurrency model.

## Decision 3 — Loop State is in-process and reconstructable from the event stream

- **Decision**: `LoopState` is a mutable in-process record the controller updates each iteration; it
  holds only **references** (`session_id`s, artifact references, checkpoint references) plus the latest
  validation/evaluation results, approval status, and the terminal stop reason (FR-060, FR-061). A pure
  function `reconstruct_state(events, outcomes) -> LoopState` rebuilds it from the ordered Loop Event
  stream and the referenced run outcomes, proving event-sufficiency (FR-062, FR-073, SC-006).
- **Rationale**: Satisfies the "reconstructable, not persisted" requirement (FR-062) and keeps Loop
  State distinct from Run State (FR-063). Durable persistence and loop resume are named extension points
  only (FR-064, FR-091).
- **Alternatives rejected**:
  - *Persist Loop State to disk this phase* — out of scope (FR-064, FR-092); the Checkpoint store stays
    the runtime's, not the loop's.
  - *Copy run history into Loop State* — forbidden by FR-061/FR-063; references only.

## Decision 4 — Validator and Evaluator are host-supplied policy callables

- **Decision**: A `Validator` is a callable
  `(RunOutcome, LoopState) -> ValidationResult | Awaitable[ValidationResult]` returning exactly one
  status in `{pass, fail, needs_repair, needs_human_review}` with optional `reason`/`metadata`
  (FR-030, FR-031). An `Evaluator` is an optional callable
  `(RunOutcome, LoopState) -> EvaluationResult | Awaitable[EvaluationResult]` producing non-gating
  `score`/`label`/`reason`/`metadata` (FR-040). Both are referenced by the validation/evaluation policy
  on the Loop Definition; the layer hardcodes no domain logic (FR-033).
- **Rationale**: Keeps validation/evaluation as policy boundaries (FR-033, FR-041) and makes them
  trivially scriptable for deterministic tests (NFR-002, SC-003). Accepting sync *or* async keeps simple
  validators ergonomic while supporting host I/O.
- **Alternatives rejected**:
  - *A Validator base class with abstract methods* — heavier than a callable for a one-method contract;
    a `Protocol` documents the shape without forcing inheritance (matches Phase-1/2 seam style).
  - *Let the Evaluator gate control flow* — forbidden by FR-041; only the stop condition or a Validator
    may consume evaluation output.

## Decision 5 — Fail-safe handling for validator faults

- **Decision**: If the Validator raises or returns an unrecognized status, the controller routes the
  iteration to human review by default, or to `loop_failed` when the approval policy makes human review
  unavailable, always emitting a `diagnostic`-bearing Loop Event — never a silent `pass` (FR-034,
  SC-003, edge cases).
- **Rationale**: Directly encodes the spec's fail-safe rule and the "never silent pass" guarantee.
- **Alternatives rejected**: *Treat an exception as `fail` and retry* — could mask a broken validator
  and burn the retry budget; the spec mandates fail-safe-to-review, not retry.

## Decision 6 — Retry vs Repair kept structurally distinct

- **Decision**: **Retry** re-submits the *same* iteration input after `fail` (no instruction change),
  bounded by `RetryPolicy(max_retries, backoff)`; the controller emits `retry_scheduled` carrying the
  contracted delay but performs **no in-process sleeping** (the backoff is a contract a host may enact)
  (FR-050, FR-051, FR-055). **Repair** re-submits after `needs_repair` with an *intentionally changed*
  input built by `build_repair_input(original_input, prior_outcome_ref, validation_reason, metadata,
  reused_artifacts)`, leaving the original Loop Definition unmutated (FR-052). The checkpoint
  reuse-or-reset decision is explicit and defaults to **reset / fresh run** (FR-054).
- **Rationale**: Operationalizes Core Distinction 6 and FR-050–FR-056 as two separate code paths so the
  distinction is testable (SC-004, SC-005). No sleeping scheduler keeps the phase scope honest (FR-091,
  no production scheduler).
- **Alternatives rejected**:
  - *Fold retry into repair with an empty instruction* — erases the distinction the phase exists to
    enforce; rejected.
  - *Sleep on the backoff in-process* — would introduce a runtime scheduler (FR-023, FR-091); the delay
    is surfaced as data on `retry_scheduled` instead.

## Decision 7 — Triggers: implement manual, define interval/condition as contracts

- **Decision**: `ManualTrigger` is the only executable trigger — a host calls `run_loop(definition)` (or
  `controller.start(definition)`) to start exactly one Loop Run (FR-020). `IntervalTrigger` and
  `ConditionTrigger` are **frozen contract dataclasses** describing inputs/semantics; a host-supplied
  driver enacts a tick or a satisfied predicate and starts the Loop Run through the *same* manual entry
  point (FR-021, FR-022, FR-023, SC-008). No scheduler, watcher, queue worker, or daemon is built
  (FR-023, FR-092).
- **Rationale**: Matches the "contracts, not scheduler" scope exactly and makes SC-008 testable with a
  plain in-test driver that calls the manual entry point.
- **Alternatives rejected**: *A minimal `asyncio` interval loop* — still a scheduler; explicitly out of
  scope this phase (FR-023).

## Decision 8 — Stop condition is a bounded predicate over Loop State

- **Decision**: A `StopCondition` is a callable `(LoopState) -> StopDecision` (stop yes/no + reason)
  combined with a mandatory hard `max_iterations` bound enforced by the controller regardless of the
  predicate (FR-007, FR-013). Common conditions ship as small constructors: `stop_on_pass()`,
  `max_iterations(n)`, `stop_when_score_at_least(threshold)` (FR-007, US4). The controller checks the
  bound first so no Loop Run is unbounded (FR-013, FR-056, SC-007).
- **Rationale**: Guarantees termination (SC-007) while letting evaluation-driven stopping read the score
  from Loop State (FR-041, US4 scenario 1).
- **Alternatives rejected**: *Predicate-only stop with no bound* — could loop forever if the predicate
  never holds (spec edge case); the hard bound is mandatory.

## Decision 9 — Iteration outcome mapping for non-natural terminations

- **Decision**: When `RunOutcome.termination_reason` is not natural completion (turn budget exhausted,
  cancelled, or unrecoverable error per Phase-1 `TerminationReason`), the controller maps it to a failed
  iteration subject to the retry policy by default, not a loop crash (FR-016, edge case). The validator
  still runs when an outcome exists; a missing/aborted run short-circuits to the failed-iteration path.
- **Rationale**: Keeps the loop resilient to inner-run faults and routes them through the existing
  retry/stop machinery rather than a separate crash path.
- **Alternatives rejected**: *Abort the Loop Run on any non-natural reason* — too brittle; the retry
  policy is exactly the mechanism for transient inner failures.

## Decision 10 — Observation defaults off with zero behavior change

- **Decision**: The observation policy defaults off; with it off, the controller attaches no Loop Event
  sink and skips emission work, while decisions and the terminal outcome are byte-identical to an
  observed run (FR-009, NFR-005, SC-009). Loop Events are always *computed* for control flow internally;
  observation only governs whether they are *emitted* to an external sink.
- **Rationale**: Mirrors Phase-1 Observability parity and makes SC-009 a direct equality test.
- **Alternatives rejected**: *Always emit* — would make observation non-optional and could change timing
  for consumers; rejected per NFR-005.

---

## Best-practice patterns reused from Phases 1–2

- **Frozen dataclasses + `Protocol` seams** for public contracts (Loop Definition, policies, results),
  matching `loopplane.host` config style; mutable state (`LoopState`) is the single exception and is
  controller-owned.
- **`ScriptedModel` + scripted validators/evaluators** as the deterministic test instruments
  (NFR-002, SC-003) — no credentials, no network.
- **Versioned, additively-evolving event vocabulary** with a `SCHEMA_VERSION` constant and unknown-type
  tolerance, mirroring `loopplane.events.SCHEMA_VERSION` (FR-075).
- **Public-safety scan extension**: add the new Phase-3 files to the existing committed scan test
  (`tests/contract/test_public_safety.py`) so SC-010 is enforced in CI (NFR-004).
- **One package per boundary**: a single new `loopplane.engineering` sub-package, additive and
  independently revertible (Constitution IV, X).

## Open risks carried into design (not blockers)

| Risk | Handling in Phase 1 design |
|---|---|
| Loop layer accidentally reaching into Phase-1 internals | A boundary-audit test asserts the loop module imports only `loopplane.host` (+ `loopplane.events`/`loopplane.model` value types), never controller/gateway/loop internals (NFR-003, SC-002). |
| Retry/repair causing unbounded loops | Hard `max_iterations` checked before every iteration (FR-013, FR-056); a dedicated never-satisfied-stop test asserts termination (SC-007). |
| Evaluator error aborting the run | Evaluator wrapped so an exception becomes a non-fatal diagnostic; the iteration proceeds on the validation result (FR-043, edge case). |
| A secret leaking through a Loop Definition | Loop Definition carries no secrets by contract; host/model hold any credentials; public-safety scan over committed files (NFR-004, SC-010). |

**Output**: all design unknowns resolved; ready for Phase 1 (`data-model.md`, `contracts/`,
`quickstart.md`).
