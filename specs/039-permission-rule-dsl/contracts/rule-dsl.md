# Contracts: Declarative permission rule DSL (policy + rule shapes + config)

The "interface" this unit exposes is: two declarative rule shapes (`PermissionRuleSpec`,
`PermissionRuleSet`); a decide-stage `rule_dsl_policy` decider composed through the existing
combinators; and an additive `RuntimeConfig.permission_rules` field. All enforcement is at
the Tool Gateway decide stage (Constitution V); the decider returns the **existing**
`PolicyVerdict` union and reuses the **existing** approval round-trip for `ask` — it
introduces no new verdict type and no new approval mechanism.

## `PermissionRuleSpec` + `PermissionRuleSet` (the declarative rules)

```python
class PermissionRuleSpec(BaseModel):          # frozen
    tool: str                                  # exact name or fnmatch pattern (e.g. "mcp:*")
    match: Mapping[str, str] | None = None     # field -> regex (or path-glob for path-shaped fields)
    decision: Literal["allow", "deny", "ask"]

class PermissionRuleSet(BaseModel):           # frozen
    rules: tuple[PermissionRuleSpec, ...] = ()
    default: Literal["allow", "deny", "ask"] = "allow"
```

- `tool` reuses the existing `fnmatch` matcher syntax (as `PermissionRule.matcher` /
  `resolve_rules`), so `mcp:*` matches `mcp:server:tool`.
- `match` is an **AND** of per-field patterns. A field name that is **path-shaped** (`path`,
  `file`, or ending in `_path`) is a **path-glob** (`**`/`*`/`?`); any other field is a
  **regex** (`re.search`). A `match` naming a field **absent** from the call → the rule does
  **not** match.
- Public-safe: only tool names + patterns + decisions; never a secret (VII).

## `rule_dsl_policy` (decide-stage decider)

```python
def rule_dsl_policy(rules: PermissionRuleSet) -> PolicyDecider: ...
```

- **Construction is eager / fail-closed**: every `match` pattern (regex or path-glob) is
  compiled at construction; a malformed pattern raises a clear error there (never compiled
  lazily into a silent decide-time allow). `decision` / `default` are validated by the
  pydantic `Literal`s.
- **Decide** (`(call, descriptor, context, emitter) -> PolicyVerdict`):

| Among the matching rules (tool matcher AND every `match`) | Combined → Verdict |
|----------------------------------------------------------|--------------------|
| any matching rule is `deny` | **deny** → `PolicyDeny(reason)` |
| else any matching rule is `ask` | **ask** → reuse `request_approval`; approve → `PolicyAllow`, reject / no-reviewer → `PolicyDeny` |
| else any matching rule is `allow` | **allow** → `PolicyAllow` |
| no rule matches | the set's **`default`** (mapped the same way) |

- Precedence is **deny > ask > allow** (the most-restrictive matching decision wins;
  reduces to `resolve_rules`' deny-wins when matching rules are name-only allow/deny).
- Decides from the call + descriptor (+ the per-run `RunContext` for `ask`) only — **never
  invokes a tool**.
- **`ask` reuses the existing round-trip**: `await
  context.interactions.request_approval(call_id=call.call_id, tool_name=call.tool_name,
  input_summary=…)`; map `ApprovalResolution.decision` → allow/deny. With no broker / no
  reviewer attached → `PolicyDeny` (the existing `request_approval` / disconnect semantics:
  never a hang, never a silent allow). Emits the **existing** `approval-requested` /
  `approval-resolved` events (no new event).
- **Composition** (`host/assembly.py::_build_decider`): one more decider in
  `safe_failure(all_of(<approval?>, network_policy, <plan_mode?>, rule_dsl_policy()))` →
  **deny-wins** + **fail-closed**. Installed only when `RuntimeConfig.permission_rules` is
  present with ≥1 rule (or another policy is already present); a config with no rules keeps
  today's posture.

## `RuntimeConfig.permission_rules` (host opt-in)

```python
permission_rules: PermissionRuleSet | None = None
```

- Additive, public-safe field (**no secret**). Present with ≥1 rule → `rule_dsl_policy` is
  composed into the decide stage. Default `None` → existing runs unchanged (no DSL policy
  installed). Coerced in `RuntimeConfig.from_mapping` from a `PermissionRuleSet` or a mapping:

```python
{
  "permission_rules": {
    "rules": [
      {"tool": "run_command", "match": {"command": "^rm -rf"}, "decision": "deny"},
      {"tool": "write_file", "match": {"path": "**/secrets/**"}, "decision": "deny"},
      {"tool": "read_file", "decision": "allow"},
      {"tool": "mcp:*", "decision": "ask"},
    ],
    "default": "allow",
  }
}
```

## Invariants (all)

- All enforcement is at the Tool Gateway **decide stage** (Constitution V); the rule DSL is
  a policy, never a bypass; the policy never resolves or executes a tool.
- The decider returns only the **existing** `PolicyVerdict` union (`PolicyAllow` /
  `PolicyDeny`); `ask` is realized by the **existing** `request_approval` round-trip — no new
  verdict type, no new approval mechanism (FR-003).
- An invalid regex / path-glob (or an invalid decision/default) is a **construction-time**
  config error (fail-closed), never a silent decide-time allow (FR-005).
- **No event-schema change** (VI): `ask` reuses the existing approval events; no
  `SCHEMA_VERSION` bump, no new event type.
- The rules are **public-safe** (tool names + patterns + decisions only; no secret) (VII).
- Permission rules **absent / empty** is a provable no-op: an empty set with `default="allow"`
  decides identically to no policy, and every existing tool, descriptor, policy, and the
  approval boundary are unchanged (back-compat).
