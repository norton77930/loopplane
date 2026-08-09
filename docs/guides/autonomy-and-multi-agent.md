# Autonomy & multi-agent

**Covered units:** 013, 043, 048, 049, 050, 051.

How LoopPlane runs more than one agent, and how it lets an agent take on work that
outlives a single turn. This guide is navigational:
[`../capabilities.md`](../capabilities.md) and [`../api-reference.md`](../api-reference.md)
are the authorities — where they disagree with this page, they win.

## The one thing to understand first: everything here is capped and off by default

Every capability in this guide is gated by a `RuntimeConfig` cap that defaults to **0**:

| Capability | Cap | Default |
| --- | --- | --- |
| Model-driven subagents (043) | `max_subagent_depth` | `0` — spawning is refused |
| Background tasks (048) | `max_background_tasks` | `0` |
| Agent-facing scheduling (049) | `max_schedules` | `0` |
| Agent messaging / swarm (050) | `max_swarm_members`, `max_swarm_messages` | `0` |
| Worktree isolation (051) | `max_worktrees` | `0` |

A cap of zero is not a soft limit: the supervisor is not created, the tools are not
registered, and a request is denied with **zero** child work performed. Raising a cap is a
deliberate act, which is the point — autonomy is opt-in per deployment.

## Two kinds of multi-agent

LoopPlane distinguishes who decides that a second agent should exist.

### Host-driven orchestration (013)

The **host** composes the agents. `loopplane.orchestration` provides an `AgentRegistry`, a
`Coordinator`, a `DelegationPolicy`, and aggregated views over children
(`aggregate_events`, `aggregate_artifacts`). The host decides the topology up front, runs
the children, and reads their combined event and artifact streams. Children never publish
onto the parent's live event bus — aggregation is a read-side operation, so the single
event-bus owner rule holds.

See [Multi-agent orchestration](../multi-agent-orchestration.md) for the full unit-013
guide.

### Model-driven subagents (043)

The **model** decides, mid-run, that a sub-task deserves its own agent, by calling
`spawn_subagent`. The tool runs exactly one bounded child through the existing loop entry
point and returns the child's final text to the parent. Properties worth knowing:

- **Depth-capped.** `RunContext.subagent_depth` increments per level; at or over
  `max_subagent_depth` the call is denied before any child runs.
- **Failure-contained.** A child failure becomes a public-safe error output for the
  parent; the parent run continues.
- **Observable.** Child events are captured and can be aggregated with the 013 helpers —
  never re-emitted onto the parent's bus.

The two models compose: a host-orchestrated agent may itself spawn subagents, subject to
the same cap.

## Work that outlives a turn

### Background tasks (048)

Long-running work is handed to a per-run supervisor and tracked by handle: the agent
starts a task, keeps working, and collects the result later. ADR 0002 records the boundary
decision. The controller never imports the tools package — the supervisor is reached
through a neutral Protocol in `loopplane.context` and constructed by an opaque factory in
the host assembly. That indirection is deliberate; see the hazard map in
[`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

### Agent-facing scheduling (049)

The agent can schedule its own future work, on top of the same in-process scheduler that
unit 004 exposes to hosts. Host-driven scheduling and agent-driven scheduling share the
trigger engine; the difference is who creates the schedule and which cap governs it. See
[Scheduling](../scheduling.md) for the host-side view.

### Agent-to-agent messaging and swarm (050)

Agents can address one another through a separate registry with its own mailbox
semantics (ADR 0003). Messages are bounded twice over — by member count and by message
count — so a swarm cannot amplify without a configured ceiling.

### Worktree isolation (051)

Per-task isolation via `WorktreeManager`: a task gets its own checkout to work in, so
parallel agents do not fight over one working tree. Isolation is filesystem-level, in
process; container-level isolation is not in scope
([`../capabilities.md`](../capabilities.md#scope-boundaries-out-of-scope--deferred)).

## Operating notes

- **Start at one level.** `max_subagent_depth = 1` is the useful first step: the top agent
  may delegate, delegates may not.
- **Cap before you enable.** Set the cap for the capability you want and leave the others
  at zero; each is independent.
- **Watch the cost.** Children consume tokens against the same budget machinery — see
  [Cost governance](cost-governance.md), particularly the per-session and per-user monthly
  caps.
- **Execution is in-process.** Children run in the same process as the parent; distributed
  or remote execution is on the roadmap, not in the product
  ([`../gap-analysis.md`](../gap-analysis.md)).

## Where to go next

- [Multi-agent orchestration](../multi-agent-orchestration.md) — the host-driven API
  (unit 013).
- [Scheduling](../scheduling.md) — the trigger engine (unit 004).
- [Loop engineering](../loop-engineering.md) — `run_loop`, the single Phase-3 entry point.
- [Agent tools & permissions](agent-tools-and-permissions.md) — what a child agent is
  allowed to do.
- [`../api-reference.md`](../api-reference.md) — the exact public names and signatures.
