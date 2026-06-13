# Contract: Review Gate, Pause/Resume, Events & Boundary

**Feature**: `006-loopplane-human-review-workflows` | FR-010–FR-022, FR-050–FR-063

## Review Gate (the human gate loop) (FR-010–FR-013)

```python
def build_review_resolver(
    reviewer: Reviewer,
    *,
    memory: ReviewMemory | None = None,
    asker: QuestionAsker | None = None,
    on_event: ReviewEventSink | None = None,
    options: tuple[ReviewOutcome, ...] = ("approve", "reject", "request_changes"),
) -> ReviewResolver: ...
```

- Returns an **async** Phase-3 `ReviewResolver` `(LoopState) -> EngineeringReviewDecision` to pass to
  `run_loop(review_resolver=...)` (FR-010).
- Per invocation it MUST: build a Review Request; emit `review_requested`; consult `memory` (a hit emits
  `review_resolved_from_memory` and uses the remembered decision); else invoke the reviewer with a Review
  Context, then `memory.remember_decision(...)` if configured; emit `review_decided`; and return
  `to_phase3_decision(decision)` (FR-011).
- It MUST start, drive, or observe **no** Loop Run by any path other than `run_loop` — it only supplies
  the resolver (FR-012).
- **Fail-safe (FR-013)**: a reviewer that raises or returns an unrecognized outcome MUST map to a
  non-approval decision (`ReviewDecision("reject", reason="fail-safe: ...")`) with a diagnostic — never a
  silent approve.

## Pause / Inspect / Resume (FR-020–FR-022)

```python
def inspect_paused(outcome: LoopOutcome) -> ReviewRequest | None: ...

async def resume_review(
    definition: LoopDefinition,
    decision: ReviewDecision,
    *,
    on_event: ReviewEventSink | None = None,
) -> LoopOutcome: ...
```

- `inspect_paused` returns a Review Request when `outcome.paused`, else `None` (FR-020).
- `resume_review` drives the Loop Run through `run_loop(definition, review_resolver=<one-shot mapped
  decision>)` and returns the terminal outcome (FR-021). Resume is **in-process** only; durable
  cross-restart resume is reserved (FR-022, FR-062). Resume exposes no tool-approval handler: Phase-1
  in-run tool approval stays the host's concern (surfaced through the host's `on_approval`, not
  re-implemented here), and the `OnApproval` type is not on the Phase-3 public surface this layer may
  name (NFR-003).

## Review Events (FR-050–FR-052)

```python
REVIEW_SCHEMA_VERSION = "1.0"
ReviewEventType = Literal[
    "review_requested", "review_question_asked", "review_question_answered",
    "review_decided", "review_resolved_from_memory",
]

@dataclass(frozen=True)
class ReviewEvent:
    type: ReviewEventType
    sequence: int
    loop_id: str
    iteration_index: int | None = None
    session_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = REVIEW_SCHEMA_VERSION

ReviewEventSink = Callable[[ReviewEvent], Awaitable[None]]
```

- A **distinct** stream — never wraps, replaces, or re-emits Loop Events or Runtime Events (FR-050).
- Deterministic order; versioned + additive; consumers tolerate unknown future types (FR-051).
- Emission is gated by the presence of an `on_event` sink; absent ⇒ no emission and identical decisions /
  loop outcomes (FR-052, NFR-006, SC-008).

## Boundary (FR-040, FR-060–FR-063, NFR-003)

The layer composes only the Phase-3 public surface:

```python
from loopplane.engineering import (
    run_loop, ReviewDecision, ReviewResolver, LoopDefinition, LoopOutcome, LoopState,
)
```

The layer MUST NOT:

- import or call any Phase-1 runtime internal — **including** the Human Approval boundary
  (`loopplane.approval.*`), the `InteractionBroker`, and the in-run question machinery — any Phase-2 host
  internal, or any Phase-3 loop-control internal (`loopplane.engineering.controller`'s `LoopController`
  mechanics) (FR-060, FR-061);
- start, drive, or observe a Loop Run by any path other than `run_loop` (FR-012);
- re-implement the Phase-1 in-run *tool* approval/question machinery — Phase-6 review is a loop-level
  acceptance concern (FR-061);
- implement any out-of-scope capability — a review UI, an external/persistent review store, a
  webhook/callback system, multi-reviewer/consensus orchestration, durable resume, or non-deterministic
  review (FR-062, FR-063).

> Permitted: stdlib and the Phase-3 public symbols above (which include `ReviewDecision` /
> `ReviewResolver`). Reading the public `LoopState` / `LoopOutcome` value types is the intended
> composition path; reaching into lower-layer modules is the prohibited reach-through.

## Reserved extension points (named, not built) — FR-062

- Durable cross-restart resume from a paused review.
- Multi-level / consensus review (multiple reviewers, escalation chains).
- External / persistent review storage, databases, webhooks, or callback infrastructure.
- Structured audit trails beyond the decision's reason and metadata.
- A review UI.

## Auditability (NFR-003, SC-002, SC-010)

- An import-boundary test MUST assert `loopplane.review` imports only `loopplane.engineering` (+ stdlib)
  and references no `loopplane.approval` / `InteractionBroker` / `LoopController` symbol.
- 100% of Loop Runs the layer drives in the suite go through `run_loop` (SC-002).
- A public-safety scan over committed Phase-6 files MUST find zero private references (SC-010, NFR-004).
