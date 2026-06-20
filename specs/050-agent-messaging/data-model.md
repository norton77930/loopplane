# Data Model: Agent-to-Agent Messaging & Swarm Coordination

Per [ADR 0003](../../docs/adr/0003-agent-messaging.md). In-memory per-run state; **no new content
block or event** (messages are a separate registry — the event bus is unchanged).

## SwarmSupervisor (new)

Owns the member scope + the member & message registries for one run/session.

| Member | Type | Notes |
| ------ | ---- | ----- |
| task group | `anyio` task group | The unit-048 supervisor scope (ADR 0002); hosts member runs. |
| members | `dict[str, Member]` | `member_id → member record`. |
| inboxes | `dict[str, list[Message]]` | `member_id → messages addressed to it`. |
| `max_members` | int | Team-size cap (`RuntimeConfig.max_swarm_members`). |
| `max_messages` | int | Per-run message cap (`RuntimeConfig.max_swarm_messages`). |
| run_child | callable | Bounded child run (reuses the 043/048 `run_child`), stamping the member id into the child context. |

Methods: `dispatch(instruction, *, allowed_tools=None, child_depth, working_scope) -> member_id |
None` (deny at the member cap / 043 depth cap), `get(member_id)`, `list_members()`,
`send(from_id, to_id, content) -> bool` (deny at the message cap / unknown recipient),
`inbox(member_id) -> list[Message]`, `cancel_all()` (scope exit).

## Member (registry record)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | str | Stable member id (the coordinator is the reserved id `"coordinator"`). |
| `status` | enum | `running` → `completed` / `failed`. |
| `reply` | `str \| None` | The member's final text when `completed`; a public-safe marker when `failed`; `None` while running. |
| (cancel handle) | internal | Used by `cancel_all`. |

## Message (inbox entry)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `from_id` | str | Sender member id (or `"coordinator"`). |
| `to_id` | str | Recipient member id. |
| `content` | str | Metadata-safe text (bounded size; no secrets/internal paths, VII). |

## RunContext additions (additive)

- `swarm: SwarmSupervisor | None = None` — the per-run supervisor; a neutral `SwarmSupervisor`
  Protocol is declared in `loopplane.context` (the 048/049 pattern) so the controller/loop never
  import the tools layer. Set only in `RuntimeController.drive()`.
- `swarm_member_id: str | None = None` — the caller's member id, stamped into a **member's** child
  context by the supervisor so its `message_send`/`message_inbox` resolve "self". `None` (the
  parent/coordinator) → the reserved `"coordinator"` id.

## RuntimeConfig additions (new gates)

- `max_swarm_members: int = 0` (default 0 = off → no supervisor/tools, byte-identical) — team cap.
- `max_swarm_messages: int = 0` — per-run message cap. Both validated as non-negative ints; no
  secret.

## Rules (from FRs + ADR 0003)

| Rule | Source |
| ---- | ------ |
| 5 Gateway tools: dispatch/get/list + message_send/inbox | FR-001/002 |
| dispatch returns a member id without blocking; replies collected by id | FR-001 |
| member-to-member messaging via inboxes (separate registry, not events) | FR-002, D2 |
| caps: team size + message count/size + 043 depth; exceed → deny | FR-003 |
| member failure contained → public-safe reply marker, never a raise | FR-004 |
| least-privilege member toolsets; metadata-safe messages | FR-005 |
| members + delivery cancelled at run/session end (no leak) | FR-006 |
| default-off byte-identical (caps 0) | FR-007 |
| unknown recipient/member id → clear normalized error | FR-008 |
| no event-bus / SCHEMA_VERSION / content-model change | FR-010, ADR 0003 D2 |
