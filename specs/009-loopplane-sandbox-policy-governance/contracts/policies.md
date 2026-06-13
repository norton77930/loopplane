# Contract: Policy Deciders

The public surface of `loopplane.governance`. Every factory returns a Phase-1 `PolicyDecider` (an async
`(call, descriptor, context, emitter) -> PolicyVerdict`) for the gateway's decide seam. All deciders are
deterministic, public-safe, default-deny, and **never execute a tool**. Behaviour is normative; signatures
are illustrative.

## Adapter & helpers (FR-001, FR-002)

```python
SimpleDecision = Callable[[ToolCallRequest, ToolDescriptor], PolicyVerdict]

def allow() -> PolicyAllow: ...
def deny(reason: str) -> PolicyDeny: ...
def as_decider(decision: SimpleDecision) -> PolicyDecider: ...   # ignores context/emitter; never invokes
```

## Permission policy (FR-010-FR-011)

```python
def permission_policy(
    rules: Sequence[PermissionRule], *, default: Literal["allow", "deny"] = "deny"
) -> PolicyDecider: ...
```

- `resolve_rules(rules, call.tool_name)`: `"deny"` ⇒ deny, `"allow"` ⇒ allow, `None` ⇒ `default` (defaults to
  **deny**). Reuses the Phase-1 engine — no re-implemented precedence (FR-082, SC-009).

## Path policy (FR-020-FR-021)

```python
def path_policy(allowed_root: str, *, key: str = "path") -> PolicyDecider: ...
```

- Reads `call.input[key]`; missing/non-string ⇒ **deny**. Lexical `.`/`..` normalization (no filesystem);
  any path not contained within `allowed_root` (traversal or absolute escape) ⇒ **deny**; a contained path ⇒
  **allow** (SC-004).

## Capability policy (FR-030)

```python
def capability_policy(
    *, require_read_only: bool = False, require_concurrency_safe: bool = False
) -> PolicyDecider: ...
```

- **Denies** a tool whose declared `read_only` / `concurrency_safe` does not meet the required flags; else
  **allows**. No invocation.

## Budget, cost & quota (FR-040-FR-050)

```python
@dataclass(frozen=True)
class CostModel:
    weights: Mapping[str, int]
    default: int = 1
    def cost(self, tool_name: str) -> int: ...

def budget_policy(ceiling: int, *, cost_model: CostModel = CostModel({})) -> PolicyDecider: ...
def quota_policy(limits: Mapping[str, int]) -> PolicyDecider: ...
```

- `budget_policy`: a stateful decider with an inspectable running spend; **denies** once the next call's cost
  would exceed `ceiling` (SC-007). `quota_policy`: per-tool counts; **denies** a tool at its limit. State is
  in-process per instance (persistent state reserved).

## Combinators & safe-failure (FR-060, FR-071)

```python
def all_of(*policies: PolicyDecider) -> PolicyDecider: ...   # deny-wins; empty ⇒ deny
def safe_failure(policy: PolicyDecider, *, reason: str = "policy error") -> PolicyDecider: ...
def default_deny(reason: str = "denied by default") -> PolicyDecider: ...
```

- `all_of` evaluates in order, short-circuits on the first deny (its reason); all must allow to allow; an
  empty bundle ⇒ **deny** (SC-008). `safe_failure` maps any raised exception to **deny**, never a silent
  allow (SC-003).

## Sandbox profile (FR-070)

```python
def sandbox_profile(
    *, permission=None, path=None, capability=None, budget=None
) -> PolicyDecider: ...
```

- Composes the supplied policies with `all_of` (deny-wins) and wraps in `safe_failure`; one decider for the
  gateway's seam, policy-level (not OS-level).

## Determinism & default-deny (NFR-001, NFR-005)

- Same call + descriptor + state ⇒ identical verdict every run. Every failure mode (no-match, malformed
  argument, raising policy, empty combinator, exhausted budget/quota) ⇒ **deny** with a public-safe reason,
  never a silent allow.
