# Contract: Named Permission Modes

Named convenience permission modes as preset `PermissionRuleSet`s over the existing 039 DSL, selected
by `RuntimeConfig.permission_mode`. Additive; composes the existing `rule_dsl_policy` decider; no new
decider/gateway/schema. P1 (no ADR).

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `RuntimeConfig.permission_mode` | `str \| None = None` | one of acceptEdits/bypassPermissions/dontAsk/plan, or None. |
| `permission_mode_ruleset(mode, explicit_rules)` | → `PermissionRuleSet \| None` | the effective ruleset (None for plan). |
| `PERMISSION_MODES` | the known mode names | for validation/docs. |

## Behavior

| Case | Result |
| ---- | ------ |
| `acceptEdits` | file-edit tools (write_file/edit_file/notebook_edit…) allowed without a prompt; others follow `default="ask"`. |
| `bypassPermissions` | all tools allowed (allow-all; the named escape hatch); ignores explicit rules. |
| `dontAsk` | the host's explicit rules with every `ask` → `allow` (never prompts; keeps `deny`); standalone → allow-all. |
| `plan` | the 038 plan mode (read-only until approved); orthogonal to explicit rules. |
| `None` (default) | no preset built — byte-identical to today. |
| `acceptEdits`/`bypassPermissions` + explicit `permission_rules` | `ConfigError` (ambiguous). |
| unknown mode | `ConfigError` at validation. |

## Invariants

- A mode produces a `PermissionRuleSet` (data) consumed by the SAME 039 `rule_dsl_policy` decider at
  the SAME decide stage (or sets `plan_mode`) — NO new decider kind, NO new gateway stage, NO event/
  `SCHEMA_VERSION`/content change, NO new dependency.
- `permission_mode=None` is byte-identical to today (no preset built; the existing
  `permission_rules`/`plan_mode`/decider composition + events unchanged).
- `bypassPermissions` relaxes only the permission DECIDER posture — tools still run through the Tool
  Gateway (V); it is a clearly-named opt-in.
- Documented precedence (no silent merge); invalid mode → `ConfigError`.
- Public-safe (plain tool-name rules; no secrets). A new exported public name → `docs/api-reference.md`
  (bijection).
- Out of scope: custom modes; per-tool overrides; 039 DSL changes; runtime mode switching; a frontend
  switcher.
