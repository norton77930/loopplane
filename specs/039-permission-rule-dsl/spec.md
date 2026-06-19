# Feature Specification: Declarative permission rule DSL (host-suppliable allow/deny/ask rules)

**Feature Branch**: `039-permission-rule-dsl` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "LoopPlane permission rule DSL. A host should be able to
express a declarative permission rule set — not only code-level policy objects — that the
Tool Gateway enforces at its decide stage. Each rule names a `tool` (an exact name or a
pattern like the existing matcher syntax, e.g. `mcp:*`), an optional `match` (a map of
input-field name → regex tested against the call's input, and/or a path-glob for
path-shaped fields), and a `decision` of `allow` | `deny` | `ask`; a top-level `default`
decision applies when no rule matches. A `rule_dsl_policy` decide-stage decider selects
the rules whose tool-matcher AND every `match` pattern match the call, combines them with
a clear, documented, SAFE precedence (deny-wins), falls back to `default`, and returns the
existing `PolicyVerdict` — reusing the existing rule/verdict machinery and the existing
approval round-trip for `ask` (no new approval mechanism, no new verdict type). It is
composed through the existing decide-stage combinators (`all_of` deny-wins +
`safe_failure` fail-closed) in the host's decider builder — no new gateway stage. An
invalid regex in a rule is a clear config error at construction (fail-closed), never a
silent allow. The rules are an additive, default-empty, public-safe `RuntimeConfig`
field; empty/absent rules are a no-op (existing runs byte-identical). Enforcement is at
the Gateway decide stage only (Constitution V); reuse the existing combinators — no new
gateway stage, no core agent-loop change, no event-schema change, no ADR."

## Overview

Both reference harnesses let a host express a **declarative permission rule set** — layered
allow/deny rules (claude-code) and a YAML/JSON permission DSL (orion) — so an operator can
say "deny `run_command` whose `command` starts with `rm -rf`", "allow `read_file`
anywhere", "ask before any `mcp:*` tool" without writing code. LoopPlane has the building
blocks — a single Tool Gateway decide stage (Constitution V), a `PermissionRule` +
`resolve_rules` precedence engine, an allow/deny `PolicyVerdict`, and a human approval
round-trip — but its permissions are only **code-level policy objects** today; a host
cannot supply a declarative rule set. This unit adds it, the LoopPlane-native way:
**additive, reuse-first, enforced only at the Gateway decide stage**.

This is a **Tier-2 governance unit**: it deepens the control plane's *governance*
expressiveness (a host-suppliable rule DSL) without adding a tool, a provider, or a new
runtime boundary.

The unit adds:

1. A declarative **rule** structure (host-suppliable, coerced from plain dicts in
   `RuntimeConfig.from_mapping`). Each rule carries a `tool` (an exact name or a pattern in
   the **existing matcher syntax** — `fnmatch`, e.g. `mcp:*`), an optional `match` (a map
   of **input-field name → regex** tested against `call.input[field]`, and/or a
   **path-glob** matcher for path-shaped fields), and a `decision` of `allow` | `deny` |
   `ask`. A top-level **`default`** decision applies when no rule matches.
2. A **`rule_dsl_policy` decide-stage decider**. For a call it selects the rules whose
   **`tool` matcher AND every `match` pattern** match the call (`call.tool_name` +
   `call.input` fields), combines them with a clear, documented, **SAFE** precedence
   (**deny-wins**, then **ask**, then **allow** — reusing `resolve_rules`' deny-wins
   semantics for the name dimension), and falls back to **`default`** on no match. It
   returns the **existing** `PolicyVerdict`: `allow` → `PolicyAllow`; `deny` →
   `PolicyDeny`; `ask` → it **reuses the existing approval round-trip** (the same
   `InteractionBroker.request_approval` the Human Approval boundary uses) and maps the
   human's resolution to `PolicyAllow` / `PolicyDeny`. It is composed through the
   **existing** decide-stage combinators (`all_of` deny-wins + `safe_failure` fail-closed)
   in the host's decider builder — **no new gateway stage** (Constitution V).
3. An additive, default-empty, public-safe **`RuntimeConfig.permission_rules`** field (a
   tuple of rules + a default decision, also coerced from a plain mapping). Leaving it at
   its default (empty) leaves every existing run **byte-identical** (no policy installed for
   that reason; existing behavior unchanged).

The change is **additive**: the core agent loop, the event bus / event schema, the gateway
pipeline, the approval boundary, and every existing tool are untouched (Constitution IV,
VI, X). There is **no ADR** — the rule DSL is a decide-stage *policy*, not a
runtime-boundary or event-schema change.

## Clarifications

### Verdict model (verified against the code; recorded in `research.md`)

The decide-stage verdict is **binary** — `PolicyVerdict = PolicyAllow | PolicyDeny`
(`src/loopplane/approval/decisions.py`). There is **no `PolicyAsk` verdict type**. "Ask"
is not a verdict; it is **behaviour inside a decider**: the Human Approval boundary's
`_escalate` calls `context.interactions.request_approval(...)` (the approval round-trip on
the `InteractionBroker`, emitting the existing `approval-requested` / `approval-resolved`
events) and maps the resulting `ApprovalResolution` to `PolicyAllow` / `PolicyDeny`; with
no reviewer attached it returns `PolicyDeny("no reviewer available")`. The DSL's
`decision: ask` therefore **reuses this exact path** — it requests approval and maps the
resolution — rather than introducing a new verdict or a new approval mechanism. This makes
`rule_dsl_policy` an **async, context-reading** decider (like `plan_mode_policy`), not a
context-free `as_decider` wrapper.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deny rule with an arg-regex denies a matching call, allows a non-matching one (Priority: P1)

A host supplies a rule `{tool: "run_command", match: {command: "^rm -rf"}, decision:
"deny"}`. A `run_command` call whose `command` matches the regex is **denied** at the
Gateway's decide stage with a normalized policy-denial; a `run_command` call whose
`command` does not match is **not** denied by this rule (it falls to `default`). The run
stays alive.

**Why this priority**: Argument-aware denial is the headline capability the DSL exists to
give — gating *specific dangerous invocations*, not whole tools; it must exist first.

**Independent Test**: Build `rule_dsl_policy` over the rule above with `default="allow"`;
decide `run_command(command="rm -rf /")` → deny; decide `run_command(command="ls")` →
allow (via the default).

**Acceptance Scenarios**:

1. **Given** a deny rule on `run_command` with `match: {command: "^rm -rf"}`, **When** `run_command(command="rm -rf /")` is decided, **Then** it is denied with a normalized policy-denial and the run continues.
2. **Given** the same rule, **When** `run_command(command="ls -la")` is decided, **Then** the rule does not match and the call falls to the `default` decision.
3. **Given** the same rule but a *different* tool (e.g. `read_file`), **When** it is decided, **Then** the rule does not match (the `tool` matcher gates first).

### User Story 2 - A path-glob deny rule denies a matching path, an allow rule allows a tool (Priority: P1)

A host supplies a path-shaped rule `{tool: "write_file", match: {path: "**/secrets/**"},
decision: "deny"}` and an `{tool: "read_file", decision: "allow"}` rule. A `write_file`
whose `path` glob-matches is **denied**; a `write_file` to a non-matching path falls to
`default`; a `read_file` is **allowed** by its rule.

**Why this priority**: Path-shaped matching (glob) is the second core matcher the DSL must
support (file tools dominate the baseline toolset); a plain `allow` rule proves the
allow path.

**Independent Test**: Decide `write_file(path="a/secrets/k.txt")` → deny; decide
`write_file(path="a/notes.txt")` → allow (default); decide `read_file(path="x")` → allow
(by its rule).

**Acceptance Scenarios**:

1. **Given** a deny rule on `write_file` with a path-glob `match: {path: "**/secrets/**"}`, **When** `write_file(path="app/secrets/key.pem")` is decided, **Then** it is denied.
2. **Given** the same rule, **When** `write_file(path="app/notes.md")` is decided, **Then** the rule does not match and the call falls to `default`.
3. **Given** an allow rule on `read_file`, **When** `read_file(path="anything")` is decided, **Then** it is allowed by the rule.

### User Story 3 - An `ask` rule yields the approval round-trip; deny-wins on conflict; default applies on no match (Priority: P2)

An `ask` rule submits the call for a human approve/reject through the **existing** approval
round-trip and returns the human's decision; when rules conflict, **deny wins**; when no
rule matches, the **`default`** decision applies.

**Why this priority**: The `ask` decision and the precedence/default behaviour complete the
DSL's decision surface; they build on the matching from US1/US2.

**Independent Test**: With a scripted broker, an `ask` rule on `echo` resolves `allow` →
`PolicyAllow` and `deny` → `PolicyDeny`, and with no reviewer attached → `PolicyDeny`. A
conflicting `allow` + `deny` on the same tool → deny. No rule matches → `default`.

**Acceptance Scenarios**:

1. **Given** an `ask` rule on a tool and an attached human who approves, **When** the call is decided, **Then** the verdict is `PolicyAllow` (via the existing approval round-trip).
2. **Given** an `ask` rule and an attached human who rejects (or no human attached), **When** the call is decided, **Then** the verdict is `PolicyDeny`.
3. **Given** an `allow` rule and a `deny` rule that both match a call, **When** it is decided, **Then** the verdict is deny (deny-wins).
4. **Given** rules that match no call, **When** a call is decided, **Then** the `default` decision applies (default `allow`).

### User Story 4 - An invalid regex is a clear config error, not a silent allow (Priority: P1)

A rule whose `match` regex (or whose `tool`/`path` pattern) is malformed is a **clear
config error surfaced at construction** (fail-closed), never compiled lazily into a silent
allow at decide time.

**Why this priority**: Failing safe on bad configuration is a hard governance guarantee — a
typo'd deny regex must never silently permit the call it was meant to block.

**Independent Test**: Building `rule_dsl_policy` over a rule with `match: {command:
"["}` (an invalid regex) raises a clear error; no decider that silently allows is produced.

**Acceptance Scenarios**:

1. **Given** a rule with an invalid `match` regex, **When** the policy is constructed, **Then** a clear error is raised (the regex is compiled eagerly at construction).
2. **Given** a policy whose composed chain raises at decide time, **When** a call is decided, **Then** the verdict is deny (fail-closed via `safe_failure`), never a silent allow.

### User Story 5 - Empty / absent rules are a no-op (existing behaviour unchanged) (Priority: P1)

A run that supplies no permission rules behaves exactly as before: an empty DSL decides
identically to no policy. The default is empty.

**Why this priority**: Additive-and-default-empty is a hard constraint (Constitution X); an
existing run must be unaffected.

**Independent Test**: An empty `rule_dsl_policy` (no rules, `default="allow"`) composed
with another decider equals that decider alone for any call. A `RuntimeConfig` without
`permission_rules` builds the same decider it builds today.

**Acceptance Scenarios**:

1. **Given** no permission rules (`default="allow"`), **When** any call is decided, **Then** the DSL allows it (no-op).
2. **Given** a `RuntimeConfig` with `permission_rules` unset and no other policy, **When** the decider is built, **Then** it is the same allow-all posture as today (no decider installed for the DSL).

### Edge Cases

- **Tool matcher gates first** — a rule whose `tool` pattern does not match the call is never considered, regardless of its `match`.
- **A `match` field absent from the call's input** → the rule does not match (a `match` requires the field to be present *and* to satisfy the pattern), so a `deny` rule never matches a call that lacks the field — it falls through to other rules / `default` (deny gates a *specific* invocation, not the tool generally).
- **A non-string input field** under a regex `match` → coerced to its string form for the regex test (the call input is raw `dict[str, object]`); a path-glob `match` likewise tests the string form.
- **Multiple rules match** → combined by precedence **deny > ask > allow**; `deny` short-circuits the whole composed chain via `all_of`.
- **`ask` with no reviewer attached / a disconnect mid-decision** → resolves as **deny** (the existing `request_approval` semantics: a disconnect denies the pending request), never a hang, never a silent allow.
- **Invalid `default`** (not one of allow/deny/ask) → a clear config error at construction.
- **An `ask` default** (`default: "ask"`) → a call matching no rule is escalated through the approval round-trip (and denies with no reviewer).
- **Empty rule list** → the policy is a pure pass-through to `default` (and a `default="allow"` no-op equals no policy).
- **Public-safe** — a rule carries only a tool name + patterns + a decision; it never carries a secret (a credential lives in the host-supplied model/provider, never in a rule).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A declarative **rule** MUST carry a `tool` (an exact name or a pattern in the existing matcher syntax — `fnmatch`, e.g. `mcp:*`), an optional `match` (a map of input-field name → regex tested against `call.input[field]`, and/or a path-glob for path-shaped fields), and a `decision` of `allow` | `deny` | `ask`; a top-level **`default`** decision (one of allow/deny/ask) MUST apply when no rule matches.
- **FR-002**: A `rule_dsl_policy` decide-stage decider MUST select the rules whose **`tool` matcher AND every `match` pattern** match the call (`call.tool_name` + the string form of `call.input` fields), combine them with a documented **SAFE** precedence (**deny-wins**, then ask, then allow — reusing `resolve_rules`' deny-wins for the name dimension), and fall back to the **`default`** decision when no rule matches.
- **FR-003**: The decider MUST return the **existing** `PolicyVerdict`: `allow` → `PolicyAllow`; `deny` → `PolicyDeny` (with a public-safe reason); `ask` → it MUST **reuse the existing approval round-trip** (`context.interactions.request_approval`, the same path the Human Approval boundary uses) and map the human's `ApprovalResolution` to `PolicyAllow` / `PolicyDeny`. It MUST NOT introduce a new verdict type or a new approval mechanism.
- **FR-004**: The `rule_dsl_policy` decider MUST be composed into the Gateway's decide stage through the **existing combinators** (`all_of` deny-wins + `safe_failure` fail-closed) in the host's decider builder — **no new gateway stage** is added (Constitution V).
- **FR-005**: An **invalid regex** in a rule's `match` (or a malformed `tool`/path pattern), or an **invalid `decision`/`default`** value, MUST be a clear config error surfaced **at construction** (eager compilation / validation; fail-closed) — never a silently-allowed call at decide time.
- **FR-006**: The rules MUST be an additive, default-empty, public-safe **`RuntimeConfig.permission_rules`** field (a structure carrying the rule list + the default decision), also coerced from a plain mapping in `RuntimeConfig.from_mapping`. Leaving it unset MUST leave existing runs unchanged (no DSL policy installed for that reason).
- **FR-007**: The DSL MUST be **public-safe**: a rule carries only a tool name, patterns, and a decision; it MUST NOT carry a secret, a credential, or a private path (Constitution VII).
- **FR-008**: The unit MUST be **additive only** — no change to the core agent loop, the gateway pipeline, the event bus, the event schema, the approval boundary, or any existing tool's behaviour or descriptor flags (Constitution IV, VI, X).
- **FR-009**: All enforcement MUST happen at the Gateway **decide stage** (Constitution V); the rule DSL is a *policy*, never a bypass, and the decider never resolves or executes a tool itself.
- **FR-010**: All new behaviour MUST be covered by **deterministic, offline** unit tests (the governance helpers; a scripted `InteractionBroker` for the `ask` round-trip). The four quality gates MUST stay green.

### Key Entities

- **`PermissionRuleSpec`** (the declarative rule): `tool` (str — exact or `fnmatch` pattern), `match` (an optional map of field → regex / path-glob), `decision` (`allow` | `deny` | `ask`). Reuses the existing `fnmatch` matcher semantics for the `tool` dimension. Public-safe (no secret).
- **`PermissionRuleSet`** (the host-suppliable bundle): an ordered `rules` collection + a `default` decision (`allow` | `deny` | `ask`, default `allow`). Carried on `RuntimeConfig.permission_rules`.
- **`rule_dsl_policy` decider**: a decide-stage policy that selects matching rules (tool matcher AND every `match`), combines deny-wins → ask → allow, falls back to `default`, and returns the existing `PolicyVerdict` (reusing the approval round-trip for `ask`). Composed deny-wins + fail-closed through the existing combinators. Decides from the call + descriptor + (for `ask`) the per-run `RunContext`; never invokes a tool.
- **`RuntimeConfig.permission_rules`**: an additive, public-safe field (default empty/`None`) carrying the rule set; coerced in `from_mapping`.

### Out of Scope

- A configuration-file format (YAML/JSON on disk): the rules are an in-memory `RuntimeConfig` field coerced from a plain mapping, like every other config field this phase (no file is read).
- Per-rule **scope** layering (user / project / session-local) as a host-suppliable dimension: the existing `PermissionRule.scope` precedence is reused conceptually (deny-wins), but the DSL's host-facing rule is flat (scope is not a config field this unit). Richer scope layering is reserved.
- Matching on anything beyond `call.tool_name` + the string form of `call.input` fields (e.g. matching on the descriptor's flags, the run context, or environment): the matcher is call-shaped only.
- A frontend affordance for editing rules in the web UI — the runtime seam ships here; a UI is a later unit.
- A new verdict type, a new approval event, or any change to the approval/interaction boundary (the DSL reuses the existing round-trip and verdict union).
- Mutating, rate-limiting, or transforming a call (the DSL only decides allow/deny/ask; it never rewrites a call's input).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deny rule with an arg-regex denies a matching call (`run_command` whose `command` matches `^rm -rf`) and does **not** deny a non-matching one (it falls to `default`); a path-glob deny rule denies a matching `path` and an allow rule allows its tool — all at the Gateway decide stage with a normalized verdict, and the run continues.
- **SC-002**: An `ask` rule yields the approval round-trip — approve → `PolicyAllow`, reject / no-human → `PolicyDeny` — reusing the existing path with no new verdict or event; deny-wins when rules conflict; the `default` applies on no match.
- **SC-003**: An invalid regex (or decision/default value) is a clear config error at construction (fail-closed), never a silent allow; a raising composed chain still denies (fail-closed).
- **SC-004**: With no permission rules (the default), the DSL policy is provably a no-op (an empty DSL with `default="allow"` decides identically to no policy), and a `RuntimeConfig` without `permission_rules` builds the same decider as today.
- **SC-005**: The change is additive — the core agent loop, the gateway pipeline, the event bus, the event schema, the approval boundary, and every existing tool and descriptor are unchanged; the four quality gates (ruff, ruff format, mypy, pytest) stay green with new deterministic offline tests.

## Assumptions

- **Reuse the verdict + rule + approval machinery**: the DSL reuses the binary `PolicyVerdict` (`PolicyAllow` / `PolicyDeny`), the existing `fnmatch` matcher semantics (as in `PermissionRule.matcher` / `resolve_rules`), and the existing approval round-trip (`InteractionBroker.request_approval`) for `ask` — no new verdict, matcher engine, or approval mechanism (verified against the code; see `research.md`).
- **Deny-wins is the house posture**: the policy combines matching rules deny-wins and composes deny-wins (`all_of`) + fail-closed (`safe_failure`), mirroring `network_policy` / `plan_mode_policy`.
- **Eager compilation fails safe**: regexes (and decision/default values) are validated/compiled at construction, so a malformed rule fails the host's config wiring rather than silently allowing a call at decide time.
- **Additive and reversible**: removing `rule_dsl_policy`, the `RuntimeConfig.permission_rules` field + its coercion, and the `_build_decider` composition leaves the baseline tool set, the gateway, the loop, the approval boundary, and every component untouched (Constitution X rollback).
- **No ADR**: the rule DSL touches neither the Tool Gateway *execution* path (it is a decide-stage policy, V) nor the Event Bus / schema (it reuses the existing approval events, VI); it does not blur a runtime boundary (IV), so it needs no ADR.
