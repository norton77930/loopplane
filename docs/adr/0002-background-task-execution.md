# ADR 0002: Background task execution model

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (approved during the spec 048 plan boundary
  review); spec 048 (background-tasks).
- **Supersedes / superseded by**: none. Second ADR in the repository (after 0001).
- **Related**: Constitution **III** (Agent Harness Before Loop Automation — background
  tasks are a *bounded, opt-in autonomy primitive* the model invokes, not the reserved
  outer loop-automation layer), **IV** (Runtime Boundary Clarity — this introduces a new
  *concurrency pattern* inside a run, so it is recorded here), **V** (Tool Gateway
  ownership — the tools dispatch only through the Gateway), **VI** (the Event Bus schema is
  unchanged), **X** (testable + reversible: additive, default-off, byte-identical when
  disabled). Builds on **043** (reuses the one-shot child-run via `run_loop` and the
  `subagent_depth` recursion cap).

## Context

Gap G5 (vs the reference agent harnesses): an agent should be able to launch
**background / long-running work that outlives a single turn** (create / get / list /
stop / output), not only the **synchronous, blocking** one-shot subagent from unit 043
(which runs one child to completion and returns its text before the tool returns).

A pre-implementation read of the run lifecycle established:

- `Dispatcher.run()` already owns a **session-level `anyio.create_task_group()`** (it
  drives turns via `task_group.start_soon`, one turn at a time via a `_driving` guard, and
  cancels in-flight work when the inbound channel closes). This is a concurrency scope that
  spans the interactive / web-API session.
- The **one-shot `host.run()`** path does **not** use the Dispatcher — it `await`s
  `controller.drive(...)` directly (blocking), with no task group.
- A Tool Gateway tool runs deep inside `drive → loop → gateway` and today has **no handle**
  to any concurrency scope, so it cannot launch work that outlives its own call.

True non-blocking background tasks therefore need (a) a concurrency scope that outlives a
turn and is bound to the run/session, and (b) a way to expose "spawn into that scope +
track it" to the tools. This is a **new runtime execution pattern**, which is why it gets
an ADR rather than being introduced silently.

## Decision

- **D1 — A background task is a concurrent child run.** It reuses the unit-043 one-shot
  child machinery (a bounded agent run via the existing public Phase-3 `run_loop`); 048
  adds **non-blocking launch + a registry + lifecycle binding** on top, not a new execution
  engine. The task's "output" is the child's final assistant text, exactly as
  `spawn_subagent` returns.
- **D2 — A per-run `BackgroundTaskSupervisor` owns the scope + registry.** It holds an
  `anyio` task group (the concurrency scope) and a registry of
  `task_id → {status, result}`; `create` does `task_group.start_soon(child_run)` and
  returns an id immediately; `get`/`output`/`list`/`stop` read/cancel the registry.
- **D3 — The scope is created by the scope owner and threaded to tools additively.** The
  **Dispatcher** (interactive / web-API) creates the supervisor from its existing session
  task group; the **one-shot `host.run`** wraps its single `drive` in a task group and
  creates a supervisor for it. The supervisor is handed to the create/get/list/stop/output
  tools through an **additive `RunContext.background_tasks` field** (the same threading
  pattern as 043's `subagent_depth`: `RuntimeController.drive(..., background_supervisor=…)`
  → the one `RunContext` construction site). No `drive`/`run`/`stream_turn` signature is
  changed in a breaking way (the new params are optional, default `None`).
- **D4 — Default-off, byte-identical.** A config gate `RuntimeConfig.max_background_tasks`
  (default `0`) governs it: `0` → no supervisor is created and **no** background-task tools
  are registered, so existing runs are byte-identical (mirroring `max_subagent_depth = 0`).
- **D5 — Bounded + contained.** The per-run task-count cap (`max_background_tasks`) plus the
  **043 recursion-depth cap** (`subagent_depth`/`max_subagent_depth`) bound breadth and
  depth; exceeding either denies `create` with a normalized error and starts no task. A
  task whose child run raises / over-runs / answers empty is **contained** — recorded as
  `failed` with a fixed public-safe message — and never raises across the Gateway or
  crashes the parent (mirroring the 043 fail-safe coordinator).
- **D6 — Lifecycle bound to the run/session; events unchanged.** Pending tasks are
  cancelled when the supervisor's task group scope exits (run/session end), so no task
  leaks. The parent's turn cycle is preserved (`create` returns immediately). The child's
  events are captured (no live sink) and never re-emitted on the parent's bus (VI), reusing
  the 043 capture posture; there is **no event-schema / `SCHEMA_VERSION` / content-model
  change**.

## Consequences

- **Enables G5**: the agent can launch and manage non-blocking background work, closing a
  real autonomy gap vs the reference harnesses, while staying bounded, contained, and
  governed at the Gateway.
- **A new, documented concurrency pattern**: tool-spawned background child runs within a
  per-run supervisor. Recorded here (IV); additive and reversible (default-off → revert by
  removing the supervisor + tools + the optional `RunContext`/`drive` params).
- **Both run paths supported**: the Dispatcher (interactive / web-API) and the one-shot
  `host.run` each create a supervisor from a scope they own; the default-off gate keeps both
  byte-identical when disabled.
- **Deferred (documented follow-ups)**: streaming a task's live events to the agent;
  cross-session / persistent / named background tasks; distributed execution. These remain
  out of scope, consistent with the spec.
