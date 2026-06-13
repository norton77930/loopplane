# Sandbox, Policy & Governance (`loopplane.governance`)

Constrain **which tool calls are permitted — before any tool runs**. The layer ships reusable,
deterministic, public-safe **policy deciders** shaped to the Tool Gateway's decide-stage seam: permission,
path, capability, budget, quota, combinators, and a named sandbox profile.

Every policy returns a Phase-1 `PolicyVerdict` (allow / deny-with-reason) and **never executes, resolves, or
OS-sandboxes a tool** — the Tool Gateway stays the single chokepoint for execution (Constitution V). The
layer composes only the public Phase-1 policy/approval contracts and is distinct from the Phase-1 Human
Approval boundary (which owns interactive approval).

## The pieces

| Piece | What it does |
|---|---|
| `permission_policy(rules, *, default="deny")` | Decides by the Phase-1 `resolve_rules` over `PermissionRule`s; no-match ⇒ default-deny. |
| `path_policy(allowed_root, *, key="path")` | Denies a call whose `input[key]` path escapes the root (traversal / absolute / missing) — lexical, no filesystem. |
| `capability_policy(*, require_read_only=, require_concurrency_safe=)` | Denies a tool whose declared flags don't meet the requirement. |
| `budget_policy(ceiling, *, cost_model=)` + `CostModel(weights, default=1)` | Denies once cumulative cost would exceed the ceiling; the running `spent` is inspectable. |
| `quota_policy(limits)` | Denies a tool once its per-tool call limit is reached. |
| `all_of(*policies)` | Deny-wins: the first denying policy short-circuits; all must allow to allow; empty ⇒ deny. |
| `safe_failure(policy)` / `default_deny()` | Any raised policy ⇒ deny (never a silent allow); a terminal always-deny. |
| `sandbox_profile(*, permission=, path=, capability=, budget=)` | One deny-wins, fail-safe bundle for the gateway's seam. |
| `as_decider(decision)` / `allow()` / `deny(reason)` | Adapt a simple `(call, descriptor) -> verdict` into the gateway's `PolicyDecider`. |

## Using it

```python
from loopplane.governance import permission_policy, path_policy, budget_policy, sandbox_profile

profile = sandbox_profile(
    permission=permission_policy(rules),
    path=path_policy("workspace"),
    budget=budget_policy(100),
)
gateway = ToolGateway(decide=profile)   # the gateway consults the profile before executing a tool
```

The host's `ToolGateway` consults the composed decider at its decide stage and obeys the verdict (allow ⇒
execute; deny ⇒ block). See [`examples/governance_quickstart.py`](../examples/governance_quickstart.py).

## Determinism, default-deny, non-execution

- **Deterministic**: no I/O, clock, or randomness; path containment is lexical; budget/quota are in-process
  counters mutated by the call sequence.
- **Default-deny**: a no-match, a malformed/missing argument, a raising policy, an empty combinator, or an
  exhausted budget/quota ⇒ **deny** with a public-safe reason — never a silent allow.
- **Non-execution**: policies return verdicts only; the layer calls no tool, starts no run, and holds no
  execution path; an import + no-invoke audit enforces it.

## Boundary

`loopplane.governance` imports only `loopplane.approval`, `loopplane.model`, `loopplane.context`, and
`loopplane.events` (the policy verdict/decider, the rule engine, the tool-call/descriptor models, and the
signature's run context / emitter). It never imports the `ToolGateway` implementation, a runtime internal,
the Human-Approval interaction symbols, or a sibling layer, and it starts no run.

## Reserved extension points (named, not built)

Actual OS-level process/filesystem sandboxing or containerization; a remote/networked policy service or
remote rule fetch; dynamic policy hot-reload; persistent cross-restart budget/quota state; and ML- or
model-based cost prediction or anomaly detection.
