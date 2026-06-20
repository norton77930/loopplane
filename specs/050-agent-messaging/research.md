# Research: Agent-to-Agent Messaging & Swarm Coordination

The Tier-2 boundary question (the cross-agent communication mechanism) is settled by
**[ADR 0003](../../docs/adr/0003-agent-messaging.md)** (maintainer-approved at the 050 plan
boundary review). Decisions below record the resulting design; no open `NEEDS CLARIFICATION`.

## Decision 1 — Swarm = coordinator + member child runs (ADR 0003 D1)

**Decision**: A member is a bounded child run reusing the 043/048 `run_child`; a per-run
`SwarmSupervisor` owns the member registry (`member_id → status + reply`). `swarm_dispatch`
launches a member via the supervisor's task group (the 048 pattern) and returns a member id.

**Rationale**: Reuse-first; ADR 0002's concurrency model + the 043 child run already exist; 050
adds team dispatch + reply collection.

**Alternatives considered**: a new execution engine (rejected — duplicates 043/048).

## Decision 2 — Messages are a SEPARATE registry, NOT events (ADR 0003 D2) — the key decision

**Decision**: The supervisor also owns a message registry — per-member inboxes
(`member_id → list[Message]`). `message_send` appends to a recipient's inbox; `message_inbox`
reads the caller's inbox. Messages are **in-memory, in-run, agent-internal** — **not**
`RuntimeEvent`s. The Event Bus schema + `SCHEMA_VERSION` are **unchanged**.

**Rationale**: The event bus is the host-facing observability contract (VI); agent-to-agent
coordination is a distinct concern. Keeping messages out of the event stream avoids a
`SCHEMA_VERSION` bump and a consumer-facing contract change — the additive, reversible path.

**Alternatives considered**: messages as new event types (rejected at the boundary review — a VI
contract change + `SCHEMA_VERSION` bump; more invasive); a durable message store (deferred).

## Decision 3 — The caller's identity (member-id on the child context)

**Decision**: When the supervisor launches a member, it stamps the member's id into that member's
child `RunContext` (an additive `swarm_member_id: str | None` field). A member's `message_send` /
`message_inbox` resolve "self" from `context.swarm_member_id`; the coordinator (the parent run) is
a reserved id (e.g. `"coordinator"`). Unknown recipient → a normalized error.

**Rationale**: Each member already gets its own child `RunContext` (built by `drive`); an additive
id field is the minimal way for a member's messaging tools to know who they are.

**Alternatives considered**: a process-global "current member" (rejected — breaks per-run/member
isolation + concurrency).

## Decision 4 — Threading (the 048/049 pattern; controller tool-agnostic)

**Decision**: A neutral `SwarmSupervisor` Protocol in `loopplane.context`; the controller /
dispatcher reference it (NOT `loopplane.tools`). The concrete supervisor is produced by an opaque
factory built in `host/assembly` and threaded as `RunContext.swarm` via
`RuntimeController.drive(..., swarm_supervisor=None)`. The Dispatcher builds it from its session
task group; the one-shot `host.run` wraps a task group + calls `cancel_all` after `drive`.

**Rationale**: The proven 048/049 wiring keeps the boundary audit
(`test_no_execution_path_outside_the_gateway`) green.

## Decision 5 — Default-off, bounded, contained, lifecycle (ADR 0003 D4)

**Decision**: `RuntimeConfig.max_swarm_members` + `max_swarm_messages` (default `0`) gate +
cap the feature: `0` → no supervisor, no tools, byte-identical. The 043 `subagent_depth` cap
applies to members. A failing member → a public-safe reply marker (never a raise). Members'
runs are cancelled at the supervisor scope exit (`cancel_all`); no member/message outlives the run.

**Rationale**: Mirrors the proven 043/048/049 default-off + fail-safe + lifecycle posture.

## Decision 6 — Tool surface

**Decision**: Five Gateway tools — `swarm_dispatch(instruction, [allowed_tools])`,
`swarm_get(member_id)`, `swarm_list()`, `message_send(to, content)`, `message_inbox()`. Replies
+ messages are text (metadata-safe; no content-model change).

**Rationale**: Matches the reference harnesses' dispatch + send/read surface; reuses the 043
`allowed_tools` least-privilege restriction.

**Alternatives considered**: a combined send+spawn tool (rejected — less clear); persistent
member loops (deferred).
