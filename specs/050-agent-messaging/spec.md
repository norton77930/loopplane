# Feature Specification: Agent-to-Agent Messaging & Swarm Coordination

**Feature Branch**: `050-agent-messaging`

**Created**: 2026-06-20

**Status**: Draft — **plan blocked on a maintainer boundary review** (see FR-010 / Assumptions)

**Input**: User description: "Agent-to-agent messaging and swarm coordination: let a coordinator agent dispatch work to a team of subagents that can exchange messages and report back, bounded and governed. Unit 050, Tier-2 (autonomy & workflow); closes gap G7. This is the swarm/messaging capability EXPLICITLY DEFERRED by unit 043; the cross-agent communication mechanism is a boundary decision requiring maintainer approval (likely a new ADR)."

## ⚠️ Boundary note (read first)

Unit 043 (model-driven one-shot subagents) **explicitly deferred** agent-to-agent messaging /
swarm. The *capability* is specified below; the **mechanism** (how agents exchange messages —
a new in-run message broker vs. the event bus vs. persistent communicating subagents) is a
**boundary-crossing decision**. Per the autopilot guardrail (board §9), the **plan step must
STOP and obtain maintainer approval** (a new ADR is likely) before the mechanism is designed or
implemented. This spec deliberately fixes only the capability + the safety envelope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coordinator dispatches a team and collects replies (Priority: P1)

A coordinator agent dispatches a focused sub-task to each of several subagents (a "team" /
swarm), the subagents work concurrently, and the coordinator collects their replies — so a
larger task is decomposed across agents and recombined, beyond a single one-shot subagent (043).

**Why this priority**: This is gap G7 and the unit's core value — the reference harnesses let a
coordinator fan work out to a team and gather results; LoopPlane has host-driven orchestration
(013) and one-shot subagents (043) but no model-driven team dispatch + reply collection.

**Independent Test**: With the feature enabled (offline, scripted child models), a coordinator
dispatches N sub-tasks; all N run as bounded child runs; the coordinator receives all N replies
(or a contained failure marker per failed member), within the caps.

**Acceptance Scenarios**:

1. **Given** the feature is enabled, **When** the coordinator dispatches a team of sub-tasks,
   **Then** each runs as a bounded child run and the coordinator collects each member's reply.
2. **Given** a team member's run fails, **When** the coordinator collects replies, **Then** that
   member's reply is a contained, public-safe failure marker (the others still return).

---

### User Story 2 - Agents exchange messages (Priority: P2)

Within a coordinated group, an agent can send a message addressed to another member (or the
coordinator) and the recipient can read messages addressed to it — so members share intermediate
findings, not just a single final reply.

**Why this priority**: Messaging (not just dispatch+reply) is what distinguishes a swarm from
parallel one-shots; it is the harder half of G7 and the part 043 deferred.

**Independent Test**: Member A sends a message to member B; B reads its inbox and sees A's
message; messages are bounded (count/size) and governed.

**Acceptance Scenarios**:

1. **Given** a group with members A and B, **When** A sends a message to B, **Then** B can read
   that message from its inbox (metadata-safe; bounded).
2. **Given** the message cap is reached, **When** an agent sends another, **Then** it is denied
   with a normalized error (no unbounded message growth).

---

### User Story 3 - Bounded, contained, governed, lifecycle-bound (Priority: P3)

Messaging + swarm are bounded (team size + message count/size caps + the 043 recursion-depth
cap), contained (a member failure never crashes the coordinator or the parent), governed
(Gateway tools; least-privilege member toolsets), default-off (byte-identical when disabled),
and lifecycle-bound (no message delivery or member run outlives its parent run/session; pending
members cancelled at scope exit).

**Why this priority**: A communication channel between agents is the highest-risk autonomy
feature — unbounded fan-out, message floods, leaks across agents, or a member taking down the
parent are unacceptable. The safety envelope is non-negotiable (the 043/048 posture).

**Independent Test**: Team size + message caps deny excess; a failing member is contained; with
the feature disabled no messaging/swarm tools are offered; ending the parent run cancels pending
members and stops delivery.

**Acceptance Scenarios**:

1. **Given** the team-size or message cap is reached, **When** the agent dispatches/sends more,
   **Then** it is denied with a normalized error and nothing is started/sent.
2. **Given** the parent run ends with members active, **When** the scope exits, **Then** members
   are cancelled and no further messages are delivered (no leak); the parent is unaffected.

---

### Edge Cases

- **message to an unknown recipient / read an unknown group**: a clear normalized error.
- **feature disabled / caps 0**: no messaging/swarm tools registered (byte-identical).
- **a member whose run raises**: contained — a public-safe failure marker; group + parent continue.
- **depth cap**: a member cannot itself spawn a swarm without bound (the 043 cap applies).
- **message size/count over cap**: denied; no partial/oversized delivery.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide agent-facing tools, reachable only through the Tool Gateway
  (V), for a coordinator to **dispatch** a team of bounded sub-tasks (child runs) and **collect**
  their replies.
- **FR-002**: The system MUST let a member **send** a message addressed to another member (or the
  coordinator) and **read** messages addressed to it, within a coordinated group.
- **FR-003**: Replies + messages MUST be **bounded** — configurable caps on team size, message
  count, and message size; the existing 043 recursion-depth cap MUST apply to member runs;
  exceeding any cap MUST be denied with a normalized error (nothing started/sent).
- **FR-004**: A member failure/over-run MUST be **contained** — surfaced as a public-safe failure
  marker on that member's reply; it MUST NOT crash the coordinator or the parent run, nor raise
  across the Gateway.
- **FR-005**: Messaging + swarm MUST be **governed** — least-privilege member toolsets
  (reuse the 043 `allowed_tools` restriction); messages carry metadata-safe content only (no
  secrets/internal paths leaked across agents, VII).
- **FR-006**: The feature MUST be **lifecycle-bound** — no member run or message delivery
  outlives its parent run/session; pending members are cancelled at scope exit; the parent's
  turn cycle is preserved.
- **FR-007**: The feature MUST be **opt-in and default-off** (byte-identical when disabled), with
  no messaging/swarm tools registered when off.
- **FR-008**: Unknown recipient/group ids MUST yield clear normalized errors (no crash).
- **FR-009**: The capability MUST reuse existing seams where possible — the 043/048 bounded
  child-run, the unit-013 orchestration concepts, and the per-run-supervisor + neutral-Protocol
  threading pattern (048/049) so the controller/loop never import the tools layer.
- **FR-010** (**boundary, blocking**): The **cross-agent communication mechanism** (a new in-run
  message broker vs. the event bus vs. persistent communicating subagents) MUST be settled by a
  **maintainer boundary review at the plan step** before any implementation. A new
  boundary-crossing ADR and/or any change to the event-bus (VI) or orchestration (IV) contract
  MUST be **maintainer-approved** — the autopilot MUST STOP and ask, not introduce it silently
  (this capability was explicitly deferred by unit 043).

### Key Entities *(include if feature involves data)*

- **Group / team**: a coordinator + its member subagents for one coordinated task, identified by
  a group id, with caps (team size, message count/size).
- **Member**: a bounded child agent run (reuses the 043/048 child run) addressable within a group,
  with a reply (or a contained failure marker).
- **Message**: a bounded, metadata-safe unit addressed from one member to another (or the
  coordinator), held in the recipient's inbox until read.
- **Message channel / broker** (**mechanism — deferred to the maintainer-reviewed plan**): the
  per-run component that routes messages between members; its design is the FR-010 boundary item.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the feature enabled, a coordinator dispatching N sub-tasks collects N replies
  (or contained failure markers) in 100% of covered scenarios, within the caps.
- **SC-002**: A message sent to a member is readable by that member; caps deny excess; unknown
  ids error cleanly — in 100% of covered scenarios.
- **SC-003**: Caps (team size, message count/size, 043 depth) deny excess; a failing member never
  crashes the coordinator/parent; no member or message outlives the parent run.
- **SC-004**: With the feature disabled, behavior is byte-identical to today — the existing test
  suite passes unchanged and no event-schema / content-model change is introduced (any such
  change requires the FR-010 maintainer-approved ADR).

## Assumptions

- A member run reuses the 043/048 bounded child-run; 050 adds **team dispatch + a message
  channel**, reusing the unit-013 orchestration concepts where possible.
- The communication mechanism is **NOT decided in this spec** — it is the FR-010 boundary item,
  resolved by a maintainer-reviewed plan (a new ADR is likely; mirror how ADR 0002 was approved
  for unit 048 before implementation).
- Out of scope (unless the maintainer approves otherwise in the plan): cross-session / persistent
  agents that outlive a run, distributed/remote swarm execution, a durable message store, and any
  human-facing messaging UI.
- Default-off; bounded; contained; Gateway-only (V); metadata-safe (VII). Per Constitution IX the
  concept is borrowed from the reference harnesses but re-derived; III keeps it a bounded, opt-in
  autonomy primitive.
