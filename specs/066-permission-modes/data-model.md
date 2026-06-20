# Data Model: Named Permission Modes

Additive config convenience over the 039 DSL. No event/content/schema change. P1 (no ADR).

## New: the mode builder (in `loopplane.governance`)

| Entity | Shape | Notes |
| ------ | ----- | ----- |
| `PERMISSION_MODES` | the known mode names: `acceptEdits`, `bypassPermissions`, `dontAsk`, `plan` | for validation. |
| `permission_mode_ruleset(mode, explicit_rules) -> PermissionRuleSet \| None` | builds the effective ruleset for a mode (None for `plan`, which sets plan_mode instead) | reuses `PermissionRuleSet`/`PermissionRuleSpec`. |

## Mode semantics

| Mode | Effective `PermissionRuleSet` | plan_mode |
| ---- | ----------------------------- | --------- |
| `acceptEdits` | `rules=(allow write_file/edit_file/notebook_edit[/undo_file]), default="ask"` | unchanged |
| `bypassPermissions` | `rules=(), default="allow"` (ignores explicit rules) | unchanged |
| `dontAsk` | the explicit rules (or empty default-allow) with every `ask` → `allow` | unchanged |
| `plan` | (none — reuses the existing decider) | `True` (038) |
| `None` (default) | (none built — byte-identical) | unchanged |

## RuntimeConfig (modified — additive)

| Surface | Type | Notes |
| ------- | ---- | ----- |
| `RuntimeConfig.permission_mode` | `str \| None = None` | the selector; `from_mapping` coerces; `validate_config` checks the known modes + the precedence. |
| assembly | derives the effective `PermissionRuleSet` / `plan_mode` from the mode and feeds the SAME `rule_dsl_policy` wiring | no new decider/stage. |

## Precedence (validate_config)

| Combination | Result |
| ----------- | ------ |
| `permission_mode=None` | no preset; byte-identical |
| `acceptEdits`/`bypassPermissions` + explicit `permission_rules` | `ConfigError` (ambiguous) |
| `dontAsk` + explicit `permission_rules` | compose (the ask→allow transform of the explicit rules) |
| `plan` + explicit `permission_rules` | compose (plan is orthogonal; rules apply within plan) |
| unknown mode string | `ConfigError` |

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| named presets from the 039 DSL; no new decider/stage | FR-001 |
| RuntimeConfig.permission_mode selector; fed through rule_dsl_policy | FR-002 |
| each mode's exact semantics (acceptEdits/bypassPermissions/dontAsk/plan) | FR-003 |
| default None byte-identical | FR-004 |
| documented precedence; invalid → ConfigError | FR-005 |
| no gateway/decider/event/schema/dependency change; public-safe; no ADR | FR-006 |
