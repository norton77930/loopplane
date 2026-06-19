# Research: Background Task Tools

The Tier-2 boundary question (the concurrency/lifecycle model) is settled by
**[ADR 0002](../../docs/adr/0002-background-task-execution.md)** (maintainer-approved). The
decisions below record the resulting design; no open `NEEDS CLARIFICATION`.

## Decision 1 — Execution model (per ADR 0002 D1/D2)

**Decision**: A background task is a concurrent child run reusing the unit-043 one-shot
`run_loop` child; a per-run `BackgroundTaskSupervisor` owns an `anyio` task group + a
`{task_id → status, result}` registry. `task_create` does `task_group.start_soon(child_run)`
and returns an id immediately (non-blocking); `task_get`/`task_output`/`task_list`/`task_stop`
read/cancel the registry.

**Rationale**: Reuse-first (043 already runs a bounded child via `run_loop`); the supervisor
adds only non-blocking launch + tracking + lifecycle. `anyio` is already a dependency.

**Alternatives considered** (rejected at the plan boundary review): a weaker "deferred task"
that runs synchronously on poll (not truly background); a new execution engine (unjustified —
043's child run suffices).

## Decision 2 — Where the scope lives & how tools reach it (ADR 0002 D3)

**Decision**: The scope owner creates the supervisor and threads it to the tools via an
additive `RunContext.background_tasks` field (the 043 `subagent_depth` pattern):
`RuntimeController.drive(..., background_supervisor=None)` stamps it onto the one `RunContext`
construction site. The **Dispatcher** creates the supervisor from its existing session task
group; the one-shot **`host.run`** wraps a task group around its single `drive` and creates
one. No breaking `drive`/`run`/`stream_turn` signature change (new params are optional).

**Rationale**: A Gateway tool has no concurrency scope today; threading via `RunContext` is
the proven additive channel. Both run paths get a supervisor from a scope they own.

**Alternatives considered**: a process-global supervisor (rejected — breaks per-run isolation
+ lifecycle); changing `stream_turn`/`drive` signatures in a breaking way (rejected — §9.5).

## Decision 3 — Default-off, bounded, contained (ADR 0002 D4/D5)

**Decision**: `RuntimeConfig.max_background_tasks` (default `0`) gates the feature: `0` → no
supervisor, no tools registered, byte-identical. When `> 0`, it caps the per-run task count;
the 043 `subagent_depth`/`max_subagent_depth` recursion cap also applies. Exceeding either cap
denies `task_create` with a normalized error and starts no task. A child that raises /
over-runs / answers empty is recorded as `failed` with a fixed public-safe message, never
raising across the Gateway (mirrors the 043 fail-safe coordinator).

**Rationale**: Mirrors the proven 043 `max_subagent_depth = 0` default-off + fail-safe posture.

## Decision 4 — Lifecycle & events (ADR 0002 D6)

**Decision**: Pending tasks are cancelled when the supervisor's task group scope exits
(run/session end) → no leak. `task_create` returns immediately (the parent turn cycle is
unchanged). Child events are captured (no live sink) and never re-emitted on the parent bus;
no event-schema / `SCHEMA_VERSION` / content-model change.

**Rationale**: Structured concurrency gives clean cancellation at scope exit; reuses the 043
event-capture posture (Constitution VI).

## Decision 5 — Tool surface & status vocabulary

**Decision**: Five Gateway tools — `task_create(instruction, [allowed_tools])`,
`task_get(task_id)`, `task_list()`, `task_stop(task_id)`, `task_output(task_id)`. Status is
one of `running` / `completed` / `failed` / `stopped`. `task_output` returns the child's final
text when `completed`, else the current status (no block). Optional `allowed_tools` restricts
the child like 043.

**Rationale**: Matches the reference harnesses' create/get/list/stop/output surface; reuses
the 043 child-toolset restriction.

**Alternatives considered**: a single multiplexed tool (rejected — less clear); streaming task
events (deferred per ADR 0002).
