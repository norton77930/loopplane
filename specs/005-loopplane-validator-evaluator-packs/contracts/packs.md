# Contract: Outcome Reader, Validators & Evaluators

**Feature**: `005-loopplane-validator-evaluator-packs` | FR-001–FR-023

Reusable implementations of the Phase-3 Validator/Evaluator Protocols. Every pack is a pure callable that
reads only the public `RunOutcome`/`LoopState` surface through the shared outcome reader and returns a
Phase-3 result. Signatures are design intent for the implementation phase.

## Outcome Reader (FR-002)

```python
@dataclass(frozen=True)
class OutcomeView:
    terminal_reason: str
    final_text: str
    artifact_references: tuple[str, ...]

def read_outcome(outcome: RunOutcome, state: LoopState) -> OutcomeView: ...
```

- MUST read only the public surface (`outcome.termination_reason`, `outcome.history`, `state.artifacts`);
  MUST NOT touch a Phase-1/2 internal (FR-002, FR-040).
- `final_text` MUST be the concatenated `TextBlock` text of the **last `assistant`** history entry, in
  order; empty when there is none (deterministic — edge case).
- MUST NOT mutate the inputs (FR-003).

## Validators (FR-010–FR-014)

```python
def rule_validator(
    predicate: Callable[[OutcomeView], bool], *, reason: str = "rule not satisfied"
) -> Validator: ...

TextMode = Literal["matches", "contains", "not_contains"]
def text_validator(*, mode: TextMode, pattern: str, reason: str | None = None) -> Validator: ...

def json_schema_validator(*, schema: Mapping[str, Any]) -> Validator: ...

def artifact_presence_validator(*, require: bool = True) -> Validator: ...
```

**Contract requirements**

- Each returns a callable implementing the Phase-3 `Validator` Protocol `(RunOutcome, LoopState) ->
  ValidationResult` and plugs into a Loop Definition's `validation_policy` (FR-001).
- `rule_validator`: `pass` when the host predicate over the `OutcomeView` is true; else `fail` with the
  reason. A raising predicate → fail-safe `fail` (FR-010, FR-014).
- `text_validator`: `matches` = `re.fullmatch`, `contains` = `re.search` present, `not_contains` =
  `re.search` absent, over `final_text`. The pattern is compiled at **construction**; an invalid pattern
  raises `PackConfigError` then (FR-011). Empty `final_text` is evaluated honestly (a `not_contains`
  passes; a `contains`/`matches` fails with a reason).
- `json_schema_validator`: parse `final_text` as JSON (stdlib `json`) and validate against `schema`
  (`jsonschema`). `pass` on a valid match; `fail` with the violation reason on a schema violation; a
  **fail-safe** `fail` with a reason on unparseable JSON — never a silent `pass` (FR-012, FR-014).
- `artifact_presence_validator`: `require=True` ⇒ `pass` iff `artifact_references` is non-empty;
  `require=False` ⇒ `pass` iff empty; else `fail` with a reason (FR-013).
- Every validator MUST be **deterministic** (NFR-002) and **fail safe** (FR-014, NFR-005): malformed or
  missing input maps to an explicit `fail` (or `needs_human_review` when configured) with a public-safe
  reason.

## Evaluators (FR-020–FR-023)

```python
def scoring_evaluator(
    score_fn: Callable[[OutcomeView], float], *, label: str | None = None
) -> Evaluator: ...

def label_evaluator(
    rules: Sequence[tuple[Callable[[OutcomeView], bool], str]], *, default: str
) -> Evaluator: ...

def length_evaluator(*, target_chars: int) -> Evaluator: ...
```

**Contract requirements**

- Each returns a callable implementing the Phase-3 `Evaluator` Protocol and plugs into a Loop
  Definition's `evaluation_policy` (FR-001).
- Output is **non-gating** (FR-023): an evaluator returns only an `EvaluationResult` and never a
  `ValidationResult`; it never by itself forces `fail`/`needs_repair`.
- `scoring_evaluator`: `EvaluationResult(score=score_fn(view), label=label)`; a raising `score_fn` →
  `EvaluationResult(score=None, reason=...)` (a non-fatal diagnostic, FR-023, NFR-005).
- `label_evaluator`: returns the first matching rule's label (with a reason), else `default`.
- `length_evaluator`: `score = clamp(len(final_text) / target_chars, 0.0, 1.0)` — always in `[0, 1]`
  (FR-022, SC-004); `target_chars` MUST be positive (else `PackConfigError`).
