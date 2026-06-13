# Feature Specification: Validator & Evaluator Packs

**Feature Branch**: `005-loopplane-validator-evaluator-packs`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Define the Validator & Evaluator Packs layer (unit 005) on top of the
completed Loop Engineering Layer (003), reusing its Validator and Evaluator Protocol contracts. This
phase ships reusable, deterministic, public-safe implementations of those Phase-3 contracts that a Loop
Definition plugs into its validation_policy and evaluation_policy — never bypassing the loop layer, never
reaching into Phase-1/2 internals, and never starting or driving runs. In scope: rule-based, text/regex,
JSON-schema, and artifact-presence validators; scoring, label, and length/heuristic evaluators; all-of /
any-of validator combinators and a threshold gate; public-safe examples and docs. Reserved (named, not
built): ML/model-graded evaluators, LLM-as-judge, external validation services or remote schema
registries, and a plugin marketplace. Out of scope: LLM-judge, ML scoring, remote/external validation,
cloud, web/UI, and any non-deterministic evaluation. Public-safe and English. Determinism is mandatory."

## Feature Overview

LoopPlane's third phase delivered the **Loop Engineering Layer**: an outer control loop that, after each
iteration's Agent Run, applies a **Validator** (a gating decision — `pass` / `fail` / `needs_repair` /
`needs_human_review`) and an optional **Evaluator** (a non-gating measurement — score / label / reason /
metadata), then decides whether to stop, retry, repair, or request human review (see
[`../003-loopplane-loop-engineering-layer/spec.md`](../003-loopplane-loop-engineering-layer/spec.md)).
Phase 3 deliberately defined the Validator and Evaluator as **policy boundaries** — host-supplied
callables — and hardcoded **no** domain-specific validation or scoring logic.

Phase 5 fills that gap with a library of reusable, drop-in **packs**: concrete implementations of the
Phase-3 Validator and Evaluator contracts a Loop Definition can plug straight into its
`validation_policy` and `evaluation_policy`. A pack is a **pure callable** that receives the Phase-3
`(RunOutcome, LoopState)` and returns a `ValidationResult` or an `EvaluationResult`, reading **only** the
public `RunOutcome` surface — its terminal reason and its history of content blocks. Packs never start or
drive runs, never reach into Phase-1/2 internals, and add no runtime of their own; they are the
domain-agnostic building blocks Phase 3 left as an extension point.

This phase ships: rule-based, text/regex, JSON-schema, and artifact-presence **validators**; scoring,
label, and length/heuristic **evaluators**; **combinators** (all-of / any-of validators and a threshold
gate that turns an evaluator score into a gating decision); plus public-safe examples and a docs guide.
Every pack is **deterministic** (the same run outcome always yields the same result) and **fails safe**
(a malformed or missing input maps to an explicit result with a reason — never a silent `pass`). Model-
graded evaluation, an LLM-as-judge, external validation services, and a plugin marketplace are named
reserved extension points, not built here.

### Core Distinctions

This phase adds implementations *behind* the Phase-3 policy boundary; it does not change the loop. The
following distinctions are normative.

| # | Phase-3 concept (contract) | Phase-5 concept (pack) |
|---|---|---|
| 1 | **Validator** — a Protocol: `(RunOutcome, LoopState) -> ValidationResult`, host-supplied; the layer hardcodes no logic. | **Validator pack** — a concrete, reusable callable that *implements* that Protocol (rule / text / JSON-schema / artifact / combinator / gate). |
| 2 | **Evaluator** — a Protocol: `(RunOutcome, LoopState) -> EvaluationResult`, optional and non-gating. | **Evaluator pack** — a concrete, reusable callable that *implements* that Protocol (scoring / label / length). |
| 3 | **RunOutcome** — the opaque per-iteration result the loop hands the Validator/Evaluator. | **Outcome reader** — a small public-safe helper that extracts the final assistant text, the terminal reason, and any artifact references from a `RunOutcome`, so every pack reads the outcome the same way. |
| 4 | Evaluation is **non-gating** — only the stop condition or a Validator may consume a score. | **Threshold gate** — the *one* explicit pack that turns an evaluation score into a gating `ValidationResult`, preserving "evaluation is otherwise non-gating". |

**Implemented this phase vs reserved extension points**:

- **Implemented**: an outcome reader; rule-based / text-regex / JSON-schema / artifact-presence
  validators; scoring / label / length evaluators; all-of / any-of validator combinators; a threshold
  gate; fail-safe handling; and public-safe examples.
- **Reserved (named, not built)**: machine-learning or model-graded evaluators, an LLM-as-judge
  evaluator, external validation services or remote schema registries, and a plugin marketplace of
  third-party packs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a run outcome and gate on a rule (Priority: P1)

A loop engineer plugs a **rule-based validator pack** into a Loop Definition's validation policy. After
an Agent Run, the pack uses the shared **outcome reader** to extract the run's terminal reason and final
assistant text from the `RunOutcome`, applies a host-supplied rule (a predicate over that extracted
view), and returns a `ValidationResult` — `pass` when the rule holds, `fail` (with a reason) otherwise.
The pack reads only the public `RunOutcome` surface and never touches a Phase-1/2 internal.

**Why this priority**: The outcome reader plus a rule-based validator is the minimum viable pack and the
foundation every other validator builds on. It is independently demonstrable with a scripted run outcome
and a one-line rule.

**Independent Test**: Build a scripted `RunOutcome` with known text and terminal reason, apply a
rule-based validator whose predicate checks that text, and assert it returns `pass`; flip the predicate
and assert it returns `fail` with a reason — deterministically across repeated calls.

**Acceptance Scenarios**:

1. **Given** a rule-based validator whose predicate accepts the run's final text, **When** it is applied
   to a matching `RunOutcome`, **Then** it returns `ValidationResult(status="pass")`.
2. **Given** the same validator and a non-matching outcome, **When** it is applied, **Then** it returns
   `fail` with a public-safe reason.
3. **Given** the outcome reader, **When** it reads a `RunOutcome`, **Then** it exposes the terminal
   reason, the final assistant text, and any artifact references — reading only the public surface.
4. **Given** any pack, **When** it is applied twice to the same `RunOutcome`, **Then** it returns
   identical results (determinism).

---

### User Story 2 - Validate text and structured output (Priority: P2)

A loop engineer attaches a **text/regex validator** (the final assistant text must match, contain, or not
contain a pattern) and/or a **JSON-schema validator** (the final output must parse as JSON and validate
against a supplied schema). Each returns `pass` on success and `fail` with a reason on mismatch, and each
fails safe when the input is malformed — unparseable JSON yields `fail` with a reason, never a silent
`pass`.

**Why this priority**: Text and schema checks are the most common concrete validations and the first
real domain-agnostic packs. They build on the outcome reader from User Story 1.

**Independent Test**: Apply a regex validator to outputs that do and do not match and assert the
statuses; apply a JSON-schema validator to valid JSON, schema-invalid JSON, and non-JSON, and assert
`pass`, `fail`, and a fail-safe `fail` respectively.

**Acceptance Scenarios**:

1. **Given** a text validator configured to require a pattern, **When** the final text contains it,
   **Then** the result is `pass`; **When** it does not, **Then** `fail` with a reason.
2. **Given** a "must-not-contain" text validator, **When** the forbidden pattern appears, **Then** the
   result is `fail`.
3. **Given** a JSON-schema validator, **When** the final output is valid JSON matching the schema,
   **Then** `pass`; **When** it parses but violates the schema, **Then** `fail` with the violation
   reason.
4. **Given** the JSON-schema validator, **When** the final output is not parseable JSON, **Then** it
   fails safe with a reason — never a silent `pass`.

---

### User Story 3 - Score and label iterations (Priority: P3)

A loop engineer adds an **evaluator pack** to the evaluation policy: a **scoring evaluator** (a
host-supplied scoring function over the extracted outcome returns a numeric score), a **label evaluator**
(simple deterministic rules assign a categorical quality label), or a **length/heuristic evaluator** (a
deterministic measurement such as normalized output length). Each returns an `EvaluationResult`
(score / label / reason / metadata) and never gates control flow by itself.

**Why this priority**: Evaluators add measurement on top of validation. They are genuinely optional and
non-gating, so they sit below the validators that the loop needs to function.

**Independent Test**: Apply each evaluator to a scripted outcome and assert the recorded score/label and
that two applications to the same outcome yield identical results; confirm no evaluator changes a
validation decision.

**Acceptance Scenarios**:

1. **Given** a scoring evaluator with a deterministic scoring function, **When** applied to an outcome,
   **Then** it returns an `EvaluationResult` with the computed score and the same score on every repeat.
2. **Given** a label evaluator with categorical rules, **When** applied, **Then** it returns the expected
   label and reason.
3. **Given** a length evaluator, **When** applied to a short and a long output, **Then** it returns the
   expected normalized scores in `[0, 1]`.
4. **Given** any evaluator, **When** applied, **Then** its result is non-gating — it never by itself
   forces a `fail` or `needs_repair`.

---

### User Story 4 - Compose validators and gate on a score (Priority: P4)

A loop engineer composes several validators into one with an **all-of** combinator (every sub-validator
must pass) or an **any-of** combinator (at least one must pass), each with a documented precedence for
combining statuses, and uses a **threshold gate** to turn an evaluator score into a gating decision (a
score below a threshold becomes `fail` or `needs_repair`). The threshold gate is the only sanctioned path
by which evaluation drives gating, preserving the Phase-3 rule that evaluation is otherwise non-gating.

**Why this priority**: Combinators and the threshold gate compose the primitives from Stories 1–3 into
real validation policies. They depend on those primitives existing.

**Independent Test**: Compose two validators with all-of and any-of and assert the combined status for
each pass/fail mix per the documented precedence; build a threshold gate over a scoring evaluator and
assert a high score yields `pass` and a low score yields the configured `fail` / `needs_repair`.

**Acceptance Scenarios**:

1. **Given** an all-of combinator over two validators, **When** both pass, **Then** the result is `pass`;
   **When** either fails, **Then** the result is `fail` per the documented precedence.
2. **Given** an any-of combinator, **When** at least one sub-validator passes, **Then** the result is
   `pass`; **When** all fail, **Then** `fail`.
3. **Given** a combinator and a sub-validator returning `needs_repair` or `needs_human_review`, **When**
   it is applied, **Then** the combined status follows the documented precedence (review/repair are not
   silently downgraded to a plain pass/fail).
4. **Given** a threshold gate over an evaluator and a threshold, **When** the score is at or above the
   threshold, **Then** `pass`; **When** below, **Then** the configured `fail` or `needs_repair` with a
   reason.

---

### User Story 5 - Validate artifacts and keep the edges honest (Priority: P5)

A loop engineer uses an **artifact-presence validator** (the run must have produced — or must not have
produced — an artifact reference) and relies on every pack's **fail-safe** behavior for malformed or
missing inputs. Public-safe **examples** and a **docs guide** show how to plug packs into a Loop
Definition, and the reserved extension points (model-graded evaluation, LLM-as-judge, external services,
a plugin marketplace) are named but not built.

**Why this priority**: The artifact validator and the fail-safe/edge guarantees define what the phase
commits to versus what it reserves. They depend on the pack machinery in Stories 1–4 existing.

**Independent Test**: Apply the artifact-presence validator to outcomes with and without artifact
references and assert the statuses; apply each pack to an empty/degenerate outcome and assert an explicit
fail-safe result; run the example and confirm its documented output.

**Acceptance Scenarios**:

1. **Given** an artifact-presence validator requiring an artifact, **When** the outcome references one,
   **Then** `pass`; **When** it references none, **Then** `fail` with a reason.
2. **Given** a "must-not-produce-artifact" variant, **When** the outcome references an artifact, **Then**
   `fail`.
3. **Given** any pack and an empty or degenerate outcome (no text, no artifacts), **When** it is applied,
   **Then** it returns an explicit, public-safe result (fail-safe), never a silent `pass`.
4. **Given** the example pack configuration, **When** the example runs against a scripted outcome,
   **Then** it produces the documented validation/evaluation results deterministically.

---

### Edge Cases

- The `RunOutcome` has no assistant text (e.g., a tool-only or empty run): the outcome reader returns an
  empty final text; text/JSON validators fail safe with a clear reason.
- The final output contains multiple JSON-looking fragments: the JSON-schema validator uses a documented,
  deterministic selection (e.g., the last complete assistant text) and never guesses ambiguously.
- A host-supplied rule, scoring function, or schema raises: the pack maps it to a fail-safe `fail` (for
  validators) or a non-fatal diagnostic with no score (for evaluators), never an unhandled crash.
- A regex pattern is invalid: it is rejected when the validator is constructed (a clear error), not at
  apply time.
- An evaluator returns a score outside `[0, 1]` from a host function: the score is recorded as-is (the
  evaluator does not silently clamp) but the length/heuristic packs the layer ships always produce
  `[0, 1]`.
- An all-of combinator over zero validators: returns a documented default (`pass`), and an any-of over
  zero validators returns the documented default (`fail`).
- The threshold gate receives an evaluation with no numeric score: it fails safe with a reason rather
  than treating a missing score as passing.

## Requirements *(mandatory)*

### Functional Requirements

#### Pack Contracts & Outcome Reader

- **FR-001**: Every pack MUST implement a Phase-3 contract: a **validator pack** satisfies the Validator
  Protocol `(RunOutcome, LoopState) -> ValidationResult` and an **evaluator pack** satisfies the
  Evaluator Protocol `(RunOutcome, LoopState) -> EvaluationResult`, so it plugs directly into a Loop
  Definition's `validation_policy` / `evaluation_policy`.
- **FR-002**: The layer MUST provide a public-safe **outcome reader** that extracts, from a `RunOutcome`,
  the terminal reason, the final assistant text, and any artifact references — reading only the public
  surface and never a Phase-1/2 internal.
- **FR-003**: A pack MUST be a **pure callable**: given the same `(RunOutcome, LoopState)` it MUST return
  an equal result every time (determinism), and it MUST NOT start, drive, or observe runs, nor mutate the
  inputs.
- **FR-004**: A pack MUST carry **no secrets and no domain data**; configuration (patterns, schemas,
  thresholds, rules) is supplied by the host and committed examples use only public-safe values.

#### Validators

- **FR-010**: The layer MUST provide a **rule-based validator** that applies a host-supplied predicate
  over the extracted outcome view and returns `pass` / `fail` (with a reason) accordingly.
- **FR-011**: The layer MUST provide a **text validator** supporting `matches` (full regex match),
  `contains`, and `not_contains` modes over the final assistant text, returning `pass` / `fail` with a
  reason; an invalid regex MUST be rejected at construction time.
- **FR-012**: The layer MUST provide a **JSON-schema validator** that requires the final output to parse
  as JSON and validate against a supplied schema, returning `pass` on success and `fail` with the
  violation reason otherwise.
- **FR-013**: The layer MUST provide an **artifact-presence validator** with a "must produce" and a
  "must not produce" mode over the outcome's artifact references.
- **FR-014**: Every validator MUST **fail safe**: malformed or missing input (no text, unparseable JSON,
  a raising host rule) maps to an explicit `fail` (or, where configured, `needs_human_review`) with a
  public-safe reason — never a silent `pass`.

#### Evaluators

- **FR-020**: The layer MUST provide a **scoring evaluator** that applies a host-supplied scoring function
  over the extracted outcome and returns an `EvaluationResult` carrying the numeric score.
- **FR-021**: The layer MUST provide a **label evaluator** that assigns a categorical quality label from
  deterministic rules and returns it (with an optional reason).
- **FR-022**: The layer MUST provide a **length/heuristic evaluator** that returns a deterministic
  measurement (such as normalized output length) as a score in `[0, 1]`.
- **FR-023**: Evaluators MUST be **non-gating** (FR-041 of Phase 3): an evaluator MUST NOT by itself
  decide `fail` / `needs_repair`; only the stop condition or a validator (via the threshold gate) may
  consume a score. A raising host scoring function MUST become a non-fatal diagnostic with no score.

#### Combinators & Threshold Gate

- **FR-030**: The layer MUST provide an **all-of** validator combinator (the combined result is `pass`
  only if every sub-validator passes) and an **any-of** combinator (the combined result is `pass` if at
  least one sub-validator passes), each with a **documented status-combination precedence**.
- **FR-031**: The combinator precedence MUST NOT silently downgrade `needs_human_review` or
  `needs_repair` to a plain `pass` / `fail`; the documented precedence MUST surface the most cautious
  status among sub-results when relevant.
- **FR-032**: The layer MUST provide a **threshold gate** that turns an evaluator's score into a gating
  `ValidationResult` (score at/above the threshold → `pass`; below → a configured `fail` or
  `needs_repair`, with a reason). The threshold gate MUST be the only pack that converts evaluation into
  gating, preserving the Phase-3 non-gating rule (FR-023).
- **FR-033**: The threshold gate MUST fail safe when the evaluation carries no numeric score — returning
  an explicit result with a reason, never treating a missing score as passing.
- **FR-034**: An all-of combinator over zero validators MUST return a documented default (`pass`); an
  any-of over zero validators MUST return the documented default (`fail`).

#### Boundary, Non-Duplication & Extension Points

- **FR-040**: A pack MUST compose only the Phase-3 public contracts and value types
  (`RunOutcome`, `LoopState`, `ValidationResult`, `EvaluationResult`, and the public content-block types)
  and MUST NOT import or call any Phase-1 runtime internal, Phase-2 host internal, or Phase-3
  loop-control internal (the Loop Controller mechanics).
- **FR-041**: A pack MUST NOT start, drive, schedule, or observe runs; it only reads a `RunOutcome` and
  returns a result. It introduces no runtime, scheduler, host, or storage of its own.
- **FR-042**: The layer MUST name, without implementing, the reserved extension points: machine-learning
  or model-graded evaluators, an LLM-as-judge evaluator, external validation services or remote schema
  registries, and a plugin marketplace of third-party packs.
- **FR-043**: The layer MUST NOT implement any out-of-scope capability — an LLM-as-judge, ML scoring,
  remote/external validation calls, cloud deployment, web/UI, or any non-deterministic evaluation. Any
  such need discovered during implementation MUST be deferred to a future-phase specification.

### Non-Functional Requirements

- **NFR-001 (Phase dependency)**: This phase MUST build strictly on the completed Phase-3 loop layer and
  inherit its guarantees; it consumes only the Phase-3 Validator/Evaluator contracts and value types and
  re-derives none of them.
- **NFR-002 (Determinism)**: Given a scripted `RunOutcome`, every pack MUST produce identical
  validation/evaluation results on every run.
- **NFR-003 (Boundary integrity)**: It MUST be auditable that a pack reads only the public `RunOutcome`
  surface and invokes no Phase-1/2/3 internal directly (operationalized by FR-040, FR-041, SC-002).
- **NFR-004 (Public-safety)**: All committed Phase-5 artifacts MUST remain public-safe — no secrets,
  credentials, private paths, private project or repository names, or internal network addresses — and no
  raw private-reference excerpts; packs carry no domain data.
- **NFR-005 (Fail-safe)**: Every pack MUST map a malformed or missing input to an explicit, public-safe
  result with a reason — a validator to `fail` (or `needs_human_review`), an evaluator to a non-fatal
  diagnostic with no score — never a silent `pass` or an unhandled crash.
- **NFR-006 (Minimalism & reversibility)**: The layer MUST stay minimal and independently reversible,
  with no speculative product surface, consistent with the constitution's surgical-scope discipline.

### Key Entities

- **Validator Pack**: A reusable callable implementing the Phase-3 Validator Protocol (rule / text /
  JSON-schema / artifact / combinator / threshold gate).
- **Evaluator Pack**: A reusable callable implementing the Phase-3 Evaluator Protocol (scoring / label /
  length).
- **Outcome Reader**: A public-safe helper that extracts the terminal reason, the final assistant text,
  and artifact references from a `RunOutcome`.
- **Combinator**: An all-of / any-of validator that composes sub-validators with a documented
  status-combination precedence.
- **Threshold Gate**: The single pack that converts an evaluator score into a gating decision.

These pack entities reference Phase-3 entities — `RunOutcome`, `LoopState`, `ValidationResult`,
`EvaluationResult`, and the public content-block types — without redefining them.

## Validator & Evaluator Pack Boundaries

Component ownership for this phase (constitution Principle IV). A pack interacts with the loop only by
*implementing* the Phase-3 Validator/Evaluator contract and reading the public `RunOutcome` — never
through reach-through internal access.

| Component | Owns | Must not |
|---|---|---|
| Outcome Reader | Extracting terminal reason / final text / artifact refs from a `RunOutcome` | Read a Phase-1/2 internal; mutate the outcome |
| Validator Packs | The gating logic for rule / text / JSON-schema / artifact checks and fail-safe handling | Start or drive runs; carry secrets/domain data; silently pass on malformed input |
| Evaluator Packs | The non-gating measurement (score / label / length) | Decide control flow; gate by themselves |
| Combinators | Status-combination precedence for all-of / any-of | Downgrade review/repair to a plain pass/fail |
| Threshold Gate | The single evaluation-to-gating conversion | Let evaluation gate by any other path |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A loop engineer can plug a pack into a Loop Definition's validation/evaluation policy and,
  given a scripted `RunOutcome`, receive a `ValidationResult` / `EvaluationResult` — with a boundary
  audit confirming the pack read only the public surface and called no Phase-1/2/3 internal.
- **SC-002**: 100% of packs in the test suite read only the public `RunOutcome` surface; no test or audit
  can demonstrate a pack importing or calling a Phase-1/2/3 internal or starting a run.
- **SC-003**: Each validator (rule / text / JSON-schema / artifact) returns the correct gating status for
  matching and non-matching outcomes in 100% of suite cases, including the fail-safe path for malformed
  input.
- **SC-004**: Each evaluator (scoring / label / length) returns the expected result and is non-gating in
  100% of suite cases; a length evaluator's score is always within `[0, 1]`.
- **SC-005**: The all-of / any-of combinators produce the documented combined status for every pass/fail/
  review/repair mix tested, never downgrading a cautious status.
- **SC-006**: The threshold gate maps a score at/above the threshold to `pass` and below to the
  configured `fail` / `needs_repair`, and fails safe on a missing score.
- **SC-007**: Every pack is deterministic — applied twice to the same `RunOutcome` it returns equal
  results in 100% of suite cases.
- **SC-008**: Every pack fails safe — a malformed or missing input yields an explicit result with a
  reason (validator `fail`/review, evaluator diagnostic), never a silent `pass` or a crash, in 100% of
  suite cases.
- **SC-009**: A public-safe example plugs packs into a Loop Definition and reproduces its documented
  validation/evaluation results deterministically.
- **SC-010**: Automated public-safety scans of all committed Phase-5 artifacts find zero private
  references, and a review confirms no Phase-1/2/3 internal is re-implemented and no out-of-scope
  capability (LLM-judge, ML scoring, external calls) is built (constitution Principles IV–VI and VIII
  upheld).

## In Scope *(this phase)*

- An outcome reader over the public `RunOutcome` surface.
- Rule-based, text/regex, JSON-schema, and artifact-presence validators with fail-safe handling.
- Scoring, label, and length/heuristic evaluators (non-gating).
- All-of / any-of validator combinators with documented precedence, and a threshold gate.
- Public-safe examples and a docs guide.

## Out of Scope *(this phase)*

- An LLM-as-judge / model-graded evaluator and any machine-learning scoring.
- External validation services, remote schema registries, and remote/network calls.
- A plugin marketplace of third-party packs.
- Cloud deployment, a web/UI, and any non-deterministic evaluation.
- Re-implementing any Phase-1/2/3 internal or starting/driving runs.

## Assumptions

- This phase depends on the completed Phase-3 loop layer
  ([`003-loopplane-loop-engineering-layer`](../003-loopplane-loop-engineering-layer/spec.md)) and
  consumes only its Validator/Evaluator contracts and value types (`RunOutcome`, `LoopState`,
  `ValidationResult`, `EvaluationResult`, content blocks).
- Phase-5 consumers are loop engineers assembling validation/evaluation policies from reusable packs; no
  end-user product host ships in this phase.
- Packs read the public `RunOutcome` surface — its terminal reason and its history of content blocks —
  and never a Phase-1/2 internal.
- Host-supplied configuration (predicates, regex patterns, JSON schemas, thresholds, scoring functions)
  carries the domain specifics; committed examples use only public-safe values.
- Determinism is mandatory: a scripted `RunOutcome` yields identical pack results on every run; no pack
  performs I/O, network calls, or non-deterministic evaluation.
- Specification and documentation artifacts are written in English, consistent with prior phases, and all
  Phase-5 artifacts contain only public-safe content (constitution Principles II and VII).
