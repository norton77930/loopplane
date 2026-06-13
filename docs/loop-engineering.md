# Loop Engineering Layer

The **loop-engineering layer** (`loopplane.engineering`) is LoopPlane's outer
control loop. It wraps agent runs: it defines a loop, triggers it, starts each
Agent Run **through the Phase-2 Host Application Interface**, validates the
outcome, optionally evaluates it, and decides whether to stop, retry, repair, or
request human review — under a hard iteration bound — until a single terminal
outcome.

It adds **no runtime internals of its own**. Every Agent Run is started and
observed through [`loopplane.host`](./embedding-host.md); the layer never reaches
into Phase-1 components. This guide points at the boundaries rather than
restating runtime internals.

> **Inner vs outer.** The Phase-1 *Agent Loop* (`loopplane.loop`) drives one
> governed run of a session. The Phase-3 *Loop Controller* drives a **Loop Run**:
> an ordered sequence of **Loop Iterations**, each of which starts exactly one
> Agent Run through the host. They are distinct layers — the loop layer sits
> beside, not inside, the runtime.

## A first loop

```python
from loopplane.engineering import (
    HostRuntimeProfile, LoopDefinition, ManualTrigger, StaticInput,
    ValidationPolicy, ValidationResult, run_loop, stop_on_pass,
)
from loopplane.host import RuntimeConfig

def always_pass(outcome, state) -> ValidationResult:
    return ValidationResult(status="pass")

definition = LoopDefinition(
    loop_id="echo-once",
    trigger=ManualTrigger(),
    input_source=StaticInput("please echo hello"),
    host_profile=HostRuntimeProfile(config=RuntimeConfig(model=my_model)),
    validation_policy=ValidationPolicy(validator=always_pass),
    stop_condition=stop_on_pass(),
)

outcome = await run_loop(definition)          # the manual entry point
assert outcome.terminal_event == "loop_completed"
```

A runnable version is in [`examples/loop_quickstart.py`](../examples/loop_quickstart.py).

## The Loop Definition

A declarative, public-safe description of an outer loop. It carries **no
secrets** and wires no Phase-1 collaborator directly — the `host_profile` is the
only path to a composed runtime.

| Field | Purpose |
|---|---|
| `loop_id` | stable identifier |
| `trigger` | `ManualTrigger` (executable) or an `IntervalTrigger` / `ConditionTrigger` contract |
| `input_source` | supplies the first iteration's input |
| `host_profile` | a Phase-2 `RuntimeConfig` **or** a `selector` that builds a `LoopPlaneHost` |
| `validation_policy` | the gating `Validator` |
| `stop_condition` | a predicate over Loop State **plus** a mandatory `max_iterations` bound |
| `retry_policy` / `repair_policy` | retry (count + backoff) and repair (instruction source), kept distinct |
| `evaluation_policy` | optional, non-gating `Evaluator` |
| `artifact_policy` / `approval_policy` / `observation_policy` | artifact reuse, human-review requirement, and loop observation (off by default) |

Call `validate_definition(definition)` to fail fast on an invalid definition
(empty id, unresolvable host profile, missing iteration bound, repair enabled
without an instruction source).

## Validation, retry, and repair

After each Agent Run the **Validator** returns exactly one status:

| Status | The Loop Controller… |
|---|---|
| `pass` | stops with `loop_completed` (when the stop condition is satisfied), else continues |
| `fail` | retries the **same** input up to `retry_policy.max_retries`, then `loop_failed` |
| `needs_repair` | builds a **new** input injecting the repair instruction + prior-run context, then re-runs |
| `needs_human_review` | emits `human_review_requested` and pauses (see below) |
| *raised / unrecognized* | fails safe to human review (or `loop_failed`) with a diagnostic — never a silent pass |

**Retry vs repair are distinct.** Retry re-sends the same input; repair re-sends
an intentionally changed input. The retry backoff is a delay *value* surfaced on
`retry_scheduled` — the layer does no in-process sleeping. Every iteration is a
fresh Agent Run by default (checkpoint reset); artifact reuse is by reference
through `host.retrieve_artifact`, governed by the artifact policy.

A non-natural Agent Run termination (turn budget exhausted, cancelled,
unrecoverable error) is mapped to a failed iteration subject to the retry policy
— never a loop crash.

## Evaluation (optional, non-gating)

When an `evaluation_policy` is present, an **Evaluator** runs after validation and
produces a score/label/reason. It is recorded in Loop State and surfaced via
`evaluation_completed`, and a stop condition may read it (e.g.
`stop_when_score_at_least(0.9, max_iterations=5)`). Evaluation **never** decides
retry or repair, and an evaluator error is a non-fatal diagnostic.

## Triggers and human review

The **manual trigger** starts a Loop Run via `run_loop(definition)`. The
`IntervalTrigger` and `ConditionTrigger` are **contracts only** this phase — a
host's own driver enacts a tick or a satisfied predicate by calling the same
manual entry point. The layer ships no scheduler, queue worker, or daemon.

On `needs_human_review` the loop emits `human_review_requested` and:

- with a host-supplied `review_resolver`, resolves the decision in-process
  (approve → `loop_completed`, reject → `loop_failed`);
- without one, the loop stays **cleanly paused** (`outcome.paused`, approval
  status `pending`) and starts no further Agent Run until a decision is supplied.

In-run *tool* approval remains the Phase-1 Human Approval boundary, surfaced
through the host's `on_approval`. Durable, cross-restart loop resume is a
reserved extension point, not built this phase.

## Loop Events and Loop State

The Loop Controller emits a **distinct** Loop Event stream (separate from the
Phase-1 Runtime Event Bus): `loop_started`, `loop_iteration_started`,
`loop_iteration_completed`, `validation_completed`, `evaluation_completed`,
`repair_requested`, `retry_scheduled`, `human_review_requested`, and exactly one
terminal `loop_completed` / `loop_failed`. Emission is **off by default**
(`observation_policy.emit_loop_events`) and adds zero behavior change when off.

**Loop State** holds references only — `session_id`s, artifact references, the
latest validation/evaluation results, the approval status, and the stop reason —
never copied run history or artifact bytes. The ordered Loop Event stream is
sufficient to reconstruct it via `reconstruct_state(events)`.

## Boundary

The layer composes the runtime **only** through `loopplane.host` (and the
normalized value types the host re-exposes). It never imports or drives
`loopplane.controller`, `.gateway`, `.loop`, the event bus, or the stores
directly. See
[`specs/003-loopplane-loop-engineering-layer/contracts/host-integration.md`](../specs/003-loopplane-loop-engineering-layer/contracts/host-integration.md).
