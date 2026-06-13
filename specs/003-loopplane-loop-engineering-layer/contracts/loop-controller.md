# Contract: Loop Controller & Run Lifecycle

**Feature**: `003-loopplane-loop-engineering-layer` | FR-010–FR-016, FR-032, FR-050–FR-056

The Loop Controller owns a **Loop Run**'s lifecycle: it starts each Agent Run through the Phase-2 Host
Interface, applies the Validator and optional Evaluator, decides the next action, records Loop State,
and emits Loop Events — and it never drives a session directly (FR-010, FR-080). Signatures are design
intent for the implementation phase.

## Entry points

```python
async def run_loop(
    definition: LoopDefinition,
    *,
    on_loop_event: LoopEventSink | None = None,   # attached only when observation is on (FR-009)
    on_approval: OnApproval | None = None,         # forwarded to host.run for in-run tool approval
) -> LoopOutcome: ...

@dataclass(frozen=True)
class LoopOutcome:
    loop_id: str
    terminal_event: Literal["loop_completed", "loop_failed"]
    stop_reason: str
    state: LoopState
```

- `run_loop` is the **manual entry point** for `ManualTrigger` and the single point a host driver calls
  to enact an interval/condition trigger (FR-020–FR-022, SC-008).
- `LoopEventSink = Callable[[LoopEvent], Awaitable[None]]` — a stream **distinct** from the Phase-1
  `EventSink` (FR-070). When `observation_policy.emit_loop_events` is off, no sink is attached and
  emission work is skipped while decisions stay identical (NFR-005, SC-009).

## Lifecycle obligations

1. **Bounded iteration loop (FR-013, FR-056)** — Before every iteration, check the hard
   `stop_condition.max_iterations`. The Loop Run MUST always reach exactly one terminal Loop Event;
   no unbounded looping (SC-007).
2. **One Agent Run per iteration (FR-011)** — Start exactly one Agent Run via
   `await host.run(prompt, on_event, on_approval=...)`, passing the iteration input and, on retry/repair
   iterations, the injected context (FR-052). The host is built from `definition.host_profile`.
3. **Outcome capture (FR-012, FR-016)** — Treat the run's `RunOutcome` as the iteration outcome; read
   only `session_id` and `termination_reason` (by reference, FR-061). A non-natural
   `termination_reason` (turn budget exhausted, cancelled, unrecoverable error) maps by default to a
   **failed iteration subject to retry**, never a loop crash (FR-016).
4. **Validate then evaluate (FR-014, FR-042)** — Apply the Validator; if an evaluation policy exists,
   apply the Evaluator (non-gating). Emit `validation_completed`, then `evaluation_completed` when
   evaluation ran.
5. **Select exactly one next action (FR-014, FR-032)** — `stop_success | stop_failure | retry | repair |
   human_review`, per the status→decision mapping below.
6. **Record + emit (FR-015)** — Update Loop State and emit the corresponding Loop Events in
   deterministic per-loop order (NFR-002).
7. **Host-only & host-free (FR-017, FR-080)** — Use no web/desktop/CLI dependency; drivable from a plain
   process. Start/observe/terminate runs **only** through the host (SC-002, NFR-003).

## Status → decision mapping (FR-032, SC-003)

| Validation status | Decision | Loop Events |
|---|---|---|
| `pass` | stop-success **iff** `stop_condition` is satisfied; else continue | `validation_completed` → (`loop_completed`) |
| `fail` | retry while `retries_used < max_retries`; else stop-failure | `validation_completed` → `retry_scheduled` … → `loop_failed` |
| `needs_repair` | repair (next iteration with changed input) | `validation_completed` → `repair_requested` |
| `needs_human_review` | request human review, pause | `validation_completed` → `human_review_requested` |
| raised / unrecognized | **fail-safe**: human review if available, else `loop_failed`; never silent pass | `human_review_requested` / `loop_failed` (+ diagnostic) |

## Retry (FR-050, FR-051, FR-055)

- Re-submit the **same** iteration input — no instruction change.
- Honor `max_retries` **exactly**: a persistently failing iteration starts at most `max_retries + 1`
  Agent Runs and ends with `loop_failed` on exhaustion (SC-004).
- Emit `retry_scheduled` carrying `backoff.delay_seconds(attempt)`; perform **no** in-process sleeping
  (the backoff is a host-enactable contract) (FR-051).
- `max_retries == 0` ⇒ a single `fail` ends the run with `loop_failed` and **no** `retry_scheduled`
  (edge case).

## Repair (FR-052, FR-053, FR-054)

- On `needs_repair`, build the next input via:

  ```python
  def build_repair_input(
      original_input: Prompt,
      prior_run_ref: RunReference,          # session_id + termination_reason
      validation_reason: str | None,
      validation_metadata: Mapping[str, JSONValue],
      reused_artifacts: tuple[ArtifactRef, ...],
  ) -> Prompt: ...
  ```

  The result MUST contain the **repair instruction** and **previous-run context** (at minimum: prior
  input, prior outcome reference, validation reason + metadata) and MUST NOT mutate the
  `LoopDefinition` (FR-052, SC-005).
- Artifact reuse is by **reference** through the host, governed by `artifact_policy.reuse`; absent prior
  artifacts ⇒ proceed with instruction + context alone (FR-053, edge case).
- The **checkpoint reuse-or-reset decision is explicit**; default is **reset / fresh Agent Run**, and
  reuse is opt-in and expressed only by reference to Phase-1 records (FR-054).
- Retry and repair both respect the iteration bound (FR-056).

## Human review (FR-009, US5)

- On `needs_human_review` (or fail-safe), emit `human_review_requested`, set Loop State
  `approval_status = pending`, and start **no** further Agent Run until a decision is supplied
  (US5 scenario 3).
- A paused loop awaiting a decision stays cleanly paused with a terminal-pending status; it never hangs
  the runtime or strands an Agent Run (US5 scenario 4, SC-007). In-run **tool** approval remains the
  Phase-1 boundary surfaced via the host's `on_approval` — not re-implemented here (FR-082).
