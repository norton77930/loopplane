# Phase 1 Data Model: Loop Engineering Layer

**Feature**: `003-loopplane-loop-engineering-layer` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

This model defines the **outer-layer** entities only. It references — and never redefines — the
Phase-1/2 entities (Agent Run / Session, Runtime Event, Checkpoint record, Artifact, Approval Request,
`LoopPlaneHost`, `RuntimeConfig`, `RunOutcome`). All field types below are illustrative design intent
for the implementation phase, not code delivered by `/speckit.plan`. Everything is public-safe (no
secrets, paths, or private names) per FR-001 / NFR-004.

## Entity overview

```text
LoopDefinition (frozen, declarative)
 ├─ trigger:            Trigger              (ManualTrigger | IntervalTrigger | ConditionTrigger)
 ├─ input_source:       InputSource          (first-iteration prompt + repair augmentation)
 ├─ host_profile:       HostRuntimeProfile   (-> Phase-2 RuntimeConfig / host selector)
 ├─ validation_policy:  ValidationPolicy     (-> Validator)
 ├─ evaluation_policy:  EvaluationPolicy?    (optional -> Evaluator)
 ├─ retry_policy:       RetryPolicy
 ├─ repair_policy:      RepairPolicy
 ├─ stop_condition:     StopCondition        (predicate + hard max_iterations)
 ├─ artifact_policy:    ArtifactPolicy
 ├─ approval_policy:    ApprovalPolicy
 └─ observation_policy: ObservationPolicy

LoopRun  (one execution of a LoopDefinition)
 └─ LoopIteration[]  (each starts exactly one Agent Run via the Host Interface)

LoopState (in-process, references only)        LoopEvent[] (separate ordered stream)
ValidationResult / EvaluationResult            RunOutcome (Phase-2, referenced by session_id)
```

---

## 1. LoopDefinition  (FR-001 – FR-009)

The declarative, public-safe description of an outer loop. **Frozen**; carries no secrets and wires no
Phase-1 collaborator directly (FR-001, FR-002).

| Field | Type | Required | Notes |
|---|---|---|---|
| `loop_id` | `str` | yes | Stable identifier for the loop (FR-001). |
| `trigger` | `Trigger` | yes | `ManualTrigger` (executable) or an interval/condition **contract** (FR-001, FR-020–FR-022). |
| `input_source` | `InputSource` | yes | Supplies iteration-1 input; augmentable by repair context (FR-003). |
| `host_profile` | `HostRuntimeProfile` | yes | References a Phase-2 `RuntimeConfig` or a host-resolvable selector; never wires Phase-1 directly (FR-002). |
| `validation_policy` | `ValidationPolicy` | yes | Names the Validator applied each iteration (FR-004). |
| `evaluation_policy` | `EvaluationPolicy \| None` | no | Optional; absent ⇒ no evaluation step (FR-005, FR-042). |
| `retry_policy` | `RetryPolicy` | yes | Count + backoff contract; independent of repair (FR-006). |
| `repair_policy` | `RepairPolicy` | yes | Enablement + instruction source; independent of retry (FR-006). |
| `stop_condition` | `StopCondition` | yes | Testable predicate over Loop State **with** a termination bound (FR-007, FR-013). |
| `artifact_policy` | `ArtifactPolicy` | yes | Whether/how prior artifacts may be reused by reference (FR-008). |
| `approval_policy` | `ApprovalPolicy` | yes | When loop-level human review is required (FR-009, FR-082). |
| `observation_policy` | `ObservationPolicy` | yes | Whether Loop Events/metrics are emitted; **defaults off** (FR-009, NFR-005). |

**Validation rules**: `loop_id` non-empty; `host_profile` resolves to a buildable host; `stop_condition`
carries a finite `max_iterations ≥ 1` (FR-013); policies are internally consistent (e.g. an
`approval_policy` requiring review must allow the `needs_human_review` path). Invalid definitions are
rejected before any Loop Run starts (mirrors Phase-2 fail-fast).

### Supporting policy/value types

| Type | Shape (design intent) | Requirements |
|---|---|---|
| `InputSource` | `initial() -> Prompt`; immutable; repair builds a *new* prompt without mutating it | FR-003, FR-052 |
| `HostRuntimeProfile` | wraps a `RuntimeConfig` **or** a `Callable[[], LoopPlaneHost]` selector | FR-002, FR-080 |
| `ValidationPolicy` | `validator: Validator` | FR-004, FR-033 |
| `EvaluationPolicy` | `evaluator: Evaluator` | FR-040 |
| `RetryPolicy` | `max_retries: int (≥0)`, `backoff: BackoffContract` | FR-006, FR-051 |
| `RepairPolicy` | `enabled: bool`, `instruction_source: RepairInstructionSource` | FR-006, FR-052 |
| `ArtifactPolicy` | `reuse: bool` (reuse prior artifacts by reference only) | FR-008, FR-053 |
| `ApprovalPolicy` | `require_human_review_on: frozenset[ValidationStatus]`, `human_review_available: bool` | FR-009, FR-034, FR-082 |
| `ObservationPolicy` | `emit_loop_events: bool = False` | FR-009, NFR-005 |
| `BackoffContract` | `delays_seconds(attempt: int) -> float` (data only; no sleeping) | FR-051 |
| `RepairInstructionSource` | `instruction(context: RepairContext) -> str` | FR-052 |

---

## 2. Trigger  (FR-020 – FR-023)

A tagged set of trigger shapes. Only `ManualTrigger` is executable this phase.

| Type | Fields | Status | Requirements |
|---|---|---|---|
| `ManualTrigger` | *(none)* | **Implemented** — host calls the manual entry point | FR-020 |
| `IntervalTrigger` | `interval_seconds: float`, `start_immediately: bool` | **Contract only** (host driver enacts) | FR-021, FR-023 |
| `ConditionTrigger` | `predicate_ref: str` (host-supplied predicate identifier), `description: str` | **Contract only** (host driver enacts) | FR-022, FR-023 |

Interval/condition triggers carry **no scheduler state** and no background behavior; a host driver
turns a tick or a satisfied predicate into a call to the manual entry point (FR-023, SC-008).

---

## 3. LoopRun & LoopIteration  (FR-010 – FR-016)

Runtime concepts owned by the Loop Controller; not persisted.

**LoopRun** — one execution of a `LoopDefinition`: an ordered, bounded sequence of `LoopIteration`s
ending in exactly one terminal Loop Event (`loop_completed` | `loop_failed`) (FR-010, FR-074).

**LoopIteration** — one pass:

| Field | Type | Notes |
|---|---|---|
| `index` | `int` (1-based) | Iteration counter; bounded by `max_iterations` (FR-013). |
| `kind` | `Literal["initial", "retry", "repair"]` | Distinguishes the three input paths (FR-050). |
| `input` | `Prompt` | The exact input submitted through the Host Interface (FR-011, FR-052). |
| `run_ref` | `RunReference \| None` | The started Agent Run's `session_id` + terminal reason (None if no run started). |
| `validation` | `ValidationResult \| None` | Set after the Validator runs (FR-014). |
| `evaluation` | `EvaluationResult \| None` | Set only if an evaluation policy exists (FR-042). |
| `decision` | `NextAction` | `stop_success \| stop_failure \| retry \| repair \| human_review` (FR-014). |

`RunReference` = `{ session_id: str, termination_reason: str }` — the **only** run data Loop State keeps
(by reference, FR-061).

---

## 4. ValidationResult  (FR-030 – FR-034)

The Validator's single gating output.

| Field | Type | Notes |
|---|---|---|
| `status` | `ValidationStatus` | exactly one of `pass`, `fail`, `needs_repair`, `needs_human_review` (FR-030). |
| `reason` | `str \| None` | human-readable, public-safe (FR-031). |
| `metadata` | `Mapping[str, JSONValue]` | structured, consumable by repair (FR-052) and stop condition (FR-007) (FR-031). |

`ValidationStatus` is a closed enum. An **unrecognized status or a raised validator** does not produce a
`ValidationResult`; the controller takes the fail-safe path instead (FR-034).

Status → decision mapping (FR-032), applied by the controller:

| Status | Decision | Emitted after `validation_completed` |
|---|---|---|
| `pass` | stop-success *(unless the stop condition demands more iterations)* | `loop_completed` |
| `fail` | retry, or stop-failure when retries exhausted | `retry_scheduled` / `loop_failed` |
| `needs_repair` | repair | `repair_requested` |
| `needs_human_review` | request human review (pause) | `human_review_requested` |
| *raised / unknown* | fail-safe → human review, else `loop_failed` (never silent pass) | `human_review_requested` / `loop_failed` + diagnostic |

---

## 5. EvaluationResult  (FR-040 – FR-043)

The optional Evaluator's **non-gating** output.

| Field | Type | Notes |
|---|---|---|
| `score` | `float \| None` | numeric quality measure; readable by a stop condition (FR-007, US4). |
| `label` | `str \| None` | categorical quality label. |
| `reason` | `str \| None` | human-readable rationale. |
| `metadata` | `Mapping[str, JSONValue]` | structured detail. |

Evaluation **never** decides stop/retry/repair by itself (FR-041). An evaluator error is a non-fatal
diagnostic; the iteration proceeds on the validation result (FR-043).

---

## 6. LoopState  (FR-060 – FR-064)

The outer per-run record, **held in process**, referencing Phase-1/2 state only by id/reference.

| Field | Type | Notes |
|---|---|---|
| `loop_id` | `str` | from the definition (FR-060). |
| `loop_definition_id` | `str` | stable definition identity (FR-060). |
| `iteration_index` | `int` | current/last iteration (FR-060). |
| `run_refs` | `tuple[RunReference, ...]` | every Agent Run's `session_id` + reason, in order (FR-060, FR-061). |
| `latest_validation` | `ValidationResult \| None` | most recent gating result (FR-060). |
| `latest_evaluation` | `EvaluationResult \| None` | most recent evaluation, if any (FR-060). |
| `artifacts` | `tuple[ArtifactRef, ...]` | artifact **references** only — no bytes (FR-061). |
| `approval_status` | `ApprovalStatus` | `none \| pending \| approved \| rejected` (FR-060). |
| `stop_reason` | `str \| None` | terminal reason, set once at the end (FR-060). |

**Invariants**:
- Never copies or owns Run State, conversation history, or artifact bytes (FR-061, FR-063).
- Reconstructable by `reconstruct_state(events, outcomes)` from the ordered Loop Event stream plus the
  referenced run outcomes (FR-062, FR-073, SC-006).
- Durable persistence and loop resume are **reserved extension points**, not built (FR-064, FR-091).

`ArtifactRef` = `{ session_id: str, reference: str }` — resolvable only via
`host.retrieve_artifact(session_id, reference)` (FR-053, FR-083).

---

## 7. LoopEvent  (FR-070 – FR-075)

A loop-level lifecycle record on a stream **distinct** from Runtime Events (FR-070). Frozen; emitted in
deterministic per-loop order (FR-073, NFR-002).

**Common envelope fields** (every event, FR-072):

| Field | Type | Notes |
|---|---|---|
| `type` | `LoopEventType` | the event kind (closed-but-extensible vocabulary, FR-075). |
| `schema_version` | `str` | versioned, additive evolution (FR-075). |
| `sequence` | `int` | monotonic per Loop Run (FR-073). |
| `loop_id` | `str` | (FR-072). |
| `loop_definition_id` | `str` | (FR-072). |
| `iteration_index` | `int \| None` | where applicable (FR-072). |
| `session_id` | `str \| None` | correlation to the relevant Agent Run when one exists (FR-072). |
| `payload` | type-specific | e.g. validation status, backoff delay, evaluation score, diagnostic. |

**The ten required event types** (FR-071):

| Order (typical) | Type | Emitted when |
|---|---|---|
| 1 | `loop_started` | a Loop Run begins. |
| 2 | `loop_iteration_started` | an iteration starts (carries `kind`). |
| 3 | `loop_iteration_completed` | the iteration's Agent Run terminated and its outcome captured. |
| 4 | `validation_completed` | the Validator returned a result (carries `status`). |
| 5 | `evaluation_completed` | an Evaluator returned a result (**only** when a policy exists, FR-042). |
| — | `repair_requested` | a `needs_repair` result triggers a repair iteration. |
| — | `retry_scheduled` | a `fail` schedules a retry (carries the backoff delay). |
| — | `human_review_requested` | a `needs_human_review` (or fail-safe) pauses the loop. |
| terminal | `loop_completed` | the Loop Run ends successfully. |
| terminal | `loop_failed` | the Loop Run ends in failure. |

**Guarantees**: exactly one terminal event per Loop Run (FR-074); the ordered stream alone reconstructs
decisions and Loop State (FR-073, SC-006); consumers tolerate unknown future types (FR-075).

---

## 8. Referenced Phase-1/2 entities (not redefined)

| Entity | Source | Referenced as |
|---|---|---|
| Agent Run / Session | Phase-1 runtime via Phase-2 host | `session_id` (string reference) |
| `RunOutcome` | Phase-2 `loopplane.host` | per-iteration runtime outcome (read-only) |
| Runtime Event / `TerminationReason` | Phase-1 `loopplane.events` | consumed through `host.run(on_event=...)`; terminal reason maps the iteration |
| Checkpoint record | Phase-1 checkpoint store | reference only, via host (FR-054) |
| Artifact | Phase-1 artifact store | `ArtifactRef`, via `host.retrieve_artifact` (FR-053) |
| Approval Request | Phase-1 approval boundary | surfaced by host `on_approval`; not re-implemented (FR-082) |

## State transitions (Loop Run lifecycle)

```text
        start                 each iteration                     terminal
  ─────────────►  loop_started ─► iteration ──► validation ──►  decision ──► (loop_completed | loop_failed)
                                     │              │                │
                                     │              │  pass ─────────┘ (stop_success, if stop_condition met)
                                     │              │  fail ────────► retry (≤ max_retries) ──► else loop_failed
                                     │              │  needs_repair ► repair iteration
                                     │              │  needs_human_review / fault ► human_review_requested (paused)
                                     │              └─ evaluation_completed (optional, non-gating)
                                     └─ max_iterations bound checked BEFORE every iteration (FR-013)
```

Every path is bounded: the hard `max_iterations` check precedes each iteration, so no Loop Run loops
unbounded and every Loop Run reaches exactly one terminal Loop Event (FR-013, FR-056, FR-074, SC-007).
