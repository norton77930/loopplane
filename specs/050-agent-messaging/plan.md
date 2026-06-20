# Implementation Plan: Agent-to-Agent Messaging & Swarm Coordination

**Branch**: `050-agent-messaging` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/050-agent-messaging/spec.md`

**Boundary review (FR-010)**: **settled by [ADR 0003](../../docs/adr/0003-agent-messaging.md)
(maintainer-approved)**. The capability 043 deferred is implemented **additively**: a new in-run
cross-agent message channel that is a **separate registry, NOT runtime events** (the Event Bus /
`SCHEMA_VERSION` are unchanged, VI), reusing the 048/049 supervisor pattern + the 043 child run.

## Summary

Add agent-facing swarm + messaging tools (`swarm_dispatch` / `swarm_get` / `swarm_list` /
`message_send` / `message_inbox`). A per-run `SwarmSupervisor` (new, `loopplane.tools.messaging`)
owns an injected `anyio` task group, a **member registry** (`member_id → member run + reply`), and
a **message registry** (per-member inboxes `member_id → list[Message]`). `swarm_dispatch` launches
a bounded member child run (reusing the 043/048 `run_child`) with the member's id stamped into its
child `RunContext` (so the member's messaging tools resolve "self"); `message_send` appends a
metadata-safe message to a recipient's inbox; `message_inbox` reads the caller's inbox;
`swarm_get`/`swarm_list` report member status + replies. Gated by `RuntimeConfig` caps (default 0 =
off, byte-identical). Bounded (team size + message count/size + the 043 depth cap), contained (a
member failure → public-safe marker, never a raise), lifecycle-bound (members cancelled at the
supervisor scope exit; reuse 048/049 `cancel_all`). Threaded as `RunContext.swarm` via a neutral
`SwarmSupervisor` Protocol in `loopplane.context` (controller stays tool-agnostic). **No
event-schema / `SCHEMA_VERSION` / content-model change** (messages are a separate registry).

## Technical Context

**Language/Version**: Python 3.11+; `anyio` (existing) for the supervisor task group.

**Primary Dependencies**: none new — reuses `anyio`, the 043/048 child-run, the 048/049 supervisor
+ neutral-Protocol pattern (ADR 0002/0003), the unit-013 orchestration concepts.

**Storage**: in-memory per-run member + message registries; no persistence (cross-session /
durable messaging out of scope).

**Testing**: pytest, offline — scripted child models; assert dispatch+collect, member-to-member
messaging, caps, containment, lifecycle, default-off byte-identity, and the structural audits.

**Target Platform**: cross-platform library

**Project Type**: single project (library + tests)

**Constraints**: additive / reuse-first; default-off byte-identical; Gateway-only tools (V);
**no event-bus / `SCHEMA_VERSION` / content-model change** (VI — messages are a separate
registry, per ADR 0003); controller/loop never import `loopplane.tools` (neutral context
Protocol); bounded + contained + lifecycle-bound + metadata-safe (VII).

**Scale/Scope**: a new supervisor module (member + message registries + 5 tools) + an additive
`RunContext.swarm` field + an additive member-id on the member's child context + the 048-style
controller/dispatcher/host/assembly wiring + `RuntimeConfig` caps + tests. Largest Tier-2 unit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-010 + ADR 0003. ✅
- **III. Agent Harness Before Loop Automation**: A bounded, opt-in, model-invoked autonomy
  primitive (default-off); not the reserved outer loop-automation layer; framed by ADR 0003. ✅
- **IV. Runtime Boundary Clarity**: The new in-run cross-agent communication pattern is recorded
  in ADR 0003; the supervisor is threaded via a neutral context Protocol (no tools import). ✅
- **V. Tool Gateway Ownership**: The five tools dispatch only through the Gateway; member runs
  reuse the 043/048 seam. ✅
- **VI. Event Bus Ownership**: **No event-schema / `SCHEMA_VERSION` / content-model change** —
  messages are a separate in-run registry (ADR 0003 D2); child events captured, never on the
  parent bus. ✅
- **X. Testable Evolution**: Additive; default-off (caps `0`) byte-identical; reversible;
  offline-tested incl. the structural audits. ✅

**Result**: PASS — the one boundary crossing (a new in-run cross-agent communication pattern) is
**maintainer-approved and recorded in ADR 0003**, implemented additively and default-off; no
breaking 001/002 contract change, **no event-bus change**. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/050-agent-messaging/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/messaging-tools.md
└── checklists/requirements.md
docs/adr/0003-agent-messaging.md   # the approved boundary decision
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── messaging.py        # NEW: SwarmSupervisor (member + message registries) + the 5 tools
                        #      (a SwarmToolsAdapter); make_swarm_supervisor[_factory]

src/loopplane/context.py            # MODIFIED: additive RunContext.swarm + a neutral
                                    #   SwarmSupervisor Protocol; additive member-id on the
                                    #   member's child context (so messaging resolves "self")
src/loopplane/controller/{controller,dispatcher}.py   # MODIFIED: thread the swarm supervisor
                                    #   (opaque factory; no loopplane.tools import) — the 048 pattern
src/loopplane/host/{host,assembly,config}.py   # MODIFIED: build/inject the factory + the
                                    #   RuntimeConfig caps; cancel_all at scope exit (one-shot)
src/loopplane/tools/__init__.py + docs/api-reference.md   # MODIFIED: export + document

tests/unit/test_agent_messaging.py  # NEW: offline coverage + structural-audit-safe wiring
```

**Structure Decision**: Mirror unit 048/049's additive wiring exactly (neutral Protocol in
`loopplane.context`; opaque supervisor factory built in `host/assembly`; threaded via `drive` →
`RunContext`; default-off gate; `cancel_all` lifecycle). The 050-specific additions are the
**message registry (inboxes)** + the **member-id on each member's child context** (so a member's
`message_send`/`message_inbox` resolve the caller). Per ADR 0003, messages are a separate registry
— the event bus is untouched.

## Complexity Tracking

> No unjustified complexity. The single boundary crossing (a new in-run cross-agent communication
> pattern) is justified by ADR 0003 (maintainer-approved) and gated default-off; the event bus is
> unchanged. Not a Constitution violation.
