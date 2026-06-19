# Research: Agent Scheduling Tools

The Tier-2 boundary question (concurrency / clock / lifecycle) is resolved **additively** — no
new ADR, no contract break (see plan.md "Boundary review"). Decisions below; no open
`NEEDS CLARIFICATION`.

## Decision 1 — Execution model (reuse 048 + ADR 0002)

**Decision**: A scheduled occurrence is a bounded child run, reusing the 043/048 `run_child`.
A per-run `ScheduleSupervisor` owns the schedule registry and starts, per schedule, a **timer
task** in an injected `anyio` task group (the unit-048 supervisor scope; ADR 0002 already
covers in-run concurrent child runs). No new execution engine.

**Rationale**: Reuse-first; ADR 0002's concurrency model already applies; 049 only adds the
time-based trigger + registry.

**Alternatives considered**: a brand-new scheduler runtime (rejected — duplicates 004/048).

## Decision 2 — Timing via an injectable `Sleeper` (do NOT modify unit-004 `Clock`)

**Decision**: 049 adds a small `Sleeper` seam — an async "wait this long" abstraction. The
production sleeper uses `anyio.sleep`; tests inject a **controllable fake** the test advances,
so interval firings are deterministic with **no real sleeping**. Unit 004's `Clock` Protocol
(which is `now()`-based / poll-driven) is **left unchanged** — adding a method to it would break
existing `Clock` implementers (a contract change we explicitly avoid).

**Rationale**: A new optional seam is purely additive and keeps tests deterministic; reusing
004's interval/registry *concepts* (period math, positive-interval validation) without touching
its contract honors "reuse-first" + "no contract break".

**Alternatives considered**: (a) add `sleep` to 004's `Clock` (rejected — breaks implementers);
(b) a poll-driven driver advanced by the host (rejected — needs the host to pump; the agent
wants fire-and-forget); (c) real `anyio.sleep` in tests (rejected — flaky/slow).

## Decision 3 — Threading (the 048 pattern; controller stays tool-agnostic)

**Decision**: A neutral `ScheduleSupervisor` Protocol in `loopplane.context`; the controller /
dispatcher reference it (NOT `loopplane.tools`). The concrete supervisor is produced by an
opaque factory built in `host/assembly` (which may import the tools layer) and threaded as
`RunContext.schedules` via `RuntimeController.drive(..., schedule_supervisor=None)`. The
Dispatcher builds it from its session task group; the one-shot `host.run` wraps a task group.

**Rationale**: This is exactly the unit-048 wiring that passes the boundary audit
(`test_no_execution_path_outside_the_gateway`): the controller/loop never import the tools
layer.

**Alternatives considered**: importing the concrete supervisor into the controller (rejected —
trips the boundary audit, as 048 first did).

## Decision 4 — Default-off, bounded, contained, lifecycle

**Decision**: `RuntimeConfig.max_schedules` (default `0`) gates it: `0` → no supervisor, no
tools, byte-identical. `> 0` caps the per-run schedule count; the 043 `subagent_depth` cap
applies to scheduled child runs. A failing/over-running occurrence is recorded on that
occurrence's status (public-safe), never raised across the Gateway. Active schedules' timers
are cancelled when the supervisor's task-group scope exits (no leak).

**Rationale**: Mirrors the proven 043/048 default-off + fail-safe + lifecycle posture.

## Decision 5 — Tool surface

**Decision**: Four Gateway tools — `schedule_create(instruction, [delay_seconds],
[interval_seconds], [allowed_tools])`, `schedule_get(schedule_id)`, `schedule_list()`,
`schedule_cancel(schedule_id)`. Exactly one of delay/interval per schedule; a non-positive
delay/interval is a normalized error. Status: `active` / `cancelled` / `completed`.

**Rationale**: Matches the reference harnesses' schedule/cron surface; reuses the 043
allowed_tools restriction.

**Alternatives considered**: cron-expression strings (deferred — out of scope, per spec).
