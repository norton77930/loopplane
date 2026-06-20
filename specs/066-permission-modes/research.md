# Research: Named Permission Modes

P1 (no ADR). Named presets over the existing 039 DSL. No open `NEEDS CLARIFICATION`.

## Decision 1 — Presets are `PermissionRuleSet`s fed through the existing `rule_dsl_policy`

**Decision**: A mode produces a `PermissionRuleSet` (data); the SAME 039 `rule_dsl_policy` decider at
the SAME decide stage consumes it. `plan` sets `plan_mode` (038). No new decider kind / gateway stage.

**Rationale**: Reuses the proven governance seam; the mode is pure config-to-data; zero new runtime
surface.

**Alternatives**: a new "mode decider" (rejected — a new decider kind for what is a preset ruleset).

## Decision 2 — The four mode semantics

**Decision**:
- **acceptEdits** = `rules=(allow on the file-edit tools: write_file, edit_file, notebook_edit [+
  undo_file]), default="ask"`.
- **bypassPermissions** = `rules=(), default="allow"` (allow all; ignores explicit rules — the named
  escape hatch).
- **dontAsk** = the host's explicit `permission_rules` (or an empty `default=allow` set) with every
  `ask` rewritten to `allow` (a pure ruleset transform) — never prompts, keeps `deny`.
- **plan** = `plan_mode=True` (reuse 038).

**Rationale**: Matches the common postures (claude-code parity) while each is expressible in the 039
DSL; `dontAsk` is a genuine ask-suppressing transform (distinct from `bypassPermissions`, which is
unconditional allow-all).

**Alternatives**: making `dontAsk` identical to `bypassPermissions` standalone (rejected — the
transform gives it a distinct, composable meaning). The exact edit-tool name list is finalized at
implement (cross-check the registered tools).

## Decision 3 — Precedence + validation

**Decision**: In `validate_config`: `acceptEdits`/`bypassPermissions` + explicit `permission_rules` →
`ConfigError` (ambiguous); `dontAsk` composes with `permission_rules` (the transform); `plan` is
orthogonal (composes). Unknown mode → `ConfigError`. `None` → no preset (byte-identical).

**Rationale**: No silent merge surprises; the one composable mode (`dontAsk`) is the transform; the
standalone presets are mutually exclusive with hand-authored rules.

## Decision 4 — Default-off byte-identity

**Decision**: `permission_mode=None` builds no preset; the existing `permission_rules`/`plan_mode`/
decider composition + events are unchanged.

**Rationale**: Impose nothing on existing deployments.

## Out of scope

Custom/user-defined named modes; per-tool mode overrides; changing the 039 DSL semantics; runtime
mode switching mid-session; a frontend mode switcher. A new public name (the mode builder/constants)
is added to `docs/api-reference.md` (bijection) if exported.
