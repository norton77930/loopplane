# Feature Specification: Human Review Workflows

**Feature Branch**: `006-loopplane-human-review-workflows`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Extend approval boundaries into human review workflows on top of the
completed Loop Engineering Layer (003): a structured review request, a review-level user question event,
review approval memory, a review decision, pause/resume, and a human gate loop. The layer composes the
Phase-3 in-process review hook (`run_loop(review_resolver=...)`, the paused `LoopOutcome`, and
`LoopState.approval_status`) into reusable, deterministic, public-safe human-review workflows — never
bypassing the loop layer, never reaching into Phase-1/2 internals, and never starting runs by any path
other than the Phase-3 entry point. No UI is in scope unless separately specified. Durable cross-restart
resume, multi-level/consensus escalation, and external audit storage remain reserved extension points."

## Feature Overview

LoopPlane's third phase delivered the **Loop Engineering Layer**: an outer control loop that, when a
Validator returns `needs_human_review` (or fails safe), emits a `human_review_requested` Loop Event, sets
`LoopState.approval_status = pending`, and either **pauses** (returning a `LoopOutcome` with no terminal
event) or resolves an in-process **`ReviewResolver`** — a host-supplied callable
`(LoopState) -> ReviewDecision` — that approves (→ `loop_completed`) or rejects (→ `loop_failed`) (see
[`../003-loopplane-loop-engineering-layer/spec.md`](../003-loopplane-loop-engineering-layer/spec.md)).
Phase 3 deliberately shipped only the bare resolver hook and the pause; it named **durable resume**,
**multi-level escalation**, **decision auditing**, and **external review storage** as reserved extension
points.

Phase 6 builds the **Human Review Workflow** layer that turns that bare hook into reusable, structured,
deterministic human-review workflows. It introduces a **Review Request** (what is being reviewed and
why, built from the paused Loop State), a richer **Review Decision** (approve / reject / request changes,
with a reason, a reviewer identity, and metadata), a **Reviewer** contract a host implements, a
**Review Context** through which a reviewer can ask the human structured **review questions** before
deciding, a **Review Memory** that remembers decisions by a review key so repeated reviews auto-resolve,
a **review-gate builder** that composes these into a Phase-3 `ReviewResolver` (the **human gate loop**),
and a distinct **Review Event** stream. It also defines the **pause / inspect / resume** path for
out-of-band review.

The layer adds **no runtime, host, or loop internals of its own**: every Loop Run is started through the
Phase-3 `run_loop`, and the layer reads only the public `LoopState` / `LoopOutcome` surface. It never
reaches into the Phase-1 Human Approval boundary or the Phase-1 question machinery (those govern in-run
*tool* approval and are surfaced separately through the host); Phase-6 review is a **loop-level** concern
about whether an iteration's outcome is accepted by a human.

### Core Distinctions

This phase adds a structured workflow *behind* the Phase-3 review hook; it does not change the loop. The
following distinctions are normative.

| # | Phase-3 concept (hook) | Phase-6 concept (workflow) |
|---|---|---|
| 1 | **`ReviewResolver`** — a bare callable `(LoopState) -> ReviewDecision`, host-supplied; the loop hardcodes no review logic. | **Review gate** — a `ReviewResolver` *built by this layer* from a Reviewer (+ memory, + question channel) that the host composes once and reuses. |
| 2 | **`ReviewDecision`** (Phase-3) — `approve: bool` + optional `reason`. | **Review Decision** (Phase-6) — `outcome ∈ {approve, reject, request_changes}` + `reason` + optional `reviewer` + `metadata`, mapped down to the Phase-3 decision. |
| 3 | **`human_review_requested`** Loop Event — a bare loop-level signal with a `cause`. | **Review Request** — the structured description a reviewer sees: loop id, iteration, the run reference, the cause, the outcome-under-review (validation result, final output, artifacts), and the allowed decision options. |
| 4 | **paused `LoopOutcome`** — terminal_event None, `.paused`, carrying the Loop State. | **Pause / inspect / resume** — `inspect_paused(outcome)` extracts a Review Request from a paused outcome; the host forms a decision out-of-band and resumes by supplying it. |
| 5 | Phase-1 **session approval memory** (in-run *tool* approval, `RunContext.session_approval_memory`). | **Review Memory** — a loop-level remember-the-decision store keyed by a review key, so a repeated identical review auto-resolves without re-asking the reviewer. Distinct from Phase-1 tool-approval memory. |

**Implemented this phase vs reserved extension points**:

- **Implemented**: Review Request, Review Decision, the Reviewer contract, a Review Context with a
  review-question channel, Review Memory, the review-gate builder (the human gate loop), the
  pause/inspect/resume path, a distinct Review Event stream, and fail-safe handling.
- **Reserved (named, not built)**: durable cross-restart resume from a paused review (the in-process
  resolver/re-drive path is the only resume this phase, consistent with Phase-3 FR-064); multi-level or
  consensus review (multiple reviewers, escalation chains); external/persistent review storage,
  databases, webhooks, or callback infrastructure; structured audit trails beyond the decision's reason
  and metadata; and any review UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gate a loop on a human reviewer (Priority: P1)

A platform developer implements a **Reviewer** — a callable that, given a **Review Request**, returns a
**Review Decision** (approve / reject / request_changes). They build a **review gate** from it and pass
it to `run_loop` as the Phase-3 `review_resolver`. When the loop reaches `needs_human_review`, the gate
constructs a Review Request from the Loop State, invokes the reviewer, records the decision, and maps it
to the Phase-3 decision so the loop resumes — completing on approve and failing on reject — without the
layer touching any Phase-1/2 internal.

**Why this priority**: The review gate is the minimum viable human-review workflow and the point of the
phase. It is independently demonstrable with a scripted loop that needs review and a one-line scripted
reviewer.

**Independent Test**: Build a review gate from a scripted reviewer that approves, run a loop that returns
`needs_human_review`, and assert the loop completes; swap the reviewer to reject and assert the loop
fails; assert the Review Request the reviewer saw carried the loop id, iteration, run reference, and the
validation reason.

**Acceptance Scenarios**:

1. **Given** a review gate built from a reviewer that approves, **When** a loop returns
   `needs_human_review`, **Then** the gate constructs a Review Request, the reviewer approves, and the
   loop ends with `loop_completed`.
2. **Given** a review gate built from a reviewer that rejects, **When** the loop returns
   `needs_human_review`, **Then** the loop ends with `loop_failed` carrying the reviewer's reason.
3. **Given** a reviewer that returns `request_changes`, **When** it is mapped to the Phase-3 decision,
   **Then** the loop does not silently complete — it follows the documented mapping (non-approval).
4. **Given** the running gate, **When** a boundary audit inspects how the loop was driven, **Then** it
   confirms the gate started no run by any path other than the Phase-3 `run_loop` and read only the
   public Loop State surface.

---

### User Story 2 - Pause, inspect, and resume a review out of band (Priority: P2)

A platform developer runs a loop **without** a resolver so it **pauses** at `needs_human_review`. They
call **`inspect_paused`** on the paused `LoopOutcome` to obtain the structured Review Request, present it
to a human out of band, and later **resume** the review by supplying a Review Decision — completing or
failing the loop. Durable cross-restart resume is not built; the resume drives the same loop with the
supplied decision in process.

**Why this priority**: The pause/inspect/resume path is how a host integrates asynchronous, out-of-band
human review. It builds on the Review Request from User Story 1.

**Independent Test**: Run a loop with no resolver, assert it pauses, call `inspect_paused` and assert the
Review Request matches the paused Loop State; then resume with an approve decision and assert the loop
completes, and separately with a reject decision and assert it fails.

**Acceptance Scenarios**:

1. **Given** a loop run with no review gate, **When** it returns `needs_human_review`, **Then** it pauses
   (`outcome.paused`), and `inspect_paused(outcome)` returns a Review Request describing the pause.
2. **Given** a paused outcome, **When** `inspect_paused` is called on a non-paused (terminal) outcome,
   **Then** it returns nothing (or a clear empty result) — there is nothing to review.
3. **Given** a paused review and an approve decision, **When** the host resumes the review, **Then** the
   loop ends with `loop_completed`; with a reject decision it ends with `loop_failed`.
4. **Given** the resume path, **When** it runs, **Then** it starts the Loop Run only through the Phase-3
   entry point and never persists state to disk (durable resume remains reserved).

---

### User Story 3 - Remember review decisions with review memory (Priority: P3)

A platform developer attaches a **Review Memory** to the gate. After a reviewer decides, the gate stores
the decision under a **review key** derived from the request (for example, the loop id, or a host-supplied
key). On a later review whose key matches, the gate resolves from memory **without** re-invoking the
reviewer, recording that the decision came from memory. The host configures which outcomes are remembered
(approvals, rejections, or both) and the key derivation.

**Why this priority**: Review memory removes repeated identical human prompts and is the loop-level
parallel of Phase-1's session approval memory. It builds on the gate from User Story 1.

**Independent Test**: Run two reviews with the same key through a gate with memory; assert the reviewer is
invoked once and the second review resolves from memory with the same decision, and that a review-event
records the memory hit.

**Acceptance Scenarios**:

1. **Given** a gate with review memory and a reviewer that approves, **When** the same review key is seen
   twice, **Then** the reviewer is invoked once and the second resolves from memory to the same decision.
2. **Given** memory configured to remember approvals only, **When** a rejection occurs, **Then** the next
   review with that key still invokes the reviewer (the rejection was not remembered).
3. **Given** a memory hit, **When** the review resolves, **Then** a review event records the resolution
   source as memory (auditability), distinct from a reviewer resolution.
4. **Given** two different review keys, **When** each is reviewed, **Then** a memory entry for one never
   resolves the other.

---

### User Story 4 - Ask the human review questions before deciding (Priority: P4)

A platform developer's reviewer needs clarifying information. Through a **Review Context** the gate passes
to the reviewer, the reviewer **asks structured review questions** and receives answers via a
host-supplied **question asker**; the gate emits review-level `review_question_asked` and
`review_question_answered` events. The reviewer then forms its Review Decision. When no asker is
configured, asking is unavailable and the reviewer decides without questions.

**Why this priority**: Review questions let a human gather context before deciding. They build on the gate
and are genuinely optional, so they sit below the core gate, pause/resume, and memory.

**Independent Test**: Build a gate with a scripted question asker; use a reviewer that asks one question
and decides based on the scripted answer; assert the answer reached the reviewer, the
`review_question_asked` / `review_question_answered` events were emitted, and the decision reflects the
answer.

**Acceptance Scenarios**:

1. **Given** a reviewer that asks a review question and a configured asker, **When** the gate runs,
   **Then** the asker receives the question, its answer reaches the reviewer, and the decision reflects
   it.
2. **Given** the question channel, **When** a review question is asked and answered, **Then** the gate
   emits `review_question_asked` then `review_question_answered` in order.
3. **Given** no configured asker, **When** the reviewer attempts to ask, **Then** the layer fails safe —
   a clear, public-safe error or an empty-answer result the reviewer can handle — never a silent hang.
4. **Given** an asker that raises, **When** it is invoked, **Then** the error is surfaced as a diagnostic
   and the review proceeds to a safe default (the reviewer decides with no answer), never crashing the
   loop.

---

### User Story 5 - Observe review events and keep the edges honest (Priority: P5)

A platform developer consumes a distinct **Review Event** stream — `review_requested`,
`review_question_asked`, `review_question_answered`, `review_decided`, and `review_resolved_from_memory` —
to drive auditing and dashboards, with observation defaulting off. The Review Decision's reason and
metadata carry the decision rationale. The reserved extension points (durable resume, multi-level /
consensus review, external storage, structured audit trails, review UI) are named but not built.

**Why this priority**: The review event stream and the reserved-edge definitions are what the phase
commits to versus what it reserves. They depend on the machinery in Stories 1–4 existing.

**Independent Test**: Run a gated review with observation on and assert the ordered review-event sequence;
run it with observation off and assert decisions and outcomes are identical with no events emitted;
confirm the layer exposes no durable-resume, multi-reviewer, or external-storage capability.

**Acceptance Scenarios**:

1. **Given** observation enabled, **When** a gated review runs (with a question and a decision), **Then**
   the review events `review_requested → review_question_asked → review_question_answered →
   review_decided` are emitted in order.
2. **Given** observation disabled, **When** the same review runs, **Then** the decision and loop outcome
   are identical and no review event is emitted.
3. **Given** a Review Decision, **When** it is recorded, **Then** its reason and optional metadata are
   carried into the `review_decided` event and the loop outcome's diagnostics where applicable.
4. **Given** the layer's public surface, **When** it is inspected, **Then** it offers no durable
   cross-restart resume, no multi-reviewer/consensus orchestration, and no external storage — those are
   documented reserved extension points.

---

### Edge Cases

- A reviewer raises or returns an unrecognized outcome: the gate fails safe — mapping to a non-approval
  Phase-3 decision (the loop does not complete) with a diagnostic — never a silent approve.
- `inspect_paused` is given a terminal (non-paused) outcome: it returns no Review Request; there is
  nothing to review.
- A review memory key collides across unrelated reviews because the host's key derivation is too coarse:
  the layer resolves from memory as configured and documents that key derivation is the host's
  responsibility; a per-loop default key never crosses loop ids.
- The reviewer asks a question but no asker is configured: asking fails safe (a clear error/empty result),
  and the reviewer must handle it; the loop never hangs.
- A reviewer approves on a fail-safe (validator-fault) review: the gate honors it but records the cause so
  the approval of a faulted iteration is auditable.
- Observation is disabled: the review decision and loop outcome are identical to an observed run; only
  event emission differs.
- The same review gate is reused across sequential Loop Runs: each Loop Run's review is independent; only
  an explicitly shared Review Memory carries decisions across runs.

## Requirements *(mandatory)*

### Functional Requirements

#### Review Request, Decision & Reviewer

- **FR-001**: The layer MUST define a structured, public-safe **Review Request** built from a paused or
  in-gate **Loop State**, carrying: the `loop_id`, the `loop_definition_id`, the current iteration index,
  the run reference (`session_id`) under review, the review **cause** (validator status or fail-safe),
  the latest validation result (status + reason), any artifact references, and the allowed decision
  outcomes. It MUST read only the public Loop State surface (FR-040).
- **FR-002**: The layer MUST define a **Review Decision** carrying an `outcome` of `approve` / `reject` /
  `request_changes`, an optional human-readable `reason`, an optional `reviewer` identity, and optional
  structured `metadata` — all public-safe.
- **FR-003**: The layer MUST define a **Reviewer** contract: a host-supplied callable that, given a Review
  Request and a Review Context, returns a Review Decision (sync or async). The layer MUST hardcode no
  domain-specific review logic.
- **FR-004**: The layer MUST map a Review Decision to the Phase-3 `ReviewDecision`: `approve` →
  `ReviewDecision(approve=True, reason=...)`; `reject` and `request_changes` →
  `ReviewDecision(approve=False, reason=...)`. The mapping MUST be documented and MUST never map a
  non-approval outcome to approval.

#### Review Gate (the human gate loop)

- **FR-010**: The layer MUST provide a **review-gate builder** that composes a Reviewer (and optional
  Review Memory and question asker) into a Phase-3 `ReviewResolver` suitable for
  `run_loop(review_resolver=...)`. The gate is the human gate loop: pause → request → (memory? question?
  reviewer) → decide → resume.
- **FR-011**: When invoked by the loop at a review point, the gate MUST construct a Review Request from
  the Loop State, obtain a Review Decision (from memory or the reviewer), record it, and return the mapped
  Phase-3 decision so the loop resumes (completes on approve, fails on reject/request_changes).
- **FR-012**: The gate MUST start, drive, or observe **no** Loop Run by any path other than the Phase-3
  entry point; it only supplies the resolver that `run_loop` calls (FR-040).
- **FR-013**: The gate MUST **fail safe**: a reviewer that raises or returns an unrecognized outcome maps
  to a non-approval Phase-3 decision with a diagnostic — never a silent approve.

#### Pause / Inspect / Resume

- **FR-020**: The layer MUST provide **`inspect_paused`**: given a paused `LoopOutcome`, it returns the
  structured Review Request describing the pause; given a terminal (non-paused) outcome, it returns no
  Review Request.
- **FR-021**: The layer MUST provide a **resume** operation: given a loop and a Review Decision, it drives
  the Loop Run through the Phase-3 entry point supplying that decision and returns the terminal outcome.
- **FR-022**: Resume MUST be **in-process** only this phase; durable cross-restart resume (re-attaching to
  a serialized paused run without re-driving) is a reserved extension point and MUST NOT be implemented
  (FR-091, consistent with Phase-3 FR-064).

#### Review Memory (approval memory)

- **FR-030**: The layer MUST provide a **Review Memory** that remembers a Review Decision under a **review
  key** derived from the Review Request (a per-loop default key, or a host-supplied key function), and
  resolves a later matching review from memory without re-invoking the reviewer.
- **FR-031**: Review Memory MUST be configurable for **which outcomes are remembered** (approvals only,
  rejections only, or both); an outcome not configured for remembering MUST re-invoke the reviewer next
  time.
- **FR-032**: A review resolved from memory MUST record its **resolution source** as memory (distinct from
  a reviewer resolution) for auditability, and MUST NOT cross unrelated review keys.
- **FR-033**: Review Memory is **in-process** and host-owned; durable persistence of review memory is a
  reserved extension point (FR-091).

#### Review Questions (user question event)

- **FR-040 (Boundary)**: Every Loop Run the layer drives MUST be started through the Phase-3 `run_loop`,
  and the layer MUST read only the public Loop State / Loop Outcome surface. It MUST NOT import or call any
  Phase-1 runtime internal (including the Phase-1 Human Approval boundary and the in-run question
  machinery), any Phase-2 host internal, or any Phase-3 loop-control internal.
- **FR-041**: The layer MUST provide a **Review Context** passed to the reviewer through which the reviewer
  can **ask structured review questions** of the human, receiving answers from a host-supplied **question
  asker**. The question asker and the questions are public-safe and carry no secrets.
- **FR-042**: When a question asker is configured, asking a review question MUST emit
  `review_question_asked` and, on an answer, `review_question_answered`, in order, and deliver the answers
  to the reviewer.
- **FR-043**: When **no** asker is configured, asking MUST fail safe with a clear, public-safe error or an
  empty-answer result the reviewer can handle — never a silent hang. An asker that raises MUST be surfaced
  as a diagnostic, and the review MUST proceed to a safe default (the reviewer decides with no answer),
  never crashing the Loop Run.

#### Review Events

- **FR-050**: The layer MUST emit a distinct **Review Event** stream (separate from Loop Events and Runtime
  Events): `review_requested`, `review_question_asked`, `review_question_answered`, `review_decided`, and
  `review_resolved_from_memory`. Each event MUST carry the `loop_id`, the iteration index, and a
  correlation to the run (`session_id`) where applicable.
- **FR-051**: Review Events MUST be emitted in deterministic order, MUST be versioned and evolve
  additively (consumers tolerate unknown future types), and MUST NOT wrap, replace, or re-emit Loop Events
  or Runtime Events.
- **FR-052**: Review observation MUST default **off** and add zero behavior change when disabled: the
  review decision and the Loop outcome MUST be identical whether observation is on or off.

#### Boundary, Non-Duplication & Extension Points

- **FR-060**: The layer MUST NOT implement or duplicate any Phase-1 runtime internal, any Phase-2 host
  internal, or any Phase-3 loop-control internal; it composes the loop only through the Phase-3 public
  `run_loop` / `ReviewResolver` / `ReviewDecision` surface and the public Loop State / Loop Outcome value
  types.
- **FR-061**: The layer MUST NOT re-implement the Phase-1 Human Approval boundary or the in-run *tool*
  approval/question machinery: Phase-6 review is a **loop-level** acceptance concern, distinct from in-run
  tool approval, which remains the Phase-1 boundary surfaced via the host's `on_approval`.
- **FR-062**: The layer MUST name, without implementing, the reserved extension points: durable
  cross-restart resume, multi-level / consensus review (multiple reviewers, escalation chains),
  external/persistent review storage or webhooks, structured audit trails beyond the decision's reason and
  metadata, and a review UI.
- **FR-063**: The layer MUST NOT implement any out-of-scope product or platform layer — a review UI, an
  external review service or database, a webhook/callback system, multi-user tenancy, or any
  non-deterministic review. Any such need discovered during implementation MUST be deferred to a future
  specification.

### Non-Functional Requirements

- **NFR-001 (Phase dependency)**: This phase MUST build strictly on the completed Phase-3 loop layer and
  inherit its guarantees; it consumes only the Phase-3 review hook (`run_loop`, `ReviewResolver`,
  `ReviewDecision`) and the public Loop State / Loop Outcome value types, re-deriving none of them.
- **NFR-002 (Determinism)**: Given a scripted loop and a scripted reviewer (and scripted question answers),
  a gated review MUST produce the same review decision, the same review-event sequence, and the same
  terminal loop outcome on every run.
- **NFR-003 (Boundary integrity)**: It MUST be auditable that the layer starts Loop Runs only through the
  Phase-3 entry point and invokes no Phase-1/2/3 internal directly (operationalized by FR-012, FR-040,
  FR-060, SC-002).
- **NFR-004 (Public-safety)**: All committed Phase-6 artifacts MUST remain public-safe — no secrets,
  credentials, private paths, private project or repository names, or internal network addresses — and
  no raw private-reference excerpts.
- **NFR-005 (Fail-safe)**: Every failure mode — a raising/unrecognized reviewer, a missing or raising
  question asker, an `inspect_paused` on a terminal outcome — MUST map to an explicit, public-safe result
  (a non-approval decision, an empty/clear question result, or an empty review request), never a silent
  approve, a crash, or a hang.
- **NFR-006 (Observability parity)**: Review observation MUST default off and add zero behavior change
  when disabled; enabling it MUST NOT alter review decisions or loop outcomes.
- **NFR-007 (Minimalism & reversibility)**: The layer MUST stay minimal and independently reversible, with
  no speculative product surface, consistent with the constitution's surgical-scope discipline.

### Key Entities

- **Review Request**: The structured, public-safe description of what a reviewer reviews — loop id,
  iteration, run reference, cause, validation result, artifact references, and allowed decision outcomes —
  built from the public Loop State.
- **Review Decision**: The reviewer's output — outcome (approve / reject / request_changes), reason,
  optional reviewer identity, and metadata — mapped down to the Phase-3 `ReviewDecision`.
- **Reviewer**: The host-supplied callable that, given a Review Request and a Review Context, returns a
  Review Decision.
- **Review Context**: What the gate passes to the reviewer — a channel to ask structured review questions
  of the human via a host-supplied asker.
- **Review Memory**: The in-process remember-the-decision store keyed by a review key, configurable for
  which outcomes are remembered.
- **Review Gate**: The Phase-3 `ReviewResolver` this layer builds from a Reviewer (+ memory + question
  channel) — the human gate loop.
- **Review Event**: A review-level lifecycle record on a stream distinct from Loop Events and Runtime
  Events.

These review-layer entities reference Phase-3 entities — `run_loop`, `ReviewResolver`, `ReviewDecision`,
`LoopState`, `LoopOutcome` — without redefining them.

## Human Review Boundaries

Component ownership for this phase (constitution Principle IV). The layer interacts with the loop only by
*supplying* a Phase-3 `ReviewResolver` and reading the public Loop State / Loop Outcome — never through
reach-through internal access.

| Component | Owns | Must not |
|---|---|---|
| Review Request | Building the structured request from the public Loop State | Read a Phase-1/2 internal; carry secrets |
| Review Decision & Reviewer | The decision vocabulary and the host-review contract; the Phase-3 mapping | Hardcode domain review logic; map a non-approval to approval |
| Review Gate | Composing reviewer + memory + questions into a Phase-3 resolver | Start a Loop Run by any path other than `run_loop`; silently approve on a fault |
| Review Memory | Remember-by-key resolution and its source recording | Cross unrelated keys; require durable persistence this phase |
| Review Context / Questions | The review-question channel and its events | Re-implement the Phase-1 in-run question machinery; hang when no asker exists |
| Review Events | The versioned review-level event stream | Wrap, replace, or re-emit Loop Events or Runtime Events |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A platform developer can build a review gate from a reviewer and gate a loop end to end:
  `needs_human_review` → a Review Request → the reviewer's decision → the loop resumes — with a boundary
  audit confirming no Phase-1/2/3 internal was called and the run was started only through the Phase-3
  entry point.
- **SC-002**: 100% of Loop Runs the layer drives in the test suite go through the Phase-3 `run_loop`; no
  test or audit can demonstrate the layer starting a run or reaching a Phase-1/2/3 internal by any other
  path.
- **SC-003**: An approve decision resumes a loop to `loop_completed` and a reject/request_changes decision
  to `loop_failed`, in 100% of suite cases, including the fail-safe path for a raised/unrecognized
  reviewer outcome (never a silent approve).
- **SC-004**: `inspect_paused` returns a Review Request for a paused outcome and nothing for a terminal
  outcome, and a resume with a supplied decision drives the loop to the matching terminal outcome — all
  in process, with no on-disk persistence.
- **SC-005**: With Review Memory, a repeated review under the same key resolves from memory without
  re-invoking the reviewer, only for outcomes configured to be remembered, and never crosses unrelated
  keys — verified across the configured remember modes.
- **SC-006**: A reviewer can ask a review question and receive a scripted answer through the Review
  Context, emitting `review_question_asked` then `review_question_answered`; with no asker configured,
  asking fails safe and never hangs.
- **SC-007**: Every gated review is deterministic — the same scripted loop, reviewer, and answers produce
  the same decision, the same ordered review-event stream, and the same terminal loop outcome on every
  run.
- **SC-008**: With review observation disabled, the review decision and loop outcome are identical to an
  observed run, and no review event is emitted — proving review observation adds zero behavior change.
- **SC-009**: Every failure mode (raising/unrecognized reviewer, missing/raising asker, `inspect_paused`
  on a terminal outcome) maps to an explicit, public-safe result, never a silent approve, a crash, or a
  hang, in 100% of suite cases.
- **SC-010**: Automated public-safety scans of all committed Phase-6 artifacts find zero private
  references, and a review confirms no Phase-1/2/3 internal is re-implemented and no out-of-scope
  capability (UI, external storage, multi-reviewer orchestration, non-deterministic review) is built
  (constitution Principles IV–VI and VIII upheld).

## In Scope *(this phase)*

- A Review Request built from the public Loop State, a Review Decision vocabulary, and a Reviewer contract.
- A review-gate builder composing reviewer + memory + question channel into a Phase-3 `ReviewResolver`.
- The pause / inspect / resume path (in-process).
- Review Memory (remember-by-key, configurable remember modes).
- A Review Context with a review-question channel and a host-supplied asker, with review-question events.
- A versioned, distinct Review Event stream, off by default.
- Public-safe examples and a docs guide.

## Out of Scope *(this phase)*

- A review UI of any kind.
- Durable cross-restart resume from a paused review.
- Multi-level / consensus review (multiple reviewers, escalation chains).
- External or persistent review storage, databases, webhooks, or callback infrastructure.
- Structured audit trails beyond the decision's reason and metadata.
- Re-implementing the Phase-1 Human Approval boundary or the in-run tool approval/question machinery.
- Multi-user tenancy and any non-deterministic review.

## Assumptions

- This phase depends on the completed Phase-3 loop layer
  ([`003-loopplane-loop-engineering-layer`](../003-loopplane-loop-engineering-layer/spec.md)) and consumes
  only its review hook (`run_loop`, `ReviewResolver`, `ReviewDecision`) and the public Loop State / Loop
  Outcome value types.
- Phase-6 review is a **loop-level** acceptance concern (does a human accept this iteration's outcome?),
  distinct from Phase-1 **in-run tool** approval, which remains the Phase-1 Human Approval boundary
  surfaced through the host's `on_approval` and is not re-implemented here.
- Reviewers, question askers, and review-key functions are host-supplied; committed examples use only
  public-safe, scripted values.
- Resume is in-process this phase (the loop is re-driven with the supplied decision); durable cross-restart
  resume is reserved, consistent with Phase-3.
- Determinism is mandatory: a scripted loop, reviewer, and answers yield identical decisions, review
  events, and outcomes on every run; the layer performs no I/O, network, or non-deterministic review.
- Specification and documentation artifacts are written in English, consistent with prior phases, and all
  Phase-6 artifacts contain only public-safe content (constitution Principles II and VII).
