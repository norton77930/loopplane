# Phase 0 Research: Validator & Evaluator Packs

**Feature**: `005-loopplane-validator-evaluator-packs` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md)

No `[NEEDS CLARIFICATION]` markers remain. Phase 0 records the design decisions that turn the spec into
implementable packs and the patterns inherited from Phase 3. Each decision cites the requirements it
satisfies.

## Inherited context (no re-derivation — NFR-001)

The packs build strictly on the Phase-3 contracts. The **only** Phase-3 surface they consume:

| Phase-3 public surface (`loopplane.engineering`) | How a pack uses it |
|---|---|
| `Validator` Protocol `(RunOutcome, LoopState) -> ValidationResult` | A validator pack *implements* this Protocol (FR-001). |
| `Evaluator` Protocol `(RunOutcome, LoopState) -> EvaluationResult` | An evaluator pack *implements* this Protocol (FR-001). |
| `ValidationResult(status, reason, metadata)` / `ValidationStatus` | A validator pack returns these (FR-010–FR-014). |
| `EvaluationResult(score, label, reason, metadata)` | An evaluator pack returns these (FR-020–FR-022). |
| `RunOutcome(session_id, termination_reason, turns_taken, history, consumer_failures)` | Read-only input; packs read `termination_reason` and `history` (FR-002). |
| `LoopState(... artifacts: tuple[ArtifactRef, ...] ...)` | Read-only input; the artifact validator reads `state.artifacts` (FR-013). |
| `HistoryEntry(role, blocks)` + `TextBlock(text)` (value types via the host) | The outcome reader extracts the final assistant text (FR-002). |

**Non-duplication (FR-040)**: packs add no runtime, host, scheduler, or storage; they only read a
`RunOutcome`/`LoopState` and return a result.

## Decision 1 — A shared, read-only Outcome Reader

- **Decision**: A small `read_outcome(outcome, state) -> OutcomeView` helper extracts a stable view:
  `terminal_reason` (= `outcome.termination_reason`), `final_text` (the concatenated `TextBlock` text of
  the **last `assistant` history entry**, empty when none), and `artifact_references` (the `reference`
  strings from `state.artifacts`). Every pack reads the outcome through this one helper.
- **Rationale**: FR-002, SC-002. One reader means every pack reads the same public surface the same way,
  and the boundary audit has a single, auditable extraction point. Using the **last assistant entry**
  resolves the "multiple JSON fragments" ambiguity deterministically (edge case).
- **Alternatives rejected**: *Each pack parses `history` itself* — duplicates extraction logic and risks
  inconsistent reads; rejected.

## Decision 2 — Packs are pure callables (functions returning closures)

- **Decision**: Each pack is a constructor function returning a callable that matches the Phase-3
  Protocol, e.g. `text_validator(contains="ok") -> Validator`. The returned callable is sync, pure, and
  closes over its (host-supplied, public-safe) configuration. The Phase-3 controller already awaits
  sync-or-async policy callables, so sync packs plug in directly.
- **Rationale**: FR-001, FR-003, NFR-002. Closures keep configuration explicit and the call deterministic;
  sync keeps packs simple and side-effect-free (no I/O, no network).
- **Alternatives rejected**: *Classes with `__call__`* — heavier than needed for stateless config; a
  closure expresses the one-method contract directly (matches the Phase-1/2/3 seam style). Either is
  Protocol-compatible; the closure form is chosen for brevity.

## Decision 3 — Fail-safe is the default for every pack

- **Decision**: A validator that hits malformed/missing input (no text, unparseable JSON, a raising host
  rule/schema) returns `ValidationResult(status="fail", reason=...)` (or `needs_human_review` when the
  pack is explicitly configured to escalate) — never a silent `pass`. An evaluator whose host scoring
  function raises returns an `EvaluationResult` with `score=None` and a `reason` (a non-fatal
  diagnostic), consistent with the Phase-3 evaluator-error rule.
- **Rationale**: FR-014, FR-023, NFR-005, SC-008. Encodes the spec's "never a silent pass" guarantee at
  the pack level and mirrors the Phase-3 fail-safe discipline.
- **Alternatives rejected**: *Raise on malformed input* — would crash the loop iteration; the loop's own
  fail-safe would catch it, but a pack-level explicit `fail` with a reason is clearer and testable.

## Decision 4 — JSON-schema validation reuses the existing `jsonschema` dependency

- **Decision**: The JSON-schema validator parses `final_text` with the stdlib `json` module and validates
  against the supplied schema using `jsonschema` (already a core dependency). A parse error or a schema
  violation → `fail` with the reason; a valid match → `pass`.
- **Rationale**: FR-012, NFR-002. No new dependency; `jsonschema` is deterministic and already vendored.
  Parsing with stdlib `json` keeps the JSON handling explicit.
- **Alternatives rejected**: *Hand-rolled schema checks* — re-implements a solved problem; *a new schema
  library* — unnecessary, `jsonschema` is present.

## Decision 5 — Regex compiled (and validated) at construction time

- **Decision**: The text validator compiles its pattern with `re` when the pack is **constructed**; an
  invalid pattern raises a clear `PackConfigError` then, not at apply time. Modes: `matches` (full-string
  `re.fullmatch`), `contains` (`re.search`), `not_contains` (`re.search` must miss).
- **Rationale**: FR-011, edge case. Construction-time validation fails fast and keeps the apply path pure
  and deterministic.
- **Alternatives rejected**: *Compile per call* — wasteful and defers errors to run time.

## Decision 6 — Evaluators are strictly non-gating; one explicit threshold gate

- **Decision**: Evaluator packs return only `EvaluationResult`; none returns a `ValidationResult`. The
  **threshold gate** is a *validator* pack that takes an evaluator plus a threshold and a below-threshold
  status (`fail` or `needs_repair`), runs the evaluator, and maps the score to a gating decision; a
  missing/`None` score → fail-safe `fail` with a reason. This is the only place evaluation becomes gating.
- **Rationale**: FR-023, FR-032, FR-033, SC-006. Preserves the Phase-3 non-gating rule while giving a
  single, explicit, testable conversion path.
- **Alternatives rejected**: *Let evaluators optionally gate* — blurs the non-gating contract; rejected.

## Decision 7 — Combinator status precedence is documented and cautious

- **Decision**: `all_of(*validators)` passes only if every sub-validator passes; `any_of(*validators)`
  passes if at least one passes. When combining, the **most cautious** status wins in this precedence:
  `needs_human_review` > `needs_repair` > `fail` > `pass`. So an all-of with a `pass` and a
  `needs_human_review` yields `needs_human_review`; an any-of where one passes yields `pass`, else the
  most cautious among the failures. Empty `all_of` → `pass`; empty `any_of` → `fail` (documented
  defaults).
- **Rationale**: FR-030, FR-031, FR-034, SC-005. A documented precedence that never silently downgrades a
  review/repair request to a plain pass/fail.
- **Alternatives rejected**: *First-failure-wins* — could hide a more cautious later status; the
  precedence ordering is clearer and order-independent.

## Decision 8 — Artifact presence reads Loop State, not run internals

- **Decision**: The artifact-presence validator reads `state.artifacts` (the Phase-3 `LoopState`
  reference-only artifact list the loop already captured) — `require=True` passes when ≥1 reference
  exists, `require=False` ("must not produce") passes when none exist.
- **Rationale**: FR-013, FR-040. Reads only the public Loop State surface; no reach into the artifact
  store or run history.
- **Alternatives rejected**: *Scan `outcome.history` for artifact blocks* — the loop already exposes
  artifact references on `LoopState`; reusing them avoids duplicating extraction.

## Best-practice patterns reused from Phases 1–3

- **Frozen dataclasses + closures** for the `OutcomeView` and pack configuration; deterministic, pure.
- **Scripted `RunOutcome` fixtures** built via the Phase-3 host helpers (or constructed directly) are the
  deterministic test instruments (NFR-002, SC-007) — no credentials, no network.
- **Import-boundary audit + public-safety scan extension** for the new `loopplane.packs` package
  (NFR-003, NFR-004, SC-002, SC-010).
- **One package per boundary**: a single new `loopplane.packs` sub-package, additive and reversible.

## Open risks carried into design (not blockers)

| Risk | Handling in Phase 1 design |
|---|---|
| A pack reaching past the public outcome surface | Import-boundary test asserts `loopplane.packs` imports only `loopplane.engineering` (+ value types, stdlib, `jsonschema`), never Phase-1/2 internals (NFR-003, SC-002). |
| A silent pass on malformed input | Every pack fails safe to an explicit `fail`/diagnostic with a reason; a dedicated fail-safe test per pack (NFR-005, SC-008). |
| Evaluation leaking into gating | Evaluators return only `EvaluationResult`; only the threshold gate converts (FR-032); a test asserts no evaluator gates (SC-004). |
| Non-determinism creeping in | Packs do no I/O/network and use deterministic stdlib (`re`, `json`, `jsonschema`); a determinism test applies each pack twice (NFR-002, SC-007). |
| A secret/domain datum committed in a pack | Packs carry no domain data; config is host-supplied; examples use public-safe values; public-safety scan over committed files (NFR-004, SC-010). |

**Output**: all design unknowns resolved; ready for Phase 1.
