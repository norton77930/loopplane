# Implementation Plan: Named Permission Modes

**Branch**: `066-permission-modes` (main-only autopilot) | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/066-permission-modes/spec.md`

**Boundary**: P1 (review-backlog batch 064–072, 3/9). Additive config convenience over 039; **no ADR**.

## Summary

Add four named permission-mode presets built from the EXISTING 039 `PermissionRuleSet`/`rule_dsl_policy`
DSL, selected by a single `RuntimeConfig.permission_mode` field. When set, assembly derives the
effective `PermissionRuleSet` (or sets `plan_mode`) and feeds it through the SAME `rule_dsl_policy`
decider at the SAME decide stage — **no new decider kind, no new gateway stage, no event/schema
change**. Default `permission_mode=None` builds no preset → **byte-identical** to today. Public-safe;
no ADR.

## Technical Context

**Language/Version**: Python 3.11+; pydantic models (the 039 DSL).

**Primary Dependencies**: none new — reuses 039 (`PermissionRuleSet`/`PermissionRuleSpec`/
`rule_dsl_policy`), 038 plan mode, the config coercion/validation seam.

**Storage**: none.

**Testing**: pytest, offline (the decider + scripted `ToolCallRequest`s): each mode yields its posture;
`None` byte-identical; invalid mode → `ConfigError`; precedence with explicit `permission_rules`.

**Target Platform**: cross-platform library.

**Constraints**: additive; default-off byte-identical; composes the existing 039 decider (no new
decider kind / gateway stage); documented precedence; public-safe; no schema/dependency change; no ADR.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-006. ✅
- **III. Governance ergonomics**: named presets over the existing rule DSL; no relaxation of the
  Gateway (tools still run through it); `bypassPermissions` is a clearly-named opt-in. ✅
- **IV. Boundary**: the mode is a config-level convenience; assembly derives a `PermissionRuleSet`
  (data) fed through the existing 039 decider; no controller/loop change. ✅
- **V. Tool Gateway**: the decider runs at the SAME decide stage; no bypass of the Gateway itself. ✅
- **VI. Event Bus**: no event/`SCHEMA_VERSION`/`TerminationReason`/content change. ✅
- **VII. Public-safe**: presets are plain tool-name rules; no secrets. ✅
- **X. Testable Evolution**: Additive; default-off byte-identical; reversible; offline-tested. ✅

**Result**: PASS — a config convenience composing the established 039 governance DSL; no ADR.
Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/066-permission-modes/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/permission-modes.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/governance/rule_dsl.py     # MODIFIED (or a new modes.py in governance): the named
                                         #   presets + a builder `permission_mode_ruleset(mode,
                                         #   base) -> PermissionRuleSet | None` (acceptEdits /
                                         #   bypassPermissions / dontAsk transform) + the mode names
src/loopplane/governance/__init__.py     # MODIFIED: export the mode names / builder (+ api-reference)
src/loopplane/host/config.py             # MODIFIED: RuntimeConfig.permission_mode: str | None = None
                                         #   + from_mapping + validate_config (known modes; the
                                         #   mode×permission_rules precedence); assembly derives the
                                         #   effective PermissionRuleSet / plan_mode from the mode
docs/api-reference.md                    # MODIFIED if a new public name is exported
tests/<permission-mode tests>            # NEW
```

**Structure Decision**: A small `permission_mode_ruleset(mode, explicit_rules)` builder in
`loopplane.governance` returns the effective `PermissionRuleSet` (or signals plan mode) for a mode;
`RuntimeConfig`/assembly call it so the SAME 039 wiring (`rule_dsl_policy`) consumes the result — no
new decider/stage. The mode semantics:
- **acceptEdits** → `PermissionRuleSet(rules=(allow write_file/edit_file/notebook_edit…), default=
  "ask")` — edits auto-allowed, everything else prompts.
- **bypassPermissions** → `PermissionRuleSet(rules=(), default="allow")` — allow all (the named
  escape hatch; ignores explicit rules).
- **dontAsk** → take the host's explicit `permission_rules` (or an empty default-`allow` set) and
  rewrite every `ask` decision (rules + default) to `allow` — a pure ruleset TRANSFORM (no new
  decider); never prompts, but keeps `deny` rules.
- **plan** → set `plan_mode=True` (reuse 038); orthogonal to `permission_rules`.

**Precedence** (validated in `validate_config`, documented): `acceptEdits` / `bypassPermissions` are
standalone presets — if explicit `permission_rules` are ALSO set, `ConfigError` (ambiguous, pick one);
`dontAsk` COMPOSES with explicit `permission_rules` (the transform); `plan` is orthogonal (composes
with rules). Default `None` → no preset, byte-identical. An unknown mode → `ConfigError`.

## Complexity Tracking

> Four named presets + a small builder over the existing 039 `PermissionRuleSet`/`rule_dsl_policy`,
> selected by one config field. Additive; default-off byte-identical; no new decider/gateway/schema/
> dependency/ADR. Not a Constitution violation.
