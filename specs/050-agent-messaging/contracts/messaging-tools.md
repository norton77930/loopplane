# Contract: Agent-to-Agent Messaging & Swarm Tools

Five Gateway tools backed by a per-run `SwarmSupervisor`
([ADR 0003](../../docs/adr/0003-agent-messaging.md)). Registered only when
`RuntimeConfig.max_swarm_members > 0` (default 0 → none; byte-identical). Messages are a separate
in-run registry — **the event bus is unchanged**.

## Tools

| Tool | Input | Result |
| ---- | ----- | ------ |
| `swarm_dispatch` | `instruction: str`, optional `allowed_tools: list[str]` | A member id (returned immediately, non-blocking). |
| `swarm_get` | `member_id: str` | The member's status (and reply if completed) — metadata only. |
| `swarm_list` | — | The run's members: ids + statuses. |
| `message_send` | `to: str` (member id / `"coordinator"`), `content: str` | Appends to the recipient's inbox; confirms delivery. |
| `message_inbox` | — | The caller's messages (sender + content), as text. |

- `swarm_dispatch` / `message_send` are `read_only=False`; `swarm_get` / `swarm_list` /
  `message_inbox` are `read_only=True`. All `concurrency_safe=False` (they touch the registries).

## Behavior

| Case | Result |
| ---- | ------ |
| `swarm_dispatch` (under caps) | Start a member child run (043/048 `run_child`, member id stamped into its context); return the id without blocking. |
| Member completes | Status `completed`; `swarm_get` returns its reply. |
| Member raises / over-runs / empty | Status `failed` with a public-safe marker; coordinator + parent unaffected (no raise across the Gateway). |
| `message_send` (under the message cap, known recipient) | Append the message to the recipient's inbox; confirm. |
| `message_inbox` | Return the caller's messages (resolved from `context.swarm_member_id`; the parent = `"coordinator"`). |
| At the member cap / message cap / 043 depth cap | `ErrorOutput` (normalized); **nothing** started/sent. |
| Unknown recipient / member id | A clear normalized error (no crash). |
| Run/session ends with members active | Members cancelled at the supervisor scope exit; no further delivery (no leak). |
| Feature disabled (`max_swarm_members = 0`) | No tools registered; byte-identical to today. |

## Invariants

- Reachable only through the Tool Gateway (V); member runs reuse the 043/048 seam.
- **No event-schema / `SCHEMA_VERSION` / content-model change** (VI) — messages are a separate
  registry (ADR 0003 D2); child events captured, never on the parent bus.
- Bounded (team size + message count/size + 043 depth) and contained (member failure → marker).
- Lifecycle-bound: members + delivery cancelled at run/session end (`cancel_all`).
- Metadata-safe: least-privilege member toolsets; message content carries no secrets/internal
  paths (VII). Default-off (caps 0) is byte-identical to pre-050 (proven by a test).
- The controller/dispatcher reference only the neutral `SwarmSupervisor` Protocol (the boundary
  audit: no `loopplane.tools` import in controller/loop).
