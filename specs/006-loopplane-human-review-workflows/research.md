# Phase 0 Research: Human Review Workflows

**Feature**: `006-loopplane-human-review-workflows` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

No `[NEEDS CLARIFICATION]` markers remain. Phase 0 records the design decisions that turn the spec into an
implementable review-workflow layer, grounded in a read-only survey of the existing human-review surface
across Phases 1 and 3. Each decision cites the requirements it satisfies.

## Inherited context (no re-derivation — NFR-001)

The layer builds strictly on the Phase-3 review hook. The **only** Phase-3 surface it consumes (all
exported from `loopplane.engineering`):

| Phase-3 public surface | How the review layer uses it |
|---|---|
| `run_loop(definition, *, on_loop_event=, on_approval=, review_resolver=) -> LoopOutcome` | The single entry point; the gate is passed as `review_resolver` (FR-010, FR-012). |
| `ReviewResolver = Callable[[LoopState], ReviewDecision \| Awaitable[ReviewDecision]]` | The contract the gate builder *produces* (FR-010). |
| `ReviewDecision(approve: bool, reason: str \| None)` (Phase-3) | The decision the gate returns; the Phase-6 decision maps down to it (FR-004). |
| `LoopOutcome(..., terminal_event, state, ...)` + `.paused` | The paused result `inspect_paused` reads (FR-020). |
| `LoopState(loop_id, loop_definition_id, iteration_index, run_refs, latest_validation, artifacts, approval_status, ...)` | The public state a Review Request is built from (FR-001). |
| `LoopDefinition` | Passed through to `run_loop` for gated runs and resume (FR-021). |

**Survey finding (the boundary, FR-061)**: Phase-1 owns the *in-run tool* approval boundary
(`HumanApproval`, `InteractionBroker`, `RunContext.session_approval_memory`, the `approval-requested` /
`question-asked` runtime events) — that governs whether a *tool call* runs, surfaced to a host through the
host's `on_approval`. Phase-6 review is a **loop-level acceptance** concern (does a human accept an
iteration's outcome?) and MUST NOT re-implement or reach into that Phase-1 machinery. The two are kept
distinct.

## Decision 1 — The gate is a built Phase-3 `ReviewResolver`

- **Decision**: `build_review_resolver(reviewer, *, memory=None, asker=None, on_event=None)` returns an
  **async** Phase-3 `ReviewResolver` `(LoopState) -> ReviewDecision`. Inside, per call it: builds a Review
  Request from the Loop State, consults memory, otherwise invokes the reviewer (with a Review Context),
  records the decision, emits review events, and returns the **mapped** Phase-3 decision. The host passes
  it to `run_loop(review_resolver=...)`.
- **Rationale**: FR-010, FR-011, FR-012, SC-001/002. There is exactly one auditable path — the gate only
  *supplies* the resolver `run_loop` calls; it starts no run itself and reads only the public Loop State.
- **Alternatives rejected**: *A bespoke loop driver* — would duplicate Phase-3 control flow and break the
  boundary; the resolver-builder composes cleanly on the existing hook.

## Decision 2 — Review Request is built from the public Loop State

- **Decision**: `build_review_request(state, *, options=DEFAULT_OPTIONS) -> ReviewRequest` reads
  `state.loop_id`, `state.loop_definition_id`, `state.iteration_index`, the last `run_refs` entry's
  `session_id`, `state.latest_validation` (status + reason → the **cause**), and `state.artifacts`. The
  cause is `validator_status` when a validation result exists, else `fail_safe`.
- **Rationale**: FR-001, FR-040. Reads only the public Loop State surface — no Phase-1/2 internal — so the
  request is deterministic and the boundary holds.
- **Alternatives rejected**: *Reading the Runtime Event stream or run history* — unnecessary; the Loop
  State already exposes everything a reviewer needs by reference.

## Decision 3 — Review Decision vocabulary maps down to the Phase-3 decision

- **Decision**: `ReviewOutcome = Literal["approve", "reject", "request_changes"]`. The Phase-6
  `ReviewDecision(outcome, reason=None, reviewer=None, metadata={})` maps to Phase-3:
  `approve → ReviewDecision(approve=True, reason)`, `reject`/`request_changes` →
  `ReviewDecision(approve=False, reason)`. The mapping is total and **never maps a non-approval to
  approval** (FR-004).
- **Rationale**: FR-002, FR-004, SC-003. A richer vocabulary for hosts while preserving the binary Phase-3
  gate; `request_changes` is a non-approval that a host can distinguish in its own logic/metadata while the
  loop fails (the loop has no "revise-and-continue" path this phase).
- **Alternatives rejected**: *Adding a loop continuation for `request_changes`* — that would require new
  Phase-3 control flow (out of scope; the loop's repair path is validator-driven, not review-driven).

## Decision 4 — Fail-safe everywhere; never a silent approve

- **Decision**: A reviewer that raises or returns an unrecognized outcome maps to a **non-approval**
  Phase-3 decision (`approve=False`) with a diagnostic reason. `inspect_paused` on a terminal outcome
  returns `None`. A missing question asker makes `ask` raise a clear `ReviewError` (the reviewer handles
  it) or, if the reviewer ignores asking, the review proceeds; a raising asker becomes a diagnostic and
  the ask returns an empty answer list.
- **Rationale**: FR-013, FR-043, NFR-005, SC-009. Mirrors the Phase-3 / packs fail-safe discipline — an
  ambiguous review never silently approves, crashes, or hangs.
- **Alternatives rejected**: *Defaulting an unknown reviewer outcome to approve* — forbidden; the safe
  default is non-approval.

## Decision 5 — Review Memory remembers by key, in process

- **Decision**: `ReviewMemory(*, remember=RememberMode, key=default_review_key)` stores a decision under a
  **review key** derived from the request (`default_review_key` = the `loop_id`). `RememberMode =
  Literal["approvals", "rejections", "both"]` governs which outcomes are stored. A later review whose key
  is present resolves from memory without invoking the reviewer, recording the source as memory. Memory is
  in process; durable persistence is reserved.
- **Rationale**: FR-030–FR-033, SC-005. The loop-level parallel of Phase-1 session approval memory, kept
  decoupled (its own store, its own key) so it never crosses unrelated reviews. The default per-loop key
  never crosses loop ids; a host can supply a finer key.
- **Alternatives rejected**: *Reusing `RunContext.session_approval_memory`* — that is Phase-1 in-run tool
  memory, a different concern and a boundary violation (FR-061).

## Decision 6 — Review Context carries a question channel; questions are host-asked

- **Decision**: The gate passes a `ReviewContext` to the reviewer with an async `ask(questions) ->
  list[str]` method. `ask` emits `review_question_asked`, delegates to a host-supplied
  `QuestionAsker = Callable[[Sequence[ReviewQuestion]], Sequence[str] | Awaitable[...]]`, emits
  `review_question_answered`, and returns the answers. With no asker, `ask` raises `ReviewError`
  (fail-safe). The reviewer is `(ReviewRequest, ReviewContext) -> ReviewDecision | Awaitable`.
- **Rationale**: FR-041–FR-043, SC-006. Lets a reviewer gather context with review-level events, without
  re-implementing the Phase-1 in-run question machinery (FR-061) — the asker is the host's own channel.
- **Alternatives rejected**: *Routing review questions through the Phase-1 `InteractionBroker`* — a
  boundary violation and conceptually wrong (that is in-run, per-tool questioning).

## Decision 7 — A distinct Review Event stream, off by default

- **Decision**: Review Events (`review_requested`, `review_question_asked`, `review_question_answered`,
  `review_decided`, `review_resolved_from_memory`) form a stream distinct from Loop Events and Runtime
  Events. Emission to an external sink is gated by an observation flag (the presence of an `on_event`
  sink); when absent, decisions and outcomes are byte-identical (FR-052, NFR-006, SC-008). Versioned with a
  `REVIEW_SCHEMA_VERSION`; consumers tolerate unknown types.
- **Rationale**: FR-050–FR-052. Parity with the Phase-1/3/4 observability discipline; the review stream
  never wraps or re-emits Loop or Runtime Events.
- **Alternatives rejected**: *Emitting onto the Loop Event stream* — blurs the boundary (distinction in
  the spec); rejected.

## Decision 8 — Pause / inspect / resume is in-process (durable resume reserved)

- **Decision**: `inspect_paused(outcome) -> ReviewRequest | None` reads a paused `LoopOutcome`.
  `resume_review(definition, decision, *, on_event=None) -> LoopOutcome` re-drives the
  Loop Run through `run_loop` with a one-shot resolver that returns the mapped decision. Durable
  cross-restart resume (re-attaching to a serialized paused run without re-driving) is **named, not built**
  (FR-022, FR-062, consistent with Phase-3 FR-064).
- **Rationale**: FR-020–FR-022, SC-004. Honest, deterministic in-process resume on the existing hook; the
  re-drive reproduces the same scripted run up to the gate, then applies the decision.
- **Alternatives rejected**: *Persisting and re-attaching the paused run* — requires Phase-3 internals and
  durable state; explicitly reserved this phase.

## Best-practice patterns reused from Phases 1–5

- **Frozen dataclasses + `Protocol` seams** for requests/decisions/reviewer/asker; the single mutable
  record is `ReviewMemory`, host-owned.
- **Scripted loop + scripted reviewer + scripted answers** as the deterministic test instruments
  (NFR-002, SC-007) — built on the Phase-3 scripted-host helpers; no credentials, no network.
- **Versioned, additively-evolving event vocabulary** with a `REVIEW_SCHEMA_VERSION` constant and
  unknown-type tolerance.
- **Import-boundary audit + public-safety scan extension** for the new `loopplane.review` package
  (NFR-003, NFR-004, SC-002, SC-010).
- **One package per boundary**: a single new `loopplane.review` sub-package, additive and reversible.

## Open risks carried into design (not blockers)

| Risk | Handling in Phase 1 design |
|---|---|
| Reaching into the Phase-1 approval/question machinery | Import-boundary test asserts `loopplane.review` imports only `loopplane.engineering` (+ stdlib); a separate assertion that no Phase-1 approval/interaction symbol is referenced (FR-061, NFR-003, SC-002). |
| A silent approve on a faulted/ambiguous review | Every fail-safe maps to a non-approval decision with a diagnostic; dedicated fail-safe tests (FR-013, NFR-005, SC-009). |
| Review questions hanging with no asker | `ask` with no asker raises a clear `ReviewError`; an asker that raises becomes a diagnostic with an empty answer (FR-043). |
| Non-determinism creeping in | The layer does no I/O/network; review memory and key derivation are pure; a determinism test runs a gated review twice (NFR-002, SC-007). |
| A secret leaking through a request/decision | Requests/decisions carry no secrets; reviewers/askers/keys are host objects; public-safety scan over committed files (NFR-004, SC-010). |

**Output**: all design unknowns resolved; ready for Phase 1.
