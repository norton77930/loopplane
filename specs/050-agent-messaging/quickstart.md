# Quickstart / Validation: Agent-to-Agent Messaging & Swarm

See [contracts/messaging-tools.md](contracts/messaging-tools.md),
[data-model.md](data-model.md), and [ADR 0003](../../docs/adr/0003-agent-messaging.md). Reuses the
unit-048/049 supervisor (ADR 0002) + the 043 child run; messages are a separate registry (the
event bus is unchanged).

## Run the unit tests

```powershell
pytest tests/unit/test_agent_messaging.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new messaging tests. With `max_swarm_members = 0`
(default), behavior is byte-identical (no tools registered).

## Validation scenarios (mirror the acceptance scenarios)

1. **Dispatch + collect** — a coordinator dispatches N members (scripted child models); all run as
   bounded child runs; `swarm_get`/`swarm_list` collect each reply. (FR-001, SC-001)
2. **Member failure contained** — a member whose run raises → `failed` with a public-safe marker;
   the others still return; the parent is unaffected. (FR-004, SC-001)
3. **Member-to-member messaging** — member A `message_send` to B; B's `message_inbox` shows A's
   message (resolved via `swarm_member_id`). (FR-002, SC-002)
4. **Message cap** — exceeding `max_swarm_messages` → `message_send` denied (normalized error),
   nothing delivered. (FR-003, SC-002)
5. **Member cap** — exceeding `max_swarm_members` → `swarm_dispatch` denied, no member started. (FR-003)
6. **Depth cap** — the 043 `subagent_depth` cap blocks a member from spawning a swarm without
   bound. (FR-003)
7. **Unknown recipient/member** — `message_send`/`swarm_get` on an unknown id → clear error. (FR-008)
8. **Lifecycle** — a one-shot run with active members returns (does not hang); members cancelled
   at scope exit (no leak). (FR-006)
9. **Event bus unchanged** — assert no new event type / `SCHEMA_VERSION` change; messages do not
   appear on the runtime event stream (they are a separate registry). (FR-010, ADR 0003 D2)
10. **Default-off byte-identical** — `max_swarm_members = 0` → `describe()` registers no
    swarm/messaging tools; existing runs unchanged. (FR-007, SC-004)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`,
`test_public_safety`) and the public-safety scan over the diff.
