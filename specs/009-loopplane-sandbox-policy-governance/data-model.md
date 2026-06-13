# Data Model: Sandbox, Policy & Governance Layer (Phase-9)

All types are public-safe value types or deciders. The layer owns no execution path and only in-process
per-instance counters. Types mirror the existing Phase-1 style: frozen dataclasses + `Protocol`,
`from __future__ import annotations`, `TYPE_CHECKING` imports to keep the boundary tight. Every policy
factory returns a Phase-1 `PolicyDecider` ready to plug into the gateway's decide seam.

## 1. Decision adapter & helpers (FR-001, FR-002)

```python
SimpleDecision = Callable[[ToolCallRequest, ToolDescriptor], PolicyVerdict]

def allow() -> PolicyAllow: ...
def deny(reason: str) -> PolicyDeny: ...

def as_decider(decision: SimpleDecision) -> PolicyDecider:
    """Adapt a simple (call, descriptor) -> verdict into the gateway's async
    (call, descriptor, context, emitter) -> verdict PolicyDecider."""
```

- `as_decider` accepts and ignores the trailing `RunContext` / `EventEmitter`; it never executes a tool.
- `allow()` / `deny(reason)` return the Phase-1 `PolicyAllow` / `PolicyDeny`.

## 2. Permission policy (US1, FR-010-FR-011)

```python
def permission_policy(
    rules: Sequence[PermissionRule], *, default: Literal["allow", "deny"] = "deny"
) -> PolicyDecider: ...
```

- Calls `resolve_rules(rules, call.tool_name)`: `"deny"` ⇒ deny, `"allow"` ⇒ allow, `None` ⇒ `default`
  (defaults to **deny**). Reuses the Phase-1 engine; no re-implemented precedence (FR-082).

## 3. Path policy (US2, FR-020-FR-021)

```python
def path_policy(allowed_root: str, *, key: str = "path") -> PolicyDecider: ...
```

- Reads `call.input[key]`. A missing or non-string value ⇒ **deny**. Else normalizes the path lexically
  (POSIX-style `.`/`..` resolution, **no filesystem access**) and **denies** any result not contained within
  `allowed_root` (traversal or absolute escape); a contained path ⇒ **allow** (FR-021, SC-004).

## 4. Capability policy (US4, FR-030)

```python
def capability_policy(
    *, require_read_only: bool = False, require_concurrency_safe: bool = False
) -> PolicyDecider: ...
```

- **Denies** a tool whose declared `read_only` / `concurrency_safe` does not meet the required flags; else
  **allows**. Decided from the descriptor's declared identity, no invocation.

## 5. Budget, cost model & quota (US3, FR-040-FR-050)

```python
@dataclass(frozen=True)
class CostModel:
    weights: Mapping[str, int]
    default: int = 1

    def cost(self, tool_name: str) -> int: ...        # weights.get(tool_name, default)

def budget_policy(ceiling: int, *, cost_model: CostModel = CostModel({})) -> PolicyDecider: ...
def quota_policy(limits: Mapping[str, int]) -> PolicyDecider: ...
```

- `budget_policy` returns a **stateful** decider holding a running `spent` tally; it **denies** once adding
  the next call's `cost_model.cost(tool_name)` would exceed `ceiling`, else allows and adds the cost. The
  spend is inspectable (the decider exposes it). Deterministic given the call sequence (FR-040, FR-041,
  SC-007).
- `quota_policy` returns a stateful decider holding per-tool call counts; it **denies** a tool once its count
  reaches `limits[tool_name]` (tools with no limit are unrestricted) (FR-050).
- State is in-process per decider instance for a run (persistent state reserved — FR-093).

## 6. Combinators & safe-failure (US4, US5, FR-060, FR-071)

```python
def all_of(*policies: PolicyDecider) -> PolicyDecider:
    """Deny-wins: evaluate in order, short-circuit on the first deny (its reason);
    all must allow to allow. Empty all_of() ⇒ deny (safe by default)."""

def safe_failure(policy: PolicyDecider, *, reason: str = "policy error") -> PolicyDecider:
    """Wrap a decider so any raised exception maps to deny (never a silent allow)."""

def default_deny(reason: str = "denied by default") -> PolicyDecider:
    """A terminal decider that always denies."""
```

## 7. Sandbox profile (US5, FR-070)

```python
def sandbox_profile(
    *,
    permission: PolicyDecider | None = None,
    path: PolicyDecider | None = None,
    capability: PolicyDecider | None = None,
    budget: PolicyDecider | None = None,
) -> PolicyDecider:
    """Compose the supplied policies with all_of (deny-wins) and wrap in
    safe_failure, returning one PolicyDecider for the gateway's seam (FR-070)."""
```

- A profile with no policies composes to `all_of()` ⇒ **deny** (safe by default), wrapped in `safe_failure`.

## Relationships

```text
ToolCallRequest + ToolDescriptor ──► PolicyDecider (permission | path | capability | budget | quota)
        │ each returns PolicyAllow | PolicyDeny(reason)
        ▼
   all_of(...) (deny-wins) ──► safe_failure(...) ──► sandbox_profile  ──► gateway decide seam
        │                                                                       │ allow ⇒ gateway executes
        ▼                                                                       ▼ deny ⇒ gateway blocks
   PolicyVerdict                                                          (the gateway is the only executor)
```

## Validation & invariants

- **Determinism (NFR-001)**: pure functions of `(call, descriptor, in-process state)`; no I/O, clock, or
  randomness; path containment is lexical.
- **Default-deny (NFR-005)**: a no-match, malformed/missing argument, raising policy, empty combinator, or
  exhausted budget/quota ⇒ **deny** with a public-safe reason.
- **Non-execution (NFR-006)**: deciders return verdicts only; no `invoke`, no run started, no gateway import.
- **Public-safe (NFR-002)**: deny reasons and configuration carry no secrets, paths, or private names.
