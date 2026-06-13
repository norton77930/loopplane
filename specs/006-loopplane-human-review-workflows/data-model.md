# Phase 1 Data Model: Human Review Workflows

**Feature**: `006-loopplane-human-review-workflows` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

This model defines the **review-layer** entities only. It references — and never redefines — the Phase-3
entities (`run_loop`, `ReviewResolver`, `ReviewDecision`, `LoopState`, `LoopOutcome`, `LoopDefinition`).
All types are illustrative design intent for the implementation phase, and all are public-safe
(FR-001/NFR-004).

## Entity overview

```text
build_review_request(LoopState) ─► ReviewRequest ──► Reviewer(request, ReviewContext) ─► ReviewDecision
                                                          │ may ask                          │ maps down
                                                          ▼                                  ▼
ReviewContext.ask(questions) ─► QuestionAsker                 to_phase3(decision) ─► ReviewDecision (Phase-3)

build_review_resolver(reviewer, *, memory?, asker?, on_event?) ─► Phase-3 ReviewResolver  (the gate)
inspect_paused(LoopOutcome) ─► ReviewRequest | None            resume_review(def, decision) ─► LoopOutcome
ReviewMemory (remember by key)                                Review Event[] (distinct stream, off by default)
```

---

## 1. ReviewRequest  (FR-001)

The structured, public-safe description a reviewer sees, built from the public Loop State.

| Field | Type | Notes |
|---|---|---|
| `loop_id` | `str` | from Loop State (FR-001). |
| `loop_definition_id` | `str` | from Loop State. |
| `iteration_index` | `int` | the iteration under review. |
| `session_id` | `str \| None` | the run reference (last `run_refs` entry), `None` if no run yet. |
| `cause` | `ReviewCause` | `validator_status` (a validation result exists) or `fail_safe`. |
| `validation_status` | `str \| None` | the latest validation status (e.g. `needs_human_review`). |
| `validation_reason` | `str \| None` | the latest validation reason. |
| `artifact_references` | `tuple[str, ...]` | artifact references from Loop State (by reference). |
| `options` | `tuple[ReviewOutcome, ...]` | the allowed decision outcomes (default: all three). |

`ReviewCause = Literal["validator_status", "fail_safe"]`. `build_review_request(state, *, options=...)`
reads only the public Loop State (FR-040); never mutates it.

---

## 2. ReviewDecision & Reviewer  (FR-002–FR-004)

```python
ReviewOutcome = Literal["approve", "reject", "request_changes"]

@dataclass(frozen=True)
class ReviewDecision:
    outcome: ReviewOutcome
    reason: str | None = None
    reviewer: str | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

class Reviewer(Protocol):
    def __call__(
        self, request: ReviewRequest, context: ReviewContext
    ) -> ReviewDecision | Awaitable[ReviewDecision]: ...
```

**Phase-3 mapping (FR-004)** — `to_phase3_decision(decision) -> engineering.ReviewDecision`:

| Phase-6 `outcome` | Phase-3 `ReviewDecision` |
|---|---|
| `approve` | `ReviewDecision(approve=True, reason=decision.reason)` |
| `reject` | `ReviewDecision(approve=False, reason=decision.reason)` |
| `request_changes` | `ReviewDecision(approve=False, reason=decision.reason or "changes requested")` |

A non-approval outcome MUST NEVER map to `approve=True` (FR-004).

---

## 3. ReviewContext & Questions  (FR-041–FR-043)

```python
@dataclass(frozen=True)
class ReviewQuestion:
    text: str
    options: tuple[str, ...] = ()

QuestionAsker = Callable[[Sequence[ReviewQuestion]], Sequence[str] | Awaitable[Sequence[str]]]

class ReviewContext:
    async def ask(self, questions: Sequence[ReviewQuestion]) -> list[str]: ...
```

- `ReviewContext.ask` emits `review_question_asked`, delegates to the host `QuestionAsker`, emits
  `review_question_answered`, and returns the answers (FR-042).
- With **no** asker configured, `ask` raises `ReviewError` (fail-safe; the reviewer handles it) — never a
  silent hang (FR-043). A raising asker becomes a diagnostic and `ask` returns `[]` (empty answers).
- `ReviewError` is a public-safe `RuntimeError` subclass.

---

## 4. ReviewMemory  (FR-030–FR-033)

```python
RememberMode = Literal["approvals", "rejections", "both"]
ReviewKey = Callable[[ReviewRequest], str]

def default_review_key(request: ReviewRequest) -> str:   # = request.loop_id
    ...

class ReviewMemory:
    def __init__(self, *, remember: RememberMode = "both", key: ReviewKey = default_review_key) -> None: ...
    def recall(self, request: ReviewRequest) -> ReviewDecision | None: ...
    def remember_decision(self, request: ReviewRequest, decision: ReviewDecision) -> None: ...
```

| Field/op | Behavior |
|---|---|
| `recall(request)` | returns a remembered decision for `key(request)`, else `None` (FR-030). |
| `remember_decision` | stores the decision under `key(request)` **only if** its outcome matches `remember` (FR-031). |
| keying | `default_review_key` = `loop_id`; never crosses unrelated keys (FR-032). |
| persistence | in process only; durable persistence reserved (FR-033, FR-062). |

`approve` counts as an approval; `reject` and `request_changes` count as rejections for `RememberMode`.

---

## 5. Review Events  (FR-050–FR-052)

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
    payload: Mapping[str, JSONValue] = field(default_factory=dict)
    schema_version: str = REVIEW_SCHEMA_VERSION

ReviewEventSink = Callable[[ReviewEvent], Awaitable[None]]
```

- Distinct from Loop Events and Runtime Events (FR-050); deterministic order; never wraps/re-emits them
  (FR-051).
- Emission is gated by the presence of an `on_event` sink; absent ⇒ no emission, identical decisions
  (FR-052, SC-008).

Representative payloads: `review_requested` (cause, validation_status); `review_decided`
(outcome, reason, reviewer); `review_resolved_from_memory` (outcome, key); `review_question_asked`
(count); `review_question_answered` (count).

---

## 6. The Gate & pause/inspect/resume  (FR-010–FR-022)

```python
def build_review_resolver(
    reviewer: Reviewer,
    *,
    memory: ReviewMemory | None = None,
    asker: QuestionAsker | None = None,
    on_event: ReviewEventSink | None = None,
    options: tuple[ReviewOutcome, ...] = ("approve", "reject", "request_changes"),
) -> ReviewResolver: ...                                   # a Phase-3 resolver

def inspect_paused(outcome: LoopOutcome) -> ReviewRequest | None: ...

async def resume_review(
    definition: LoopDefinition,
    decision: ReviewDecision,
    *,
    on_event: ... = None,
) -> LoopOutcome: ...
```

**Gate flow (FR-011)** — the async resolver `(LoopState) -> engineering.ReviewDecision`:

```text
 resolver(state):
   request = build_review_request(state, options=options)
   emit review_requested
   if memory and (remembered = memory.recall(request)):
       emit review_resolved_from_memory ; decision = remembered
   else:
       context = ReviewContext(asker, on_event, request)         # ask -> question events
       decision = await reviewer(request, context)               # sync or async
       if invalid/raised: decision = ReviewDecision("reject", reason="fail-safe: ...")   # FR-013
       if memory: memory.remember_decision(request, decision)
   emit review_decided
   return to_phase3_decision(decision)
```

`inspect_paused`: `build_review_request(outcome.state)` when `outcome.paused`, else `None` (FR-020).
`resume_review`: `run_loop(definition, review_resolver=lambda _state: to_phase3_decision(decision), ...)`
— in-process re-drive; durable resume reserved (FR-021, FR-022).

## Referenced Phase-3 entities (not redefined)

| Entity | Source | Referenced as |
|---|---|---|
| `run_loop` | `loopplane.engineering` | the only path to drive a (gated/resumed) Loop Run |
| `ReviewResolver` | `loopplane.engineering` | the contract the gate builder produces |
| `ReviewDecision` (Phase-3) | `loopplane.engineering` | the mapped-down decision the gate returns |
| `LoopState` | `loopplane.engineering` | the public state a Review Request is built from |
| `LoopOutcome` | `loopplane.engineering` | the paused/terminal result `inspect_paused` reads |
| `LoopDefinition` | `loopplane.engineering` | passed through to `run_loop` |
