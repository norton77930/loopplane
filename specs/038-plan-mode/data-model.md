# Phase 1 Data Model: Plan Mode

This feature introduces no persisted entities. It adds one per-run state holder + an
additive `RunContext` field, one decide-stage policy, one internal tool descriptor +
handler, and one additive `RuntimeConfig` flag. The "model" here is those shapes plus
the in-memory per-run state.

## New / changed types

### `PlanModeState` (new holder — `src/loopplane/context.py`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `active` | `bool` | `True` | Whether the run is currently in plan mode. The decider denies non-read-only (non-allowlisted) tools while `True`; `exit_plan_mode` sets it `False` on approval. |

A minimal **mutable** dataclass (one cell). Constructed per run. The decider and the
`exit_plan_mode` tool share the **same instance** via the per-run `RunContext`.

### `RunContext.plan_mode` (additive field — `src/loopplane/context.py`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `plan_mode` | `PlanModeState \| None` | `None` | The per-run plan-mode holder. `None` (the default) means **not** in plan mode — the policy is a no-op. |

All existing `RunContext` fields (`session_id`, `working_scope`, `cancellation`,
`turn_budget`, `session_approval_memory`, `feature_toggles`, `interactions`) are
unchanged.

### `RuntimeConfig.plan_mode` (additive field — `src/loopplane/host/config.py`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `plan_mode` | `bool` | `False` | Start runs in plan mode. Carries **no secret**. Default `False` → existing behavior unchanged. |

## New tool descriptor (`ToolDescriptor` — `src/loopplane/tools/internal.py`)

| Tool | `network` | `read_only` | `concurrency_safe` | Inputs (required) |
|------|-----------|-------------|--------------------|-------------------|
| `exit_plan_mode` | `False` | `False` | `False` | `plan` |

> `exit_plan_mode` is **not** `read_only` (it mutates run state and requests a human
> decision), so the plan-mode policy would deny it — except it is in the policy's
> **allowlist**, so it stays callable while planning. It is not `concurrency_safe`
> (it performs a human round-trip and a state flip).

### `exit_plan_mode` input schema

- `plan` (string, required) — the proposed plan, as readable text, submitted for the
  human's approve/reject decision.

## Policy: `plan_mode_policy` (decide-stage — `src/loopplane/governance/plan_mode.py`)

```python
PLAN_MODE_ALLOWLIST: frozenset[str] = frozenset({"ask_user", "exit_plan_mode"})

def plan_mode_policy(
    state: PlanModeState | None = None,
    *,
    allowlist: frozenset[str] = PLAN_MODE_ALLOWLIST,
) -> PolicyDecider: ...
```

Decision table (where `S` is `state` if given, else `context.plan_mode`):

| Condition | Verdict |
|-----------|---------|
| `S` is `None` or `S.active` is `False` | **allow** (no-op) |
| `S.active` and `descriptor.read_only` is `True` | allow |
| `S.active` and `descriptor.name` in `allowlist` | allow |
| `S.active` and `descriptor.read_only` is `False` and name not in `allowlist` | **deny** ("plan mode is active: …") |

Decided from the descriptor + the per-run holder; **no tool invocation**. Composed in
`_build_decider` as one more decider inside the existing
`safe_failure(all_of(<approval?>, network_policy, plan_mode_policy(...)))`:
**deny-wins** (any deny short-circuits) and **fail-closed** (a raised policy → deny).

## Output shapes for `exit_plan_mode` (`AdapterOutput` — unchanged union)

- **Approve** → `TextBlock(text=...)`: a confirmation that the plan is approved and
  execution may proceed (the holder is now inactive). May echo the approved plan.
- **Reject** → `TextBlock(text=...)`: a clear "plan not approved" message (the holder
  stays active; the agent may revise and resubmit).
- **No user available / cancelled** → `ErrorOutput(message="no user is available to
  approve the plan")` (mirrors `ask_user`'s no-user `ErrorOutput`; the holder stays
  active).

No raised exception ever crosses the gateway boundary (V).

## Wiring (per-run state flow)

```text
RuntimeConfig.plan_mode=True
        │  (host/assembly.py)
        ▼
RuntimeController(plan_mode=True)
        │  drive(): build RunContext(plan_mode=PlanModeState(active=True))
        ▼
RunContext  ──────────────┬───────────────────────────┐
   (one instance per run) │                           │
                          ▼                           ▼
        gateway.decide(call, descriptor,    InternalToolAdapter.invoke(
          context, emitter)                   "exit_plan_mode", input, context)
        → plan_mode_policy reads             → _exit_plan_mode flips
          context.plan_mode (deny while        context.plan_mode.active = False
          active)                              on approve
```

## Validation rules (from requirements)

- FR-001: while active, deny non-read-only tools except the allowlist; allow read-only; no-op when inactive.
- FR-002: decide activity from `RunContext` per-run state; absent holder = inactive.
- FR-003: composed through `all_of` + `safe_failure`; no new gateway stage.
- FR-004: `PlanModeState` is the single per-run sharing channel on `RunContext`.
- FR-005/FR-006/FR-007: `exit_plan_mode` reuses `ask_question`; approve clears + success; reject / no-user keeps + normalized outcome.
- FR-008: `exit_plan_mode` is allowlisted and `read_only=False`.
- FR-009: `RuntimeConfig.plan_mode` default `False`; coerced in `from_mapping`; starts a run with an active holder.
- FR-010/FR-011: additive; enforcement at the decide stage only; no loop/gateway/event change.
