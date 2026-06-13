# Validator & Evaluator Packs

The **packs layer** (`loopplane.packs`) ships reusable, deterministic,
public-safe implementations of the Phase-3 Validator and Evaluator Protocol
contracts. A pack is a **pure callable** that reads only the public
`RunOutcome` / `LoopState` surface and returns a Phase-3 `ValidationResult` or
`EvaluationResult`. Packs never start or drive runs and never reach into
Phase-1/2/3 internals — you plug them straight into a Loop Definition's
`validation_policy` and `evaluation_policy`.

A runnable example is [`examples/packs_quickstart.py`](../examples/packs_quickstart.py).

## The outcome reader

Every pack reads the outcome the same way:

```python
from loopplane.packs import read_outcome
view = read_outcome(outcome, state)
view.terminal_reason        # the run's terminal reason
view.final_text             # the last assistant entry's text ("" if none)
view.artifact_references    # the artifact reference strings from Loop State
```

## Validators

```python
from loopplane.packs import (
    rule_validator, text_validator, json_schema_validator, artifact_presence_validator,
)

rule_validator(lambda view: "ok" in view.final_text)
text_validator(mode="contains", pattern="done")        # matches | contains | not_contains
json_schema_validator(schema={"type": "object", "required": ["ok"]})
artifact_presence_validator(require=True)               # or require=False ("must not produce")
```

Each returns a Phase-3 `Validator`. Every validator **fails safe** — empty text,
unparseable JSON, a raising rule, or a missing artifact maps to an explicit
`fail` with a reason, never a silent `pass`. An invalid regex is rejected at
construction (`PackConfigError`).

## Evaluators (non-gating)

```python
from loopplane.packs import scoring_evaluator, label_evaluator, length_evaluator

scoring_evaluator(lambda view: my_score(view.final_text))
label_evaluator([(lambda v: "error" in v.final_text, "bad")], default="ok")
length_evaluator(target_chars=200)                      # normalized length score in [0, 1]
```

Each returns a Phase-3 `Evaluator`. Evaluators are **non-gating**: they return
only an `EvaluationResult` and never decide control flow. A raising scoring
function becomes a non-fatal diagnostic (`score=None` with a reason).

## Combinators & the threshold gate

```python
from loopplane.packs import all_of, any_of, threshold_gate

all_of(text_validator(mode="contains", pattern="done"), artifact_presence_validator(require=False))
any_of(text_validator(mode="matches", pattern=r"\{.*\}"), json_schema_validator(schema=schema))
threshold_gate(length_evaluator(target_chars=200), threshold=0.5, below="needs_repair")
```

`all_of` passes only if every sub-validator passes; `any_of` passes if at least
one does. When combining, the **most cautious** status wins:
`needs_human_review` > `needs_repair` > `fail` > `pass` — a review/repair request
is never silently downgraded. Empty `all_of()` ⇒ `pass`; empty `any_of()` ⇒
`fail`. The **threshold gate** is the *only* pack that turns an evaluation score
into a gating decision (a missing score fails safe), preserving the Phase-3 rule
that evaluation is otherwise non-gating.

## Plugging packs into a loop

```python
from loopplane.engineering import ValidationPolicy, EvaluationPolicy

definition = LoopDefinition(
    ...,
    validation_policy=ValidationPolicy(validator=all_of(
        text_validator(mode="contains", pattern="done"),
        artifact_presence_validator(require=False),
    )),
    evaluation_policy=EvaluationPolicy(evaluator=length_evaluator(target_chars=200)),
)
outcome = await run_loop(definition)
```

## Determinism, public-safety & reserved extension points

Packs do no I/O and no network: given the same outcome they return the same
result. They carry no secrets or domain data — patterns, schemas, thresholds,
and rules are host-supplied. Reserved, **not** built this phase: machine-learning
or model-graded evaluators, an LLM-as-judge, external validation services or
remote schema registries, and a plugin marketplace.

## Boundary

A pack imports only `loopplane.engineering` (the contracts/results), the
`RunOutcome` / content-block value types, the stdlib, and the existing
`jsonschema` dependency. It never imports or calls `loopplane.controller`,
`.gateway`, `.loop`, the host facade, the scheduler, or `run_loop`. See
[`specs/005-loopplane-validator-evaluator-packs/contracts/combinators-boundary.md`](../specs/005-loopplane-validator-evaluator-packs/contracts/combinators-boundary.md).
