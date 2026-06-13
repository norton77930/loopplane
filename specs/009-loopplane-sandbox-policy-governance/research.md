# Research: Sandbox, Policy & Governance Layer (Phase-9)

Phase-0 decisions for `loopplane.governance`. Every decision composes the public Phase-1 policy contracts;
the Tool Gateway keeps execution (Constitution V), the Phase-1 engine keeps rule precedence, and the Phase-1
Human Approval boundary keeps interactive approval.

## Inherited context, no re-derivation (NFR-003, FR-082)

The layer consumes these **public** surfaces verbatim and adds only decision logic above them:

| Surface | Source (public) | Used by |
|---|---|---|
| `PolicyAllow` / `PolicyDeny(reason)` / `PolicyVerdict` | `loopplane.approval` | every policy's return value |
| `PolicyDecider = Callable[[ToolCallRequest, ToolDescriptor, RunContext, EventEmitter], Awaitable[PolicyVerdict]]` | `loopplane.approval` | the gateway's decide-stage shape every policy targets |
| `PermissionRule` / `RuleEffect` / `RuleScope` / `resolve_rules(rules, tool_name)` | `loopplane.approval` | the permission policy (reused, not re-implemented) |
| `ToolCallRequest` (`call_id`, `tool_name`, `input`) | `loopplane.model` | the decision input (tool name + arguments) |
| `ToolDescriptor` (`read_only`, `concurrency_safe`, …) | `loopplane.model` | the capability policy |
| `RunContext` / `EventEmitter` | `loopplane.context` / `loopplane.events` | the trailing decider-signature parameters (accepted, usually unused) |

## Decision 1 — Policies are deciders shaped to the gateway signature; a small adapter hides the trailing params

- **Decision**: define `SimpleDecision = Callable[[ToolCallRequest, ToolDescriptor], PolicyVerdict]` and
  `as_decider(decision) -> PolicyDecider` that wraps a simple `(call, descriptor) -> verdict` into the
  gateway's async four-parameter `PolicyDecider` (accepting and ignoring `RunContext` / `EventEmitter`). Each
  policy factory returns a ready-to-plug `PolicyDecider`.
- **Rationale**: the gateway consults a `PolicyDecider`; most policies decide from the call + descriptor only.
  The adapter keeps each policy small and uniform while producing exactly the gateway's shape (FR-001).
- **Alternatives rejected**: *Each policy re-declaring the full four-parameter async closure* — repetitive
  and error-prone; the adapter centralizes it.

## Decision 2 — Permission policy reuses the Phase-1 `resolve_rules`; no re-implemented precedence

- **Decision**: `permission_policy(rules, *, default="deny")` returns a decider that calls
  `resolve_rules(rules, call.tool_name)`: `"deny"` ⇒ `PolicyDeny`, `"allow"` ⇒ `PolicyAllow`, `None`
  (no match) ⇒ the configured `default`, which **defaults to deny** (safe by default).
- **Rationale**: rule precedence (session-local > project > user; deny > allow) is Phase-1's; reusing it
  guarantees consistency and non-duplication (FR-010, FR-011, FR-082, SC-009).
- **Alternatives rejected**: *Re-implementing precedence* — divergence risk; forbidden by FR-082.

## Decision 3 — Path containment is pure lexical normalization (no filesystem access)

- **Decision**: `path_policy(allowed_root, *, key="path")` reads `call.input[key]`; a missing or non-string
  value ⇒ **deny**. Otherwise it normalizes the path **lexically** (resolve `.` / `..` with a POSIX-style
  pure path, no filesystem call) relative to the root and **denies** any result that is not contained within
  the root — including parent-directory traversal and absolute paths outside it; a contained path ⇒ **allow**.
- **Rationale**: FR-020/FR-021/SC-004 — deterministic and platform-stable (no filesystem, no symlink
  surprises). Lexical containment is sufficient to reject traversal and absolute escapes for a host-supplied
  root and argument.
- **Alternatives rejected**: *`os.path.realpath` / filesystem resolution* — non-deterministic, platform- and
  state-dependent, and touches the filesystem; rejected.

## Decision 4 — Capability policy decides by declared descriptor flags

- **Decision**: `capability_policy(*, require_read_only=False, require_concurrency_safe=False)` returns a
  decider that **denies** a tool whose declared `read_only` / `concurrency_safe` does not meet the required
  flags (e.g., a non-read-only tool under `require_read_only=True`), else **allows**.
- **Rationale**: FR-030 — a read-only or concurrency-safe profile is a common sandbox need, decided from the
  declared identity without invocation.

## Decision 5 — Budget, cost, and quota are in-process, deterministic counters

- **Decision**: `CostModel(weights, *, default=1)` maps a tool name to a deterministic cost; `budget_policy(
  ceiling, *, cost_model=CostModel())` returns a **stateful** decider that tallies spend and **denies** once
  adding the next call's cost would exceed the ceiling (the running spend is inspectable). `quota_policy(
  limits)` denies a tool once its per-tool call count reaches its limit.
- **Rationale**: FR-040/FR-041/FR-050/SC-007 — cost/quota governance with deterministic per-call accounting.
  State is in-process per decider instance for a run; persistent state is reserved (FR-093).
- **Alternatives rejected**: *A shared global tally* — non-deterministic across loops; each decider instance
  owns its own counter.

## Decision 6 — The combinator is deny-wins; an empty combinator denies

- **Decision**: `all_of(*policies)` returns a decider that evaluates the policies in order and **short-
  circuits on the first deny** (returning its reason); **all** must allow to allow. An empty `all_of()`
  returns **deny** (safe by default).
- **Rationale**: FR-060/SC-008 — composing constraints must never let a denied call through; deny-wins is the
  safe precedence. An empty bundle denying is the safe default.
- **Alternatives rejected**: *allow-wins / any-of as the default* — unsafe for governance; a permissive
  combinator is not built this phase.

## Decision 7 — Safe-failure wraps any decider; a raising policy becomes deny

- **Decision**: `safe_failure(policy)` wraps a `PolicyDecider` so that if it raises, the verdict is **deny**
  with a public-safe reason; `default_deny(reason=…)` is a terminal decider that always denies.
- **Rationale**: FR-071/NFR-005/SC-003 — every failure mode maps to deny, never a silent allow. The sandbox
  profile wraps its composed decider in `safe_failure`.
- **Alternatives rejected**: *Letting a policy exception propagate* — the gateway might treat an error
  ambiguously; the layer guarantees an explicit deny instead.

## Decision 8 — The sandbox profile bundles policies via the combinator + safe-failure

- **Decision**: `sandbox_profile(*, permission=None, path=None, capability=None, budget=None)` composes the
  supplied policies with `all_of` and wraps the result in `safe_failure`, returning a single `PolicyDecider`
  the host applies at the gateway's seam.
- **Rationale**: FR-070 — one named, deny-wins, fail-safe bundle is the ergonomic "sandbox" a host applies;
  it is policy-level, not OS-level (FR-090 reserved).

## Decision 9 — Determinism, fail-safe (default-deny), non-execution are first-class

- **Determinism (NFR-001/SC-002)**: no I/O, network, clock, or randomness; verdicts derive from the call,
  descriptor, and in-process counters.
- **Fail-safe (NFR-005/SC-003)**: a no-match, a malformed/missing argument, a raising policy, an empty
  combinator, or an exhausted budget/quota all map to **deny** with a public-safe reason — never a silent
  allow.
- **Non-execution (NFR-006/SC-005)**: policies return verdicts only; the layer calls no tool and holds no
  execution path; a contract test asserts zero invocations.

## Decision 10 — Distinct from the Phase-1 Human Approval boundary

- **Decision**: this layer produces **non-interactive policy verdicts** for the gateway's decide seam. It
  does not call the `InteractionBroker`, request human input, or orchestrate approval resolutions — that
  remains the Phase-1 Human Approval boundary (`loopplane.approval.interactions`), which this layer does not
  import.
- **Rationale**: FR-082 — clear separation between automatic policy (here) and interactive approval (Phase-1).
