# Tasks: Agent-to-Agent Messaging & Swarm Coordination

**Feature**: 050-agent-messaging | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0003](../../docs/adr/0003-agent-messaging.md)

**Scope**: additive, cross-cutting — a new `tools/messaging.py` (SwarmSupervisor: member registry
+ message registry/inboxes + 5 tools) + `RunContext`/`RuntimeConfig` fields + controller/
dispatcher/host/assembly wiring + export + api-reference + tests. Default-off
(`max_swarm_members = 0`) byte-identical. **Messages are a separate registry — NO event-bus /
SCHEMA_VERSION / content-model change** (ADR 0003 D2). Reuses the 048/049 supervisor + the 043/048
child-run.

**Tests**: requested (TDD-friendly).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Add gates `RuntimeConfig.max_swarm_members: int = 0` + `max_swarm_messages: int = 0`
  to `src/loopplane/host/config.py` (coerce + validate non-negative ints; no secret), mirroring
  `max_background_tasks`/`max_schedules`.
- [ ] T002 In `src/loopplane/context.py` add a neutral `SwarmSupervisor` Protocol + a
  `SwarmSupervisorFactory` alias (the 048/049 pattern), the additive field
  `RunContext.swarm: SwarmSupervisor | None = None`, and `RunContext.swarm_member_id: str | None =
  None` (the caller's member id, stamped into a member's child context). The controller/loop must
  reference the Protocol, never `loopplane.tools`.

## Phase 2: User Story 1 — Dispatch a team & collect replies (P1) 🎯 MVP

- [ ] T003 [US1] Create `src/loopplane/tools/messaging.py`: a `SwarmSupervisor` holding an injected
  `anyio` task group, a member registry (`member_id -> Member(status, reply)`), a message registry
  (`member_id -> list[Message]`), the caps, and the injected `run_child` (reuse the 043/048 child
  run) that stamps the member's id into its child `RunContext` (`swarm_member_id`).
  `dispatch(instruction, *, allowed_tools=None, child_depth, working_scope) -> member_id | None`:
  deny at the member cap / 043 depth cap; else `start_soon` a member run recording `completed` +
  reply, or (contained) `failed` + a public-safe marker. Add `make_swarm_supervisor[_factory]`
  (the 048 `make_supervisor_factory` pattern) so the host assembly owns the tools import.
- [ ] T004 [US1] Add the `swarm_dispatch` Gateway tool (descriptor + handler) reading
  `context.swarm`; write `tests/unit/test_agent_messaging.py` asserting dispatch returns a member
  id without blocking + replies collected; a failing member is contained (others return).

## Phase 3: User Story 2 — Agents exchange messages (P2)

- [ ] T005 [US2] Add `swarm_get`, `swarm_list`, `message_send`, `message_inbox` tools (descriptors
  + handlers + dispatch): get/list report member status + reply (metadata); `message_send(to,
  content)` appends to the recipient's inbox (sender resolved from `context.swarm_member_id`, the
  parent = `"coordinator"`), denying at the message cap / unknown recipient; `message_inbox()`
  returns the caller's messages.
- [ ] T006 [US2] Extend the tests: A→B messaging readable via inbox; message cap denial; unknown
  recipient/member-id error.

## Phase 4: User Story 3 — Bounded, contained, lifecycle, event-bus-unchanged (P3)

- [ ] T007 [US3] Enforce the member cap + message cap + 043 depth cap; ensure a failing member is
  recorded (coordinator/parent unaffected); ensure members are cancelled when the supervisor's
  task-group scope exits (`cancel_all`; no leak); ensure messages are metadata-safe (VII).
- [ ] T008 [US3] Extend the tests: member-cap + message-cap + depth-cap denial, containment,
  lifecycle (one-shot run with active members does NOT hang — `cancel_all`), **event-bus-unchanged**
  (no new event type / `SCHEMA_VERSION`; messages do not appear on the runtime event stream), and
  **default-off byte-identity** (`max_swarm_members = 0` → no tools registered).

## Phase 5: Wiring (scope owners thread the supervisor)

- [ ] T009 Wire additively (the 048/049 pattern): optional
  `RuntimeController.drive(..., swarm_supervisor=None)` stamps it onto the `RunContext`; the
  **Dispatcher** builds a supervisor from its session task group (when `max_swarm_members > 0`) +
  calls `cancel_all` on close; the one-shot **`host.run`** wraps a task group + calls `cancel_all`
  after `drive`; `host/assembly.py` registers the 5 tools + builds/injects the opaque supervisor
  factory only when `max_swarm_members > 0`. The controller holds the opaque factory (typed via the
  context Protocol) — **no `loopplane.tools` import in controller/dispatcher**.
- [ ] T010 Export `SwarmSupervisor` + the tool adapter from `src/loopplane/tools/__init__.py` and
  add them to `docs/api-reference.md` (unit-014 bijection), mirroring 048/049.

## Phase 6: Polish & Cross-Cutting

- [ ] T011 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof + default-off byte-identity). ALSO confirm the structural
  audits stay green: `test_no_execution_path_outside_the_gateway` (controller/loop do not import
  `loopplane.tools`) and `test_public_safety` (no secret-looking literals). ALSO confirm no
  event-schema change (the events serialization/`SCHEMA_VERSION` tests unchanged).

## Dependencies

- T001, T002 → block all. T003 → T004 (MVP). T004 → T005 → T006. T003/T004 → T007 → T008.
  T002/T003 → T009. T003 → T010. T010 → T011 (gates last).

## Implementation strategy

- **MVP = Phase 1 + 2 (US1)** + T009 wiring. US2 adds messaging; US3 adds safety + the
  event-bus-unchanged proof. The implement is large/cross-cutting — a fork subagent MAY do the
  mechanical multi-file work (mirroring the now-correct 048/049 module + wiring exactly), then the
  four gates + the two structural audits + the event-bus-unchanged check are verified + committed
  in the main session.
- All changes additive; default-off (`max_swarm_members = 0`) byte-identical; reuse 048/049 + the
  043 child run; per ADR 0003 messages are a separate registry (no event-bus change).

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
