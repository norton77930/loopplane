# Contracts: Plan Mode (policy + tool + per-run holder + config)

The "interface" this unit exposes is: a decide-stage `plan_mode_policy` decider
composed through the existing combinators; a per-run `PlanModeState` holder carried on
`RunContext`; an `exit_plan_mode` Internal Tool Adapter tool that reuses the existing
human round-trip; and an additive `RuntimeConfig.plan_mode` flag. All enforcement is at
the Tool Gateway decide stage (Constitution V); `exit_plan_mode` returns its outcome
through the gateway output union (`TextBlock` / `ErrorOutput`) and never raises across
the boundary.

## `plan_mode_policy` (decide-stage decider)

```python
PLAN_MODE_ALLOWLIST: frozenset[str] = frozenset({"ask_user", "exit_plan_mode"})

def plan_mode_policy(
    state: PlanModeState | None = None,
    *,
    allowlist: frozenset[str] = PLAN_MODE_ALLOWLIST,
) -> PolicyDecider: ...
```

- `state` given → the policy decides against that holder (unit tests).
- `state` omitted (the assembly path) → the policy decides against
  `context.plan_mode` (the per-run holder on the `RunContext` it is handed at decide
  time).

| Condition (`S` = `state` or `context.plan_mode`) | Verdict |
|--------------------------------------------------|---------|
| `S is None` or `not S.active` | **allow** (no-op) |
| `S.active` and `descriptor.read_only` | allow |
| `S.active` and `descriptor.name in allowlist` | allow |
| `S.active` and not `descriptor.read_only` and name not in allowlist | **deny** ("plan mode is active: …") |

- Decides from the descriptor + the holder only — **never invokes a tool**.
- **Composition** (`host/assembly.py::_build_decider`): one more decider in
  `safe_failure(all_of(<approval?>, network_policy, plan_mode_policy()))` → **deny-wins**
  + **fail-closed**. Installed only when `RuntimeConfig.plan_mode` is `True` (or another
  policy is already present); a run whose `RunContext.plan_mode` is `None` is unaffected
  even when the policy is installed (it is a no-op).

## `PlanModeState` (per-run holder)

```python
@dataclass
class PlanModeState:
    active: bool = True
```

- Mutable single cell, created per run; the decider reads `active`, `exit_plan_mode`
  sets it `False` on approval. Shared by reference via `RunContext.plan_mode`.

## `RunContext.plan_mode` (additive field)

```python
plan_mode: PlanModeState | None = None    # default None = not in plan mode
```

- The single, additive sharing channel between the decider and `exit_plan_mode` (both
  receive the same per-run `RunContext`). Per-run; never process-global.

## `exit_plan_mode` (Internal Tool Adapter tool)

**Description**: Submit a proposed plan for a human approve/reject decision. On
approval, leave plan mode (subsequent non-read-only tools become allowed) and let the
run proceed to execute; on rejection or when no human is available, stay in plan mode.

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "plan": {"type": "string"}
  },
  "required": ["plan"],
  "additionalProperties": false
}
```

**Behaviour contract**

| Condition | Result |
|-----------|--------|
| human approves (answer `approve`, case-insensitive) | set `context.plan_mode.active = False`; `TextBlock` confirming the plan is approved and execution may proceed |
| human rejects (any other answer) | leave plan mode active; `TextBlock` ("plan not approved") |
| no reviewer attached / question cancelled (`ask_question` → `None`) | leave plan mode active; `ErrorOutput` ("no user is available to approve the plan") |
| `context.plan_mode` is `None` (not in plan mode) | still requests the decision; on approve leaves it inactive (idempotent — already allowed) |

- Reuses `context.interactions.ask_question([...])` (the same round-trip as `ask_user`);
  emits the **existing** `question-asked` / `question-answered` events (no new event).
- **Flags**: `network=False`, `read_only=False`, `concurrency_safe=False`.
- **Allowlisted** by `plan_mode_policy` so it is callable while planning.

## `RuntimeConfig.plan_mode` (host opt-in)

```python
plan_mode: bool = False
```

- Additive, public-safe flag (**no secret**). `True` → a run starts with
  `RunContext.plan_mode = PlanModeState(active=True)`. Default `False` → existing runs
  unchanged (no plan-mode policy installed for that reason; `RunContext.plan_mode` stays
  `None`). Coerced in `RuntimeConfig.from_mapping`.

## Invariants (all)

- All enforcement is at the Tool Gateway **decide stage** (Constitution V); plan mode is
  a policy, never a bypass; the policy never resolves or executes a tool.
- `exit_plan_mode` is reachable **only** through the Gateway (it is allowlisted so it
  survives its own gate) and returns only `TextBlock` / `ErrorOutput` — no raw exception
  crosses the boundary (V).
- The per-run holder is per-run, never process-global; one run's plan mode never affects
  another (Decision 2).
- **No event-schema change** (VI): the round-trip reuses the existing question/answer
  events; no `SCHEMA_VERSION` bump, no new event type.
- Plan mode **off / absent** is a provable no-op: the policy decides identically to no
  policy, and every existing tool, descriptor, and policy is unchanged (back-compat).
