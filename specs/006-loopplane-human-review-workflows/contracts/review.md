# Contract: Review Request, Decision, Reviewer, Context & Memory

**Feature**: `006-loopplane-human-review-workflows` | FR-001–FR-004, FR-030–FR-043

The review vocabulary a host composes. Signatures are design intent for the implementation phase. All
types are public-safe and carry no secrets (FR-004, NFR-004).

## Review Request (FR-001)

```python
ReviewCause = Literal["validator_status", "fail_safe"]

@dataclass(frozen=True)
class ReviewRequest:
    loop_id: str
    loop_definition_id: str
    iteration_index: int
    session_id: str | None
    cause: ReviewCause
    validation_status: str | None
    validation_reason: str | None
    artifact_references: tuple[str, ...]
    options: tuple[ReviewOutcome, ...]

def build_review_request(
    state: LoopState, *, options: tuple[ReviewOutcome, ...] = ("approve", "reject", "request_changes")
) -> ReviewRequest: ...
```

- MUST read only the public `LoopState` (loop_id, loop_definition_id, iteration_index, run_refs,
  latest_validation, artifacts); MUST NOT touch a Phase-1/2 internal (FR-001, FR-040).
- `cause` is `validator_status` when `state.latest_validation` exists, else `fail_safe`.
- `session_id` is the last `run_refs` entry's session id (or `None`). MUST NOT mutate the state (FR-003 of
  the loop layer reused).

## Review Decision & Reviewer (FR-002–FR-004)

```python
ReviewOutcome = Literal["approve", "reject", "request_changes"]

@dataclass(frozen=True)
class ReviewDecision:
    outcome: ReviewOutcome
    reason: str | None = None
    reviewer: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

class Reviewer(Protocol):
    def __call__(
        self, request: ReviewRequest, context: ReviewContext
    ) -> ReviewDecision | Awaitable[ReviewDecision]: ...

def to_phase3_decision(decision: ReviewDecision) -> EngineeringReviewDecision: ...
```

- `to_phase3_decision`: `approve → ReviewDecision(approve=True, reason)`; `reject` / `request_changes` →
  `ReviewDecision(approve=False, reason)`. A non-approval MUST NEVER become `approve=True` (FR-004).
- The Reviewer is host-supplied; the layer hardcodes no domain review logic (FR-003).

## Review Context & Questions (FR-041–FR-043)

```python
@dataclass(frozen=True)
class ReviewQuestion:
    text: str
    options: tuple[str, ...] = ()

QuestionAsker = Callable[[Sequence[ReviewQuestion]], Sequence[str] | Awaitable[Sequence[str]]]

class ReviewContext:
    async def ask(self, questions: Sequence[ReviewQuestion]) -> list[str]: ...

class ReviewError(RuntimeError): ...   # public-safe
```

- `ask` MUST emit `review_question_asked`, delegate to the host `QuestionAsker`, emit
  `review_question_answered`, and return the answers (FR-042).
- With **no** asker, `ask` MUST raise `ReviewError` — never hang (FR-043). An asker that raises MUST be
  surfaced as a diagnostic and `ask` MUST return `[]` (the reviewer proceeds with no answer) (FR-043).

## Review Memory (FR-030–FR-033)

```python
RememberMode = Literal["approvals", "rejections", "both"]
ReviewKey = Callable[[ReviewRequest], str]

def default_review_key(request: ReviewRequest) -> str: ...   # = request.loop_id

class ReviewMemory:
    def __init__(self, *, remember: RememberMode = "both", key: ReviewKey = default_review_key) -> None: ...
    def recall(self, request: ReviewRequest) -> ReviewDecision | None: ...
    def remember_decision(self, request: ReviewRequest, decision: ReviewDecision) -> None: ...
```

- `recall` returns a stored decision for `key(request)`, else `None` (FR-030).
- `remember_decision` stores **only** when the decision's outcome matches `remember` (`approve` counts as
  an approval; `reject` / `request_changes` as rejections) (FR-031).
- Keying never crosses unrelated keys; the default key is the `loop_id` (FR-032). In process only; durable
  persistence reserved (FR-033, FR-062).
