# Contract: Combinators, Threshold Gate & Boundary

**Feature**: `005-loopplane-validator-evaluator-packs` | FR-030–FR-034, FR-040–FR-043

## Combinators (FR-030, FR-031, FR-034)

```python
def all_of(*validators: Validator) -> Validator: ...
def any_of(*validators: Validator) -> Validator: ...
```

**Status-combination precedence** (most cautious wins):

```text
needs_human_review  >  needs_repair  >  fail  >  pass
```

- `all_of`: `pass` iff **every** sub-validator returns `pass`; otherwise the **most cautious** non-pass
  status among the sub-results (so a `pass` + `needs_human_review` ⇒ `needs_human_review`).
- `any_of`: `pass` iff **at least one** sub-validator returns `pass`; otherwise the **most cautious**
  status among the sub-results.
- The precedence MUST NOT silently downgrade `needs_human_review` / `needs_repair` to a plain `pass` /
  `fail` (FR-031).
- **Empty defaults (FR-034)**: `all_of()` ⇒ `pass`; `any_of()` ⇒ `fail`.
- The combined `reason`/`metadata` MUST identify which sub-validators drove the result (public-safe).

## Threshold Gate (FR-032, FR-033)

```python
def threshold_gate(
    evaluator: Evaluator, *, threshold: float, below: ValidationStatus = "fail",
) -> Validator: ...
```

- Runs `evaluator` over the `(RunOutcome, LoopState)`, reads its `score`, and gates:
  `score >= threshold` ⇒ `pass`; `score < threshold` ⇒ the configured `below` status (`fail` or
  `needs_repair`) with a reason.
- A **missing/`None` score** ⇒ fail-safe `fail` with a reason — never treats a missing score as passing
  (FR-033, NFR-005).
- This MUST be the **only** pack that converts evaluation into a gating decision, preserving the Phase-3
  non-gating rule (FR-023, FR-032).

## Boundary (FR-040–FR-043, NFR-003)

A pack composes only the Phase-3 public surface:

```python
from loopplane.engineering import (
    Validator, Evaluator, ValidationResult, ValidationStatus, EvaluationResult,
)
# RunOutcome / LoopState are read-only inputs (Phase-3 types re-exposed by the loop layer).
```

A pack MUST NOT:

- import or call any Phase-1 runtime internal (`loopplane.controller`, `.gateway`, `.loop`,
  `.events.EventEmitter`, `.memory`, `.checkpoint`, `.artifacts`, `.approval`, `.observability`), any
  Phase-2 host internal (`loopplane.host.*` assembly), or any Phase-3 loop-control internal
  (`loopplane.engineering.controller`'s `LoopController` mechanics) (FR-040);
- start, drive, schedule, or observe runs; it only reads a `RunOutcome`/`LoopState` and returns a result
  (FR-041);
- carry secrets or domain data; configuration is host-supplied and examples use public-safe values
  (FR-004);
- implement any out-of-scope capability — an LLM-as-judge, ML scoring, remote/external validation calls,
  cloud, web/UI, or non-deterministic evaluation (FR-043).

> Permitted: stdlib (`re`, `json`), the existing core `jsonschema` dependency, and the Phase-3 public
> symbols above. Reading the public `RunOutcome`/`LoopState`/content-block value types is the intended
> composition path; reaching into lower-layer modules is the prohibited reach-through.

## Reserved extension points (named, not built) — FR-042

- Machine-learning or model-graded evaluators, and an LLM-as-judge evaluator.
- External validation services and remote schema registries.
- A plugin marketplace of third-party packs.

## Auditability (NFR-003, SC-002, SC-010)

- An import-boundary test MUST assert `loopplane.packs` imports only `loopplane.engineering` (+ stdlib +
  `jsonschema`) and never a prohibited Phase-1/2/3 internal.
- 100% of packs in the suite read only the public surface and start no run (SC-002).
- A public-safety scan over committed Phase-5 files MUST find zero private references (SC-010, NFR-004).
