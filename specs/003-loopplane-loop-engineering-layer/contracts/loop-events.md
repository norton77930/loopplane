# Contract: Loop Events & Loop State

**Feature**: `003-loopplane-loop-engineering-layer` | FR-060–FR-064, FR-070–FR-075

The loop-level event stream and the in-process state it reconstructs. The stream is **distinct** from the
Phase-1 Runtime Event Bus (FR-070) and mirrors its discipline (Constitution VI). Signatures are design
intent for the implementation phase.

## Loop Event vocabulary (FR-070–FR-075)

```python
LOOP_SCHEMA_VERSION = "1.0"            # versioned; evolves additively (FR-075)

LoopEventType = Literal[
    "loop_started", "loop_iteration_started", "loop_iteration_completed",
    "validation_completed", "evaluation_completed", "repair_requested",
    "retry_scheduled", "human_review_requested", "loop_completed", "loop_failed",
]

@dataclass(frozen=True)
class LoopEvent:
    type: LoopEventType
    schema_version: str
    sequence: int                       # monotonic per Loop Run (FR-073)
    loop_id: str
    loop_definition_id: str
    iteration_index: int | None = None
    session_id: str | None = None       # correlation to the Agent Run when one exists (FR-072)
    payload: Mapping[str, JSONValue] = field(default_factory=dict)

LoopEventSink = Callable[[LoopEvent], Awaitable[None]]
```

**Contract requirements**

- MUST emit, at the appropriate points, all ten event types (FR-071). `evaluation_completed` is emitted
  **only** when an evaluation policy exists (FR-042).
- Every event MUST carry `loop_id`, `loop_definition_id`, the applicable `iteration_index`, and the
  correlating `session_id` when a run exists (FR-072).
- Events MUST be emitted in **deterministic per-loop order**; the ordered stream MUST be sufficient to
  reconstruct the loop's decisions and Loop State (FR-073, SC-006, NFR-002).
- Every Loop Run MUST end with **exactly one** terminal event — `loop_completed` or `loop_failed`
  (FR-074).
- The vocabulary MUST be versioned and evolve additively; consumers MUST tolerate unknown future types
  (FR-075). MUST NOT wrap, replace, or re-emit Runtime Events (FR-070).

### Representative payloads

| Type | Payload keys |
|---|---|
| `loop_iteration_started` | `kind` (`initial`/`retry`/`repair`) |
| `loop_iteration_completed` | `termination_reason` |
| `validation_completed` | `status`, `reason?` |
| `evaluation_completed` | `score?`, `label?` |
| `retry_scheduled` | `attempt`, `delay_seconds` |
| `repair_requested` | `reason?` |
| `human_review_requested` | `cause` (`validator_status`/`fail_safe`) |
| `loop_completed` / `loop_failed` | `stop_reason` |

## Loop State (FR-060–FR-064)

`LoopState` shape and invariants are defined in [data-model.md](../data-model.md#6-loopstate-fr-060--fr-064).
Contract obligations restated:

- MUST carry `loop_id`, `loop_definition_id`, `iteration_index`, `run_refs` (session_ids + reasons),
  `latest_validation`, `latest_evaluation`, `artifacts` (references), `approval_status`, and `stop_reason`
  (FR-060).
- MUST reference Phase-1/2 state **only by id/reference** — no copied Run State, conversation history, or
  artifact bytes (FR-061, FR-063).
- MUST be held in process and reconstructable from the ordered Loop Event stream + referenced run
  outcomes (FR-062).

### Reconstruction (FR-062, FR-073, SC-006)

```python
def reconstruct_state(
    events: Sequence[LoopEvent],
    outcomes: Mapping[str, RunOutcome],   # session_id -> RunOutcome (referenced runs)
) -> LoopState: ...
```

- MUST rebuild an equivalent `LoopState` from the event stream alone (plus referenced outcomes),
  proving event-sufficiency (SC-006).
- Durable persistence and **loop resume** are **reserved extension points**, named but not implemented
  (FR-064, FR-091).
