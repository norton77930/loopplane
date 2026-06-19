# Phase 1 Data Model: Declarative permission rule DSL

This feature introduces no persisted entities. It adds two in-memory rule shapes + a
decide-stage policy + one additive `RuntimeConfig` field. The "model" here is those shapes
plus the matching/precedence rules.

## New types (`src/loopplane/governance/rule_dsl.py`)

### `PermissionRuleSpec` (the declarative rule)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `tool` | `str` | (required) | An exact tool name or an `fnmatch` pattern (the existing matcher syntax, e.g. `mcp:*`) tested against `call.tool_name`. |
| `match` | `Mapping[str, str] \| None` | `None` | An optional map of input-field name → pattern. A **path-shaped** field name (`path`, `file`, or `*_path`) → a **path-glob**; any other field → a **regex**. Every entry must match (AND) for the rule to match. |
| `decision` | `"allow" \| "deny" \| "ask"` | (required) | The decision when this rule matches. |

A frozen pydantic model (`BaseModel` + `ConfigDict(frozen=True)`, matching `PermissionRule`).
Public-safe (no secret).

### `PermissionRuleSet` (the host-suppliable bundle)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `rules` | `tuple[PermissionRuleSpec, ...]` | `()` | The ordered rule set (order does not affect precedence — see below). |
| `default` | `"allow" \| "deny" \| "ask"` | `"allow"` | The decision when **no** rule matches. Default `"allow"` so an empty set is a no-op. |

A frozen pydantic model. Carried on `RuntimeConfig.permission_rules`.

### `RuntimeConfig.permission_rules` (additive field — `src/loopplane/host/config.py`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `permission_rules` | `PermissionRuleSet \| None` | `None` | The host-suppliable rule set. `None` (the default) → **no DSL policy installed**; existing behaviour unchanged. Carries **no secret**. Coerced in `from_mapping`. |

All existing `RuntimeConfig` fields are unchanged.

## Policy: `rule_dsl_policy` (decide-stage — `src/loopplane/governance/rule_dsl.py`)

```python
def rule_dsl_policy(rules: PermissionRuleSet) -> PolicyDecider: ...
```

- **Construction** (eager / fail-closed): for each rule, each `match` entry is compiled —
  a path-shaped field via `fnmatch.translate(...)` → `re.compile`, any other field via
  `re.compile`. A **malformed** pattern raises (a clear config error) at this point — never
  a silent allow at decide time (FR-005). `decision` / `default` values are validated by the
  pydantic `Literal` at model construction.
- **Decide** (per call): compute the matching rules, then the combined decision; map to a
  verdict.

### Matching a rule against a call

A `PermissionRuleSpec` **matches** a `ToolCallRequest` iff **both**:

1. `fnmatch.fnmatchcase(call.tool_name, rule.tool)` — the tool matcher (gates first), AND
2. for **every** `(field, compiled_pattern)` in `match`: `field in call.input` **and** the
   field's **string form** satisfies the pattern (a path-shaped field's value is normalized
   to forward slashes before the glob test; a regex field uses `pattern.search(str(value))`).

A `match` naming an **absent** field → the rule does **not** match (so a `deny` gates a
*specific present invocation*, not a call lacking the field).

### Combined decision (precedence) + verdict

| Among the matching rules… | Combined decision |
|---------------------------|-------------------|
| any `deny` | **deny** |
| else any `ask` | **ask** |
| else any `allow` | **allow** |
| no rule matches | the set's **`default`** |

→ **deny > ask > allow** (the most-restrictive matching decision wins; reduces to
`resolve_rules`' deny-wins when all matching rules are name-only allow/deny). Then:

| Combined decision | Verdict |
|-------------------|---------|
| `allow` | `PolicyAllow()` |
| `deny` | `PolicyDeny(reason="…denied by permission rule…")` (public-safe) |
| `ask` | **reuse the approval round-trip**: `resolution = await context.interactions.request_approval(call_id=…, tool_name=…, input_summary=…)`; `allow` → `PolicyAllow()`, else `PolicyDeny(reason=resolution.reason or "…")`; **no broker / no reviewer** → `PolicyDeny("no reviewer available to approve …")` |

Decided from the call + descriptor (+ the per-run `RunContext` for `ask`) only; **no tool
invocation**. Composed in `_build_decider` as one more decider inside the existing
`safe_failure(all_of(<approval?>, network_policy, <plan_mode?>, rule_dsl_policy(...)))`:
**deny-wins** (any deny short-circuits) and **fail-closed** (a raised policy → deny).

## Output / verdict shapes (`PolicyVerdict` — unchanged union)

- **allow** → `PolicyAllow()` (the existing empty allow verdict).
- **deny** → `PolicyDeny(reason=…)` (the existing deny-with-reason; reason is public-safe —
  the tool name + "denied by permission rule", never a secret).
- **ask** → after the existing approval round-trip, **one of** the above (never a new type).

No new verdict type is introduced (FR-003).

## Wiring (decision flow)

```text
RuntimeConfig.permission_rules = PermissionRuleSet(rules=[...], default="allow")
        │  (host/assembly.py::_build_decider — when rules present)
        ▼
deciders.append(rule_dsl_policy(config.permission_rules))   # eager compile here
        │
        ▼
safe_failure(all_of(<approval?>, network_policy, <plan_mode?>, rule_dsl_policy(...)))
        │  gateway.decide(call, descriptor, context, emitter)
        ▼
rule_dsl_policy: select matching rules → deny>ask>allow → default
   allow → PolicyAllow ; deny → PolicyDeny ; ask → context.interactions.request_approval → map
```

## Validation rules (from requirements)

- FR-001: a rule = `tool` (exact/`fnmatch`) + optional `match` (regex / path-glob) + `decision`; a top-level `default`.
- FR-002: select rules whose tool matcher AND every `match` match; combine deny>ask>allow; fall back to `default`.
- FR-003: return the existing `PolicyVerdict`; `ask` reuses `request_approval`; no new verdict/approval mechanism.
- FR-004: composed through `all_of` + `safe_failure`; no new gateway stage.
- FR-005: invalid regex / decision / default → a clear config error at construction (eager); never a silent allow.
- FR-006: `RuntimeConfig.permission_rules` default `None`; coerced in `from_mapping`; absent → unchanged.
- FR-007: public-safe — tool names + patterns + decisions only; no secret.
- FR-008/FR-009: additive; enforcement at the decide stage only; no loop/gateway/event/approval change.
