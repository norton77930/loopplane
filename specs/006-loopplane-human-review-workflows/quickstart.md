# Quickstart & Validation Guide: Human Review Workflows

**Feature**: `006-loopplane-human-review-workflows` | **Spec**: [spec.md](./spec.md) |
**Plan**: [plan.md](./plan.md)

Runnable scenarios that prove the review layer gates a loop through the **public** Phase-3 surface only,
deterministically and fail-safe. Every scenario uses a scripted loop, a scripted reviewer, and scripted
answers; no I/O, no network.

## Prerequisites

- Phases 1–3 merged (`loopplane.engineering` importable, incl. `run_loop` / `ReviewResolver` /
  `ReviewDecision`).
- Dev install: `pip install -e .[dev]` (pytest + anyio).
- The review tests reuse the Phase-3 scripted-host helpers from `tests/loop_helpers.py`.

## Run the validation suite

```powershell
pytest tests/unit/test_review_core.py `
       tests/integration/test_review_us1.py `
       tests/integration/test_review_us2.py `
       tests/integration/test_review_us3.py `
       tests/integration/test_review_us4.py `
       tests/integration/test_review_us5.py `
       tests/contract/test_review_boundary.py
```

## Minimal example (design intent)

```python
from loopplane.engineering import run_loop
from loopplane.review import build_review_resolver, ReviewDecision

def approve(request, context) -> ReviewDecision:
    return ReviewDecision(outcome="approve", reason="looks good", reviewer="alice")

gate = build_review_resolver(approve)
outcome = await run_loop(definition_that_needs_review, review_resolver=gate)
assert outcome.terminal_event == "loop_completed"
```

## Scenario → requirement map

| # | Scenario | Asserts | Maps to |
|---|---|---|---|
| 1 | Build a review request | `build_review_request(state)` carries loop id, iteration, run ref, cause, validation reason | US1, FR-001 |
| 2 | Gate approves | a needs_human_review loop + approving gate ⇒ loop_completed | US1.1, SC-001/003 |
| 3 | Gate rejects | a rejecting gate ⇒ loop_failed with the reason | US1.2, SC-003 |
| 4 | request_changes is non-approval | maps to approve=False; loop does not silently complete | US1.3, FR-004 |
| 5 | Boundary audit | the gate started the run only through run_loop; read only public state | US1.4, SC-002, NFR-003 |
| 6 | Determinism | a gated review run twice ⇒ identical decision + events + outcome | SC-007, NFR-002 |
| 7 | Pause + inspect | a no-resolver run pauses; inspect_paused returns the Review Request | US2.1, FR-020 |
| 8 | inspect_paused on terminal | returns None — nothing to review | US2.2, FR-020 |
| 9 | Resume approve/reject | resume_review with a decision ⇒ loop_completed / loop_failed | US2.3, SC-004 |
| 10 | Resume in-process | no on-disk persistence; durable resume reserved | US2.4, FR-022 |
| 11 | Memory remembers | same key twice ⇒ reviewer invoked once; second from memory | US3.1, SC-005 |
| 12 | Remember mode | approvals-only ⇒ a rejection re-invokes the reviewer next time | US3.2, FR-031 |
| 13 | Memory source recorded | a memory hit emits review_resolved_from_memory | US3.3, FR-032 |
| 14 | Keys isolated | a memory entry for one key never resolves another | US3.4, FR-032 |
| 15 | Reviewer asks a question | the answer reaches the reviewer; decision reflects it | US4.1, SC-006 |
| 16 | Question events | review_question_asked → review_question_answered in order | US4.2, FR-042 |
| 17 | No asker | ask fails safe (ReviewError), never hangs | US4.3, FR-043, SC-009 |
| 18 | Asker raises | diagnostic + empty answer; review proceeds, no crash | US4.4, FR-043 |
| 19 | Review event order | review_requested → … → review_decided emitted in order | US5.1, FR-050 |
| 20 | Observation parity | observation off vs on ⇒ identical decision + outcome, no events | US5.2, SC-008 |
| 21 | Fail-safe reviewer | a raising/unknown reviewer ⇒ non-approval + diagnostic, never silent approve | Edge, SC-009 |
| 22 | Public-safety scan | committed Phase-6 files contain zero private references | SC-010, NFR-004 |

## Rollback

The `loopplane.review` package is **purely additive** over Phases 1–3. Reverting the feature's commits
removes the package, example, docs, and tests and leaves the Phase-1/2/3 layers untouched (the review
layer owns no runtime/loop state and no storage). Observation defaults off, so a partial revert can never
change loop behavior.
