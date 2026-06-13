# Feature Specification: LoopPlane Sandbox, Policy & Governance Layer

**Feature Branch**: `main` (main-only autopilot)

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Define the LoopPlane Sandbox, Policy & Governance layer (unit 009) on top of the Phase-1 runtime foundation, composing only its public policy/approval contracts (the Tool Gateway's decide-stage PolicyDecider, the PermissionRule rules engine, and the tool-call/tool-descriptor models): reusable, deterministic, public-safe POLICY DECISIONS — permission, path, capability, budget, quota, cost governance, safe-failure, combinators, and a sandbox profile — that a host plugs into the gateway's decide seam. It never executes or OS-sandboxes a tool; the Tool Gateway stays the single chokepoint (Constitution V), and this layer only decides allow/deny before execution."

## Overview

The Sandbox, Policy & Governance layer (Phase-9) lets a host **constrain which tool calls are permitted —
before any tool runs**. It ships reusable, deterministic, public-safe **policy deciders** — permission,
path, capability, budget, quota, cost, and safe-failure — plus combinators and a named **sandbox profile**,
each shaped to the Tool Gateway's decide-stage interface so a host plugs them into the gateway's policy seam.

It is a **decision layer**: every policy returns an **allow** or **deny** verdict and **never executes,
resolves, or OS-sandboxes a tool** — the Tool Gateway remains the single chokepoint that executes tools
(Constitution V — Tool Gateway Ownership). It composes the existing Phase-1 permission-rule engine rather
than re-implementing it, and it is distinct from the Phase-1 Human Approval boundary, which owns interactive
approval. It is deterministic, fail-safe (defaulting to **deny**), and offline.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gate tool calls by permission rules (Priority: P1)

A host wants only an approved set of tools to be callable. It configures a **permission policy** from a set
of permission rules (tool-name matchers with allow/deny effects and user/project/session-local precedence)
and plugs it into the gateway's decide seam. A call to an allowed tool is permitted; a denied or unmatched
tool is **denied with a reason** and never executes.

**Why this priority**: Gating which tools may run is the core governance primitive and the safe default;
it exercises the full policy → verdict path. This is the minimum slice that delivers value.

**Independent Test**: With scripted permission rules and tool calls, assert an allowed tool yields **allow**,
a denied tool yields **deny** with a reason, and an unmatched tool defaults to **deny** (safe by default).

**Acceptance Scenarios**:

1. **Given** a permission policy that allows tool `read`, **When** `read` is called, **Then** the verdict is
   **allow**.
2. **Given** a permission policy that denies tool `write`, **When** `write` is called, **Then** the verdict
   is **deny** with a public-safe reason.
3. **Given** a tool matched by no rule, **When** it is called, **Then** the verdict defaults to **deny**.

---

### User Story 2 - Restrict tool arguments to an allowed path root (Priority: P2)

A host wants file-touching tools confined to a directory. It configures a **path policy** with an allowed
root and the argument key that carries the path; a call whose path argument escapes the root — via
parent-directory traversal or an absolute path outside it — is **denied**.

**Why this priority**: Argument-level confinement is the most common sandbox need; independent of the
permission gate.

**Independent Test**: With an allowed root and scripted calls, assert a path inside the root is allowed, a
`..` traversal is denied, an absolute path outside the root is denied, and a missing/malformed path argument
is denied (never a silent allow).

**Acceptance Scenarios**:

1. **Given** a path policy rooted at a directory, **When** a call's path stays within the root, **Then** the
   verdict is **allow**.
2. **Given** the same policy, **When** a call's path escapes the root (traversal or absolute), **Then** the
   verdict is **deny** with a reason.
3. **Given** the same policy, **When** the path argument is missing or malformed, **Then** the verdict is
   **deny** (never a silent allow).

---

### User Story 3 - Bound cost and per-tool quota (Priority: P2)

A host wants to cap how much a loop can spend and how often a tool runs. It configures a **budget policy**
(a cumulative cost or call ceiling, with deterministic per-tool **cost weights** and an inspectable running
spend) and a **quota policy** (per-tool call limits). Once a ceiling is reached, further calls are **denied**.

**Why this priority**: Cost and quota governance protects against runaway loops; independent of permission
and path policies.

**Independent Test**: With a budget of N cost units and scripted costed calls, assert calls are allowed until
the budget is exhausted then denied, and the running spend is inspectable; with a per-tool quota, assert the
tool is denied once its quota is reached.

**Acceptance Scenarios**:

1. **Given** a budget policy with a ceiling, **When** calls accumulate cost up to the ceiling, **Then** they
   are allowed; the next call is **denied** and the spend reflects the total.
2. **Given** a quota policy of K calls for tool `fetch`, **When** `fetch` is called a (K+1)th time, **Then**
   the verdict is **deny**.

---

### User Story 4 - Compose policies and gate by capability (Priority: P2)

A host wants several constraints at once and a read-only mode. It composes multiple policies into one with a
documented **deny-wins** precedence (the first denying policy short-circuits with its reason; all must allow
to allow) and adds a **capability policy** that denies a non-read-only tool in a read-only profile.

**Why this priority**: Real governance combines constraints; the combinator is what makes a sandbox.

**Independent Test**: Compose an allowing and a denying policy; assert the combination denies with the
denier's reason. With a read-only capability policy, assert a mutating tool is denied and a read-only tool
allowed.

**Acceptance Scenarios**:

1. **Given** a combinator over policies A (allow) and B (deny), **When** a call is decided, **Then** the
   verdict is **deny** with B's reason (deny-wins).
2. **Given** a read-only capability policy, **When** a non-read-only tool is called, **Then** the verdict is
   **deny**; a read-only tool is **allow**.

---

### User Story 5 - Fail safe and apply a named sandbox profile (Priority: P3)

A host wants one named bundle and a guarantee that nothing slips through on error. It applies a **sandbox
profile** composing path + permission + capability + budget into a single decider, wrapped by **safe-failure
governance** so any policy that raises, or any ambiguous input, becomes a **deny** — never a silent allow.

**Why this priority**: Bundling and fail-safe harden the layer; lowest priority because the individual
policies deliver value first.

**Independent Test**: Apply a sandbox profile and assert it composes its policies (deny-wins); replace one
policy with a raising one and assert the verdict is **deny** with a fail-safe reason, never allow.

**Acceptance Scenarios**:

1. **Given** a sandbox profile, **When** a call violates any bundled policy, **Then** the verdict is
   **deny** with that policy's reason.
2. **Given** a policy that raises, **When** it is decided under safe-failure governance, **Then** the verdict
   is **deny** with a public-safe reason — never **allow**.

---

### Edge Cases

- **No matching permission rule** → **deny** (safe default).
- **Missing/malformed path argument, or a non-string path** → **deny**, never a silent allow.
- **A path equal to the root, or a normalized child** → **allow**; a `..` escape or sibling/absolute escape →
  **deny**.
- **Budget/quota exactly at the ceiling** → the documented boundary (the call that would exceed is denied).
- **A policy that raises** → **deny** with a fail-safe reason (never allow).
- **An empty combinator (no policies)** → the documented default (**deny**, safe by default).
- **Iterating an unknown future verdict reason** → tolerated (verdicts are allow/deny only).

## Requirements *(mandatory)*

### Policy verdict & decider (foundational)

- **FR-001**: The layer MUST express every decision as the Phase-1 **policy verdict** — **allow** or **deny
  with a public-safe reason** — and MUST produce deciders shaped to the Tool Gateway's decide-stage interface
  so a host plugs them into the gateway's policy seam (FR-080).
- **FR-002**: Every policy MUST be a pure decision over its inputs (the tool call, the tool descriptor, and
  its own configuration/state); it MUST NOT execute, resolve, or OS-sandbox a tool, and MUST NOT start a run.
- **FR-003**: Every policy MUST be deterministic: the same call, descriptor, and policy state yield the same
  verdict on every run.

### Permission policy (US1)

- **FR-010**: The layer MUST provide a **permission policy** that decides a call by composing the **existing
  Phase-1 permission-rule resolution** over a set of permission rules (it MUST NOT re-implement rule
  precedence).
- **FR-011**: A rule **deny** MUST produce **deny**; a rule **allow** MUST produce **allow**; a **no-match**
  MUST fall back to a configurable default that **defaults to deny** (safe by default).

### Path policy (US2)

- **FR-020**: The layer MUST provide a **path policy** that, given an allowed root and the input key carrying
  a path, **denies** a call whose path escapes the root — via parent-directory traversal or an absolute path
  outside it — and **allows** a path contained within the root.
- **FR-021**: Path containment MUST be a deterministic normalization check (no filesystem access); a missing,
  non-string, or malformed path argument MUST map to **deny** (FR-071), never a silent allow.

### Capability policy (US4)

- **FR-030**: The layer MUST provide a **capability policy** that decides by the tool descriptor's declared
  capability (e.g., **deny** a non-read-only tool in a read-only profile; **allow** a read-only tool).

### Budget, cost & quota (US3)

- **FR-040**: The layer MUST provide a **budget policy** that denies once a cumulative ceiling (call count or
  cost units) is reached; it MUST be deterministic given the call sequence.
- **FR-041**: The layer MUST provide a **cost model** of deterministic per-tool cost weights (with a default
  weight) and an **inspectable running spend** the budget policy consults.
- **FR-050**: The layer MUST provide a **quota policy** enforcing per-tool call limits, denying a tool once
  its limit is reached.

### Combinators & sandbox profile (US4, US5)

- **FR-060**: The layer MUST provide a **combinator** that composes several policies into one with a
  documented **deny-wins** precedence: the first denying policy short-circuits with its reason; **all** must
  allow to allow. An empty combinator MUST default to **deny** (safe by default).
- **FR-070**: The layer MUST provide a **sandbox profile** — a named bundle composing path + permission +
  capability + budget policies into a single decider — applied at the gateway's policy seam (policy-level,
  not OS-level).

### Safe-failure governance

- **FR-071**: The layer MUST provide **safe-failure** governance: a wrapper that maps any policy that raises,
  or any ambiguous/unknown input, to **deny** with a public-safe reason — never a silent allow — and a
  terminal **default-deny** policy.

### Boundary, non-execution & non-duplication

- **FR-080**: The layer MUST integrate **only** by producing deciders the Tool Gateway consults at its policy
  seam; it MUST NOT execute, resolve, authorize-by-side-effect, or OS-sandbox a tool, and MUST NOT start a
  Loop Run (Constitution V).
- **FR-081**: The layer MUST read only the **public** Phase-1 policy/approval contracts (the policy
  verdict/decider, the permission-rule engine, and the tool-call/tool-descriptor models, plus the run context
  and event emitter the decider signature carries). It MUST NOT import a Phase-1 runtime control internal, a
  Phase-2 host symbol, the Tool Gateway implementation, or a sibling phase layer.
- **FR-082**: The layer MUST NOT re-implement rule precedence, tool execution, or human-approval interaction
  orchestration; rule precedence reuses the Phase-1 engine, execution stays the gateway's, and interactive
  approval stays the Phase-1 Human Approval boundary's.

### Reserved extension points

- **FR-090** (reserved, named-not-built): actual OS-level process/filesystem sandboxing or containerization.
- **FR-091** (reserved): a remote/networked policy service or remote rule fetch.
- **FR-092** (reserved): dynamic policy hot-reload.
- **FR-093** (reserved): persistent cross-restart budget/quota state.
- **FR-094** (reserved): ML- or model-based cost prediction or anomaly detection.
  Each reserved point MUST be named in docs and MUST NOT be implemented this phase.

### Non-Functional Requirements

- **NFR-001 (Determinism)**: Given a scripted call, descriptor, and policy configuration/state, every verdict
  MUST be identical on every run.
- **NFR-002 (Public-safety)**: No committed artifact may contain secrets, credentials, private paths, private
  project/repository names, internal names, or internal network addresses; deny reasons MUST be public-safe.
- **NFR-003 (Boundary)**: The layer composes only the public Phase-1 policy/approval contracts; it references
  no Tool Gateway implementation, runtime control internal, Phase-2 host, or sibling layer — enforced by an
  import audit.
- **NFR-004 (Language & safety)**: All artifacts are English and public-safe.
- **NFR-005 (Fail-safe)**: Every failure mode — a raising policy, a malformed/missing argument, a no-match,
  an exhausted budget/quota — MUST map to an explicit **deny** with a public-safe reason, never a silent
  allow, a crash, or a hang.
- **NFR-006 (Non-execution)**: The layer returns policy verdicts only; it invokes zero tools and never
  bypasses the Tool Gateway.

### Key Entities

- **Policy Verdict**: **allow**, or **deny** with a public-safe reason (the Phase-1 verdict).
- **Policy Decider**: a deterministic decision over a tool call + descriptor, shaped to the gateway's policy
  seam.
- **Permission / Path / Capability / Budget / Quota Policy**: the concrete deciders.
- **Cost Model**: deterministic per-tool weights + an inspectable running spend.
- **Policy Combinator**: composes deciders with deny-wins precedence.
- **Safe-failure wrapper / default-deny**: the fail-safe terminal.
- **Sandbox Profile**: a named bundle of policies applied as one decider.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A host gates tool execution by plugging a single permission policy into the gateway's decide
  seam; allowed tools are permitted and denied/unmatched tools never execute.
- **SC-002**: Every policy is 100% reproducible — the same call, descriptor, and state yield an identical
  verdict every run.
- **SC-003**: An unmatched tool, a malformed argument, or a raising policy always yields **deny** (0 silent
  allows across the suite).
- **SC-004**: A path escaping the allowed root is always denied (0 escapes permitted across the suite).
- **SC-005**: The layer invokes 0 tools and starts 0 runs; execution occurs only through the Tool Gateway.
- **SC-006**: No committed artifact contains secrets, private paths, internal names, or internal network
  addresses (public-safety scan green).
- **SC-007**: Budget and quota ceilings are enforced exactly — a call that would exceed a ceiling is denied,
  and the running spend equals the sum of consumed cost weights.
- **SC-008**: The combinator is deny-wins — any single denying policy denies the whole (0 cases where a
  denied call is allowed by the combination).
- **SC-009**: The layer composes the Phase-1 permission-rule engine and never re-implements rule precedence
  (import-boundary audit green; permission verdicts match the engine).
- **SC-010**: The reserved extension points (OS sandboxing, remote policy, hot-reload, persistent state, ML
  cost) are absent from the shipped surface.

## Assumptions

- The layer composes the existing public Phase-1 policy/approval contracts: the **policy verdict** (allow /
  deny-with-reason) and **decider** interface the Tool Gateway consults, the **permission-rule engine**
  (rules with allow/deny effects and user/project/session-local precedence), and the **tool-call** (call id /
  tool name / input arguments) and **tool-descriptor** (declared capabilities) models, plus the run context
  and event channel the decider signature carries. These exist and are stable (unit 001 is Verified).
- **Policies are deciders, not executors.** The host wires a policy into the gateway's decide seam; the
  gateway calls it before executing a tool and obeys the verdict. This layer never runs a tool.
- **Default-deny is the safe posture**: a no-match, a malformed input, an empty combinator, or a raising
  policy yields **deny**.
- **Path containment is pure normalization** (lexical `..`/absolute-escape analysis, no filesystem access),
  so it is deterministic and platform-stable for the host-supplied root and argument.
- **Budget/quota state is in-process** per decider instance for the duration of a run; persistent
  cross-restart state is a reserved extension point.
- **Cost weights are host-supplied** deterministic numbers; the layer bundles no real cost data.
- This layer is **distinct from the Phase-1 Human Approval boundary** (which owns interactive approval) and
  from actual OS-level sandboxing (reserved).

## Out of Scope

- Executing, resolving, or OS-sandboxing tools (the Tool Gateway owns execution — Constitution V).
- Re-implementing the permission-rule engine, tool execution, sizing, timeout, or error normalization.
- Human-approval interaction orchestration (the Phase-1 Human Approval boundary owns it).
- Any network, remote, or filesystem-based policy loading; remote rule fetch; cloud deployment; web or UI.
- Any non-deterministic decision; persistent cross-restart budget/quota state; ML/model-based cost.
