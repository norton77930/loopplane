# Contract: Validator & Evaluator

**Feature**: `003-loopplane-loop-engineering-layer` | FR-030–FR-034, FR-040–FR-043

Both are **host-supplied policy callables** referenced by the Loop Definition. The layer defines their
contracts and handles their outcomes but hardcodes no domain-specific logic (FR-033). Signatures are
design intent for the implementation phase.

## Validator (gating) — FR-030–FR-034

```python
ValidationStatus = Literal["pass", "fail", "needs_repair", "needs_human_review"]

@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    reason: str | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

class Validator(Protocol):
    def __call__(
        self, outcome: RunOutcome, state: LoopState,
    ) -> ValidationResult | Awaitable[ValidationResult]: ...
```

**Contract requirements**

- MUST return **exactly one** `status` of the four (FR-030). The controller awaits the result if a
  coroutine is returned (sync or async validators both supported).
- `reason` and `metadata` MUST be carriable and are consumable by repair (FR-052) and the stop condition
  (FR-007) (FR-031). All values MUST be public-safe (NFR-004).
- The controller MUST map each status to its defined decision (FR-032) — see
  [loop-controller.md](./loop-controller.md).
- **Fail-safe (FR-034)**: if the Validator raises or returns an unrecognized status, the controller MUST
  route the iteration to human review (or `loop_failed` when review is unavailable) and emit a
  diagnostic — it MUST NOT treat the outcome as a silent `pass`. This is observable in 100% of suite
  cases (SC-003).
- MUST be supplied by the host via `ValidationPolicy`; the layer MUST NOT embed domain validation
  (FR-033).

## Evaluator (non-gating, optional) — FR-040–FR-043

```python
@dataclass(frozen=True)
class EvaluationResult:
    score: float | None = None
    label: str | None = None
    reason: str | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

class Evaluator(Protocol):
    def __call__(
        self, outcome: RunOutcome, state: LoopState,
    ) -> EvaluationResult | Awaitable[EvaluationResult]: ...
```

**Contract requirements**

- Runs **only** when an `EvaluationPolicy` is present; absent ⇒ no evaluation step executes and **no**
  `evaluation_completed` event is emitted (FR-005, FR-042, US4 scenario 3).
- Output is **non-gating**: an `EvaluationResult` MUST NOT by itself decide stop, retry, or repair. Only
  the stop condition (FR-007) or a Validator may consume evaluation output to influence control flow
  (FR-041, US4 scenario 2).
- The controller MUST record each result in Loop State and emit `evaluation_completed` (FR-042).
- **Non-fatal errors (FR-043)**: an Evaluator that raises MUST be surfaced as a diagnostic and MUST NOT
  abort the Loop Run; the iteration proceeds on the validation result alone (US4 scenario 4).

## Stop condition interaction (FR-007, US4)

A `StopCondition` is a predicate over Loop State (it may read `latest_evaluation.score` /
`latest_validation.status`) plus a mandatory `max_iterations` bound. Reference constructors:

```python
def stop_on_pass() -> StopCondition: ...                       # stop on first passing validation
def max_iterations(n: int) -> StopCondition: ...               # bound-only
def stop_when_score_at_least(threshold: float, *, max_iterations: int) -> StopCondition: ...
```

The controller checks the bound **before** the predicate so termination is always guaranteed
(FR-013, SC-007). Evaluation can drive *stopping* but never *retry/repair* (FR-041).
