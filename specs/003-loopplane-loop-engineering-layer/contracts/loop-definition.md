# Contract: Loop Definition & Policies

**Feature**: `003-loopplane-loop-engineering-layer` | FR-001–FR-009, FR-020–FR-023

The declarative, public-safe surface a loop engineer constructs to describe an outer loop. Frozen and
serializable; **carries no secrets, paths, or private names** and wires no Phase-1 collaborator directly
(FR-001, FR-002, NFR-004). Signatures below are **design intent** for the implementation phase.

## `LoopDefinition`

```python
@dataclass(frozen=True)
class LoopDefinition:
    loop_id: str
    trigger: Trigger
    input_source: InputSource
    host_profile: HostRuntimeProfile
    validation_policy: ValidationPolicy
    retry_policy: RetryPolicy
    repair_policy: RepairPolicy
    stop_condition: StopCondition
    artifact_policy: ArtifactPolicy
    approval_policy: ApprovalPolicy
    observation_policy: ObservationPolicy
    evaluation_policy: EvaluationPolicy | None = None   # optional (FR-005)
```

**Contract requirements**

- MUST carry all fields in FR-001; only `evaluation_policy` is optional (FR-005).
- MUST be **validatable before any Loop Run** — `validate_definition(defn) -> None` raises a public-safe
  `LoopDefinitionError` on: empty `loop_id`; an unresolvable `host_profile`; a `stop_condition` without a
  finite `max_iterations ≥ 1` (FR-007, FR-013); an `approval_policy` that requires human review while
  declaring it unavailable.
- MUST NOT embed runtime internals or credentials; the host runtime profile is the **only** path to a
  composed runtime (FR-002, FR-080).
- The original definition is **immutable across a Loop Run**; repair builds new inputs without mutating
  it (FR-003, FR-052).

## `HostRuntimeProfile` (FR-002, FR-080)

```python
@dataclass(frozen=True)
class HostRuntimeProfile:
    config: RuntimeConfig | None = None              # a Phase-2 RuntimeConfig …
    selector: Callable[[], LoopPlaneHost] | None = None  # … or a host-resolvable factory
    def build(self) -> LoopPlaneHost: ...            # exactly one source must be present
```

- MUST resolve to a Phase-2 `LoopPlaneHost`; MUST NOT wire `RuntimeController`, `ToolGateway`, or any
  Phase-1 collaborator directly (FR-002, FR-090).

## `InputSource` (FR-003)

```python
class InputSource(Protocol):
    def initial(self) -> Prompt: ...    # Prompt = str | Sequence[ContentBlock] (Phase-2 type)
```

- `initial()` supplies the iteration-1 prompt; repair augmentation is produced by the repair path
  (see [loop-controller.md](./loop-controller.md)), never by mutating the source (FR-003, FR-052).

## Policies

```python
@dataclass(frozen=True)
class ValidationPolicy:    validator: Validator                       # FR-004, FR-033
@dataclass(frozen=True)
class EvaluationPolicy:    evaluator: Evaluator                       # FR-040 (optional holder)

@dataclass(frozen=True)
class RetryPolicy:                                                    # FR-006, FR-051
    max_retries: int = 0                                             # ≥ 0
    backoff: BackoffContract = NO_BACKOFF                            # data only; no sleeping

@dataclass(frozen=True)
class RepairPolicy:                                                   # FR-006, FR-052
    enabled: bool = False
    instruction_source: RepairInstructionSource | None = None        # required when enabled

@dataclass(frozen=True)
class ArtifactPolicy:      reuse: bool = False                        # FR-008, FR-053
@dataclass(frozen=True)
class ApprovalPolicy:                                                 # FR-009, FR-034, FR-082
    require_human_review_on: frozenset[ValidationStatus] = frozenset({"needs_human_review"})
    human_review_available: bool = True
@dataclass(frozen=True)
class ObservationPolicy:   emit_loop_events: bool = False            # default OFF (FR-009, NFR-005)
```

**Contract requirements**

- `RetryPolicy` and `RepairPolicy` MUST be expressible **independently** — retry as count+backoff,
  repair as enablement+instruction — preserving the retry-vs-repair distinction (FR-006, FR-050).
- `BackoffContract.delay_seconds(attempt: int) -> float` returns a **delay value only**; the layer
  performs no in-process sleeping (FR-051).
- `ArtifactPolicy.reuse` permits referencing prior artifacts **by reference only** through the host
  (FR-008, FR-053).
- `ObservationPolicy.emit_loop_events` defaults **off**; enabling it MUST NOT alter loop decisions or
  the terminal outcome (NFR-005, SC-009).

## Trigger contracts (FR-020–FR-023)

```python
@dataclass(frozen=True)
class ManualTrigger: ...                                  # implemented (FR-020)

@dataclass(frozen=True)
class IntervalTrigger:                                    # CONTRACT ONLY (FR-021, FR-023)
    interval_seconds: float
    start_immediately: bool = False

@dataclass(frozen=True)
class ConditionTrigger:                                   # CONTRACT ONLY (FR-022, FR-023)
    predicate_ref: str
    description: str = ""

Trigger = ManualTrigger | IntervalTrigger | ConditionTrigger
```

- Only `ManualTrigger` is executable this phase: a host starts exactly one Loop Run through the manual
  entry point (FR-020, SC-008 scenario 1).
- `IntervalTrigger` / `ConditionTrigger` are **data contracts**, carrying no scheduler/watcher state; a
  host-supplied driver enacts a tick or satisfied predicate by calling the **same** manual entry point
  (FR-021–FR-023, SC-008). The layer ships **no** scheduler, queue worker, or background daemon
  (FR-023, FR-092).
