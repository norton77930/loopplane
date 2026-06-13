# Phase 1 Data Model: Validator & Evaluator Packs

**Feature**: `005-loopplane-validator-evaluator-packs` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

This model defines the **pack-layer** entities only. It references — and never redefines — the Phase-3
entities (`RunOutcome`, `LoopState`, `ValidationResult`, `ValidationStatus`, `EvaluationResult`, the
`Validator`/`Evaluator` Protocols, and the public content-block types). All types are illustrative design
intent for the implementation phase, and all are public-safe (FR-004 / NFR-004).

## Entity overview

```text
read_outcome(outcome, state) -> OutcomeView   (the one read of the public surface)
        ▲
        │ used by every pack
Validator packs  ──implements──► Phase-3 Validator Protocol  ──returns──► ValidationResult
 ├─ rule_validator(predicate)
 ├─ text_validator(mode, pattern)
 ├─ json_schema_validator(schema)
 ├─ artifact_presence_validator(require)
 ├─ all_of(*validators) / any_of(*validators)        (combinators)
 └─ threshold_gate(evaluator, threshold, below)      (the one evaluation->gating)

Evaluator packs  ──implements──► Phase-3 Evaluator Protocol ──returns──► EvaluationResult
 ├─ scoring_evaluator(score_fn)
 ├─ label_evaluator(rules)
 └─ length_evaluator(target)
```

---

## 1. OutcomeView  (FR-002)

The single read of the public `RunOutcome` / `LoopState` surface.

```python
@dataclass(frozen=True)
class OutcomeView:
    terminal_reason: str            # = RunOutcome.termination_reason
    final_text: str                 # concatenated TextBlock text of the last assistant entry ("" if none)
    artifact_references: tuple[str, ...]  # the reference strings from LoopState.artifacts

def read_outcome(outcome: RunOutcome, state: LoopState) -> OutcomeView: ...
```

**Rules**: reads only the public surface (FR-002, FR-040); `final_text` is the **last `assistant`**
history entry's `TextBlock` text joined in order (deterministic selection — edge case); empty when there
is no assistant text. Never mutates the inputs (FR-003).

---

## 2. Validator packs  (FR-010–FR-014)

Each constructor returns a callable implementing the Phase-3 `Validator` Protocol.

| Pack | Signature (design intent) | Returns |
|---|---|---|
| `rule_validator` | `(predicate: Callable[[OutcomeView], bool], *, reason="rule failed") -> Validator` | `pass` if predicate true, else `fail` (FR-010) |
| `text_validator` | `(*, mode: TextMode, pattern: str, reason=None) -> Validator` | `pass`/`fail` on the regex check (FR-011) |
| `json_schema_validator` | `(*, schema: Mapping[str, Any]) -> Validator` | `pass` if `final_text` parses + validates, else `fail` with the reason (FR-012) |
| `artifact_presence_validator` | `(*, require: bool = True) -> Validator` | `pass`/`fail` on `artifact_references` presence/absence (FR-013) |

`TextMode = Literal["matches", "contains", "not_contains"]`. The text validator compiles its pattern at
construction; an invalid regex raises `PackConfigError` then (FR-011, edge case).

**Fail-safe (FR-014, NFR-005)**: every validator maps malformed/missing input — empty `final_text`,
unparseable JSON, a raising host predicate, a missing artifact — to an explicit `fail` (or
`needs_human_review` when configured) with a public-safe reason, never a silent `pass`.

---

## 3. Evaluator packs  (FR-020–FR-023)

Each constructor returns a callable implementing the Phase-3 `Evaluator` Protocol; output is **non-gating**.

| Pack | Signature (design intent) | Returns |
|---|---|---|
| `scoring_evaluator` | `(score_fn: Callable[[OutcomeView], float], *, label=None) -> Evaluator` | `EvaluationResult(score=score_fn(view), label=label)` (FR-020) |
| `label_evaluator` | `(rules: Sequence[tuple[Callable[[OutcomeView], bool], str]], *, default: str) -> Evaluator` | the first matching rule's label, else `default` (FR-021) |
| `length_evaluator` | `(*, target_chars: int) -> Evaluator` | `EvaluationResult(score=clamp(len(final_text)/target_chars, 0, 1))` (FR-022) |

**Rules**: an evaluator never returns a `ValidationResult` and never gates (FR-023). A raising
`score_fn` → `EvaluationResult(score=None, reason="scoring function raised: ...")` (a non-fatal
diagnostic). `length_evaluator` always yields a score in `[0, 1]`.

---

## 4. Combinators & Threshold Gate  (FR-030–FR-034)

Validator-composition packs.

```python
def all_of(*validators: Validator) -> Validator: ...   # pass iff every sub passes
def any_of(*validators: Validator) -> Validator: ...    # pass iff >=1 sub passes
def threshold_gate(
    evaluator: Evaluator, *, threshold: float, below: ValidationStatus = "fail",
) -> Validator: ...
```

**Combinator precedence (FR-030, FR-031)** — the most cautious status wins:
`needs_human_review` > `needs_repair` > `fail` > `pass`.

- `all_of`: if every sub-result is `pass` → `pass`; otherwise the most cautious non-pass status.
- `any_of`: if any sub-result is `pass` → `pass`; otherwise the most cautious status among the
  sub-results.
- **Empty defaults (FR-034)**: `all_of()` → `pass`; `any_of()` → `fail`.

**Threshold gate (FR-032, FR-033)**: runs the evaluator; if its `score` is `None` → fail-safe `fail`
with a reason; if `score >= threshold` → `pass`; else → the configured `below` status (`fail` or
`needs_repair`) with a reason. This is the **only** pack converting evaluation into gating (preserving
FR-023).

---

## 5. PackConfigError  (FR-011)

A public-safe `ValueError` raised at **construction** for an invalid pack configuration (e.g. an invalid
regex). Apply-time inputs never raise — they fail safe (FR-014).

## Referenced Phase-3 entities (not redefined)

| Entity | Source | Referenced as |
|---|---|---|
| `Validator` / `Evaluator` Protocols | `loopplane.engineering` | the contracts each pack implements |
| `ValidationResult` / `ValidationStatus` | `loopplane.engineering` | validator pack output |
| `EvaluationResult` | `loopplane.engineering` | evaluator pack output |
| `RunOutcome` / `LoopState` | `loopplane.engineering` (re-exposed Phase-2/3 types) | read-only pack input |
| `HistoryEntry` / `TextBlock` | content value types via the host | read by the outcome reader |
