# ADR 0003: Agent-to-agent messaging & swarm communication model

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (approved during the spec 050 plan boundary review);
  spec 050 (agent-messaging).
- **Supersedes / superseded by**: none. Third ADR in the repository (after 0001, 0002).
- **Related**: Constitution **III** (Agent Harness Before Loop Automation — a bounded, opt-in
  autonomy primitive the model invokes, not the reserved outer loop-automation layer), **IV**
  (Runtime Boundary Clarity — this introduces a new *in-run cross-agent communication pattern*,
  recorded here), **V** (Tool Gateway ownership — the tools dispatch only through the Gateway),
  **VI** (the Event Bus schema is **unchanged** — see D2), **VII** (public-safe / metadata-safe
  across agents), **X** (testable + reversible: additive, default-off, byte-identical when
  disabled). Builds on **043** (which **explicitly deferred** this; reuses its one-shot child run
  + `subagent_depth` cap), **048/049** (the per-run supervisor + neutral-context-Protocol
  threading pattern; ADR 0002 concurrency model), and **013** (host-driven orchestration
  concepts).

## Context

Gap G7 (vs the reference agent harnesses): a coordinator agent should be able to dispatch work to
a **team of subagents** that can **exchange messages** and report back — a *swarm*. LoopPlane has
host-driven orchestration (013) and **one-shot** model-driven subagents (043), but 043
**explicitly deferred** agent-to-agent messaging: a 043 child runs to completion and returns only
its final text; there is no channel for members to communicate mid-run, nor for a coordinator to
fan work to N members and collect replies.

The **mechanism** for cross-agent communication is the boundary question:

- **The event bus (VI)** is the runtime's versioned, specified, *consumer-facing* observability
  contract. Routing agent-to-agent messages through it would mean new `RuntimeEvent` types + a
  `SCHEMA_VERSION` bump — conflating *agent-internal coordination* with *host-facing events*.
- A 043 child has no addressable identity or inbox; one-shot children cannot exchange messages.

This is a new in-run pattern (cross-agent messaging), which is why it gets an ADR — and why the
plan step **stopped for maintainer approval** before any implementation (mirroring ADR 0002).

## Decision

- **D1 — A swarm is a coordinator + N member child runs.** Members reuse the unit-043/048 bounded
  one-shot child run (the existing public Phase-3 `run_loop`); 050 adds **team dispatch + reply
  collection + a message channel** on top, not a new execution engine. A member's reply is its
  child's final assistant text (as 043 returns), or a contained public-safe failure marker.
- **D2 — Messages are a SEPARATE in-run registry, NOT runtime events.** A per-run `SwarmSupervisor`
  owns a member registry **and** a message registry (per-member inboxes:
  `member_id → list[Message]`). Messages are agent-internal coordination held in memory for the
  run; they are **not** `RuntimeEvent`s. **The Event Bus schema and `SCHEMA_VERSION` are
  unchanged** (VI) — this is the central decision: agent-to-agent messages are a distinct channel
  from the host-facing event stream.
- **D3 — Threading is the 048/049 additive pattern.** A neutral `SwarmSupervisor` Protocol lives
  in `loopplane.context`; the controller/dispatcher reference **only** it (never `loopplane.tools`
  — the boundary audit). The concrete supervisor is produced by an opaque factory built in
  `host/assembly` (which owns the tools-layer import) and threaded as `RunContext.swarm` via
  `RuntimeController.drive(..., swarm_supervisor=None)`. The Dispatcher builds it from its session
  task group; the one-shot `host.run` wraps a task group. No `drive`/`run`/`stream_turn`
  signature is changed in a breaking way (new params optional, default `None`).
- **D4 — Default-off, bounded, contained, lifecycle-bound.** Config gates (e.g.
  `RuntimeConfig.max_swarm_members` / `max_swarm_messages`, default `0`) govern it: `0` → no
  supervisor, no tools, **byte-identical**. Caps bound team size + message count/size; the 043
  `subagent_depth` cap bounds member recursion; exceeding any cap denies the tool call with a
  normalized error and starts/sends nothing. A member that raises/over-runs is **contained**
  (public-safe marker, never raised across the Gateway). Members + message delivery are bound to
  the run/session: pending members are cancelled at the supervisor scope exit (reusing the
  048/049 task-group + `cancel_all`); no member or message outlives its parent run.
- **D5 — Governed + metadata-safe.** All swarm/messaging tools dispatch only through the Gateway
  (V); members get least-privilege toolsets (the 043 `allowed_tools` restriction); message
  payloads carry metadata-safe text only — no secrets/internal paths leak across agents (VII).
- **D6 — No content-model change.** Replies and messages are text (like 043's final text); no new
  `ContentBlock`/event type is introduced.

## Consequences

- **Enables G7**: model-driven team dispatch + reply collection + member-to-member messaging,
  closing the autonomy gap 043 deferred, while staying bounded, contained, governed, and
  default-off.
- **The Event Bus stays intact (VI)**: messages are a separate in-run registry, so no
  `SCHEMA_VERSION` bump and no consumer-facing event change — observability is unchanged.
- **A new, documented in-run communication pattern** (IV): per-run cross-agent inboxes managed by
  a supervisor. Additive and reversible (default-off → revert by removing the supervisor + tools +
  the optional `RunContext`/`drive` params), reusing the 048/049 concurrency + 043 child runs.
- **Deferred (documented follow-ups)**: persistent / cross-session agents that outlive a run,
  distributed / remote swarm execution, a durable message store, and any human-facing messaging
  UI. These remain out of scope unless a future unit + ADR revisits them.
