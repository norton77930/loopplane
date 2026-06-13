# Human Review Workflows

The **human-review layer** (`loopplane.review`) turns the Phase-3 bare review hook
(`run_loop(review_resolver=...)`, the paused `LoopOutcome`, `LoopState.approval_status`) into reusable,
structured, deterministic human-review workflows. A host implements a **Reviewer**;
`build_review_resolver` composes it (plus an optional **Review Memory** and a review-question channel)
into a Phase-3 `ReviewResolver` — the **human gate loop**.

The layer composes only the Phase-3 public surface and reads only the public Loop State. It is **distinct
from** the Phase-1 in-run *tool* approval boundary (which decides whether a tool call runs, surfaced via
the host's `on_approval`) — review here is a **loop-level acceptance** concern: does a human accept an
iteration's outcome? A runnable example is
[`examples/review_quickstart.py`](../examples/review_quickstart.py).

## Gate a loop on a reviewer

```python
from loopplane.engineering import run_loop
from loopplane.review import build_review_resolver, ReviewDecision

def reviewer(request, context) -> ReviewDecision:
    # request: loop id, iteration, run ref, cause, validation reason, artifacts
    return ReviewDecision(outcome="approve", reason="looks good", reviewer="alice")

gate = build_review_resolver(reviewer)
outcome = await run_loop(definition, review_resolver=gate)   # approve -> loop_completed
```

A Review Decision's `outcome` is `approve` / `reject` / `request_changes`. It maps to the Phase-3
decision: `approve` completes the loop; `reject` and `request_changes` fail it. A reviewer that raises or
returns an unrecognized outcome **fails safe** to a non-approval — never a silent approve.

## Pause, inspect, resume

```python
from loopplane.review import inspect_paused, resume_review, ReviewDecision

paused = await run_loop(definition)              # no resolver -> pauses at needs_human_review
request = inspect_paused(paused)                 # the structured Review Request (None if terminal)
# ... present `request` to a human out of band, collect a decision ...
final = await resume_review(definition, ReviewDecision(outcome="approve"))
```

Resume is **in-process** (the loop is re-driven with the supplied decision); durable cross-restart resume
is a reserved extension point.

## Review memory

```python
from loopplane.review import build_review_resolver, ReviewMemory

memory = ReviewMemory(remember="approvals")      # "approvals" | "rejections" | "both"
gate = build_review_resolver(reviewer, memory=memory)
```

A decision is remembered under a **review key** (default: the loop id; supply your own `key=`). A later
review whose key matches resolves from memory without re-invoking the reviewer, emitting
`review_resolved_from_memory`. Only outcomes matching `remember` are stored. This is the loop-level
parallel of Phase-1 session approval memory, kept decoupled.

## Review questions

```python
from loopplane.review import build_review_resolver, ReviewQuestion

async def reviewer(request, context):
    answers = await context.ask([ReviewQuestion(text="Approve this output?", options=("yes", "no"))])
    return ReviewDecision(outcome="approve" if answers[0] == "yes" else "reject")

gate = build_review_resolver(reviewer, asker=my_question_asker)   # host-supplied asker
```

Asking emits `review_question_asked` then `review_question_answered`. With **no** asker configured, `ask`
raises `ReviewError` (never a silent hang); an asker that raises becomes a diagnostic and `ask` returns
an empty answer list.

## Review events

The gate emits a **distinct** Review Event stream (off by default — pass `on_event=`):
`review_requested`, `review_question_asked`, `review_question_answered`, `review_decided`, and
`review_resolved_from_memory`. It never wraps or re-emits Loop Events or Runtime Events, and observation
adds zero behavior change — the decision and loop outcome are identical whether observation is on or off.

## Reserved extension points

Named but **not** built this phase: durable cross-restart resume, multi-level / consensus review
(multiple reviewers, escalation chains), external / persistent review storage or webhooks, structured
audit trails beyond the decision's reason and metadata, and a review UI.

## Boundary

The layer imports only `loopplane.engineering` (`run_loop`, `ReviewResolver`, `ReviewDecision`,
`LoopState`, `LoopOutcome`, `LoopDefinition`) and the stdlib. It never imports or references the Phase-1
Human Approval boundary, the `InteractionBroker`, the host facade, the scheduler, or the `LoopController`
mechanics. See
[`specs/006-loopplane-human-review-workflows/contracts/gate-boundary.md`](../specs/006-loopplane-human-review-workflows/contracts/gate-boundary.md).
