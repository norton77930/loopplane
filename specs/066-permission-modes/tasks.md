# Tasks: Named Permission Modes

**Feature**: 066-permission-modes | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive — four named permission-mode presets built from the EXISTING 039 `PermissionRuleSet`/
`rule_dsl_policy` DSL, selected by a `RuntimeConfig.permission_mode` field; the SAME decider consumes
the preset at the SAME decide stage. No ADR. Default `None` byte-identical. P1 (batch 064–072, 3/9).

**Tests**: requested.

## Phase 1: The mode builder (Foundational) 🎯

- [x] T001 In `src/loopplane/governance/rule_dsl.py` (or a new `governance/modes.py`): add
  `PERMISSION_MODES` (the known names: `acceptEdits`, `bypassPermissions`, `dontAsk`, `plan`) +
  `permission_mode_ruleset(mode: str, explicit_rules: PermissionRuleSet | None) -> PermissionRuleSet
  | None` returning the effective ruleset: `acceptEdits` = `rules=(allow on the registered file-edit
  tools — cross-check the actual names: write_file/edit_file/notebook_edit[/undo_file]),
  default="ask"`; `bypassPermissions` = `rules=(), default="allow"`; `dontAsk` = the explicit rules
  (or empty `default="allow"`) with every `ask` rewritten to `allow` (a pure transform; keeps `deny`);
  `plan` → `None` (the caller sets `plan_mode`). Reuse `PermissionRuleSet`/`PermissionRuleSpec`.
- [x] T002 Export the new public name(s) from `src/loopplane/governance/__init__.py` `__all__` (the
  builder + `PERMISSION_MODES`) and add them to `docs/api-reference.md` (the bijection).

## Phase 2: Config wiring (P1)

- [x] T003 In `src/loopplane/host/config.py`: add `RuntimeConfig.permission_mode: str | None = None`
  + `from_mapping` coercion. In `validate_config`: reject an unknown mode (`ConfigError`); reject
  `acceptEdits`/`bypassPermissions` combined with explicit `permission_rules` (`ConfigError` —
  ambiguous); `dontAsk`/`plan` may combine. In assembly (where `permission_rules`/`plan_mode` are
  consumed): when `permission_mode` is set, derive the effective `PermissionRuleSet` via
  `permission_mode_ruleset(mode, permission_rules)` and feed the SAME `rule_dsl_policy` wiring; for
  `plan`, set `plan_mode=True`. Default `None` → no preset (byte-identical).

## Phase 3: Tests (P1)

- [x] T004 Add `tests/<unit>/test_permission_modes.py` (offline; the decider + scripted
  `ToolCallRequest`s): (a) `acceptEdits` → a file-edit tool allowed, another tool follows `ask`;
  (b) `bypassPermissions` → all allowed; (c) `dontAsk` → an otherwise-`ask` decision → `allow`, a
  `deny` rule still denies; (d) `plan` → plan-mode behaviour (read-only until approved); (e)
  `permission_mode=None` → byte-identical (no preset); (f) `validate_config`: unknown mode →
  `ConfigError`, `acceptEdits` + explicit rules → `ConfigError`. Use benign placeholders.

## Phase 4: Gates

- [x] T005 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-off byte-identity). Confirm: the structural audits
  (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the events
  serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the api-reference bijection (the new public name) +
  the existing governance suite pass. Do NOT run the full pytest concurrently with a verify Workflow
  (MCP load flake).

## Dependencies

- T001 → T002 (export) + T003 (config uses the builder). T003 → T004. T005 last.

## Implementation strategy

- A small builder over the 039 DSL + a config selector/validation. May be done inline or via a fork;
  then the four gates + the structural audits + the events SCHEMA_VERSION/api-reference tests + a
  focused adversarial review (each mode's posture is correct; default-off byte-identity; the
  precedence/validation; composes the existing decider with no new stage; public-safety) before commit.
  Commit only on a clean review / GO; fix + re-verify FRESH otherwise.
- Additive; P1; no ADR.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-21) — 0 critical, 0 high, 2 low (informational). 100% requirement
coverage (FR-001..FR-006 and SC-001..003 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ data-model ↔ contract ↔ tasks agree (the
`permission_mode_ruleset` builder + `PERMISSION_MODES` over the existing 039 `PermissionRuleSet`/
`rule_dsl_policy`; the four mode semantics [acceptEdits/bypassPermissions/dontAsk/plan]; a
`RuntimeConfig.permission_mode` selector fed through the SAME decider at the SAME decide stage; the
documented precedence in `validate_config`; default `None` byte-identical). **Additive**: no new
decider kind / gateway stage / Event-Bus / `SCHEMA_VERSION` / dependency change; composes the existing
039 governance seam. No Constitution violation (I/III/IV/V/VI/VII/X). Low notes (informational): (1)
the `acceptEdits` edit-tool name list must be cross-checked against the ACTUAL registered tool names
(write_file/edit_file/notebook_edit[/undo_file]) at implement so the preset allows exactly the edit
tools. (2) the new exported governance public name (`permission_mode_ruleset`/`PERMISSION_MODES`) must
register in `docs/api-reference.md` (the bijection enumerates packages with `__all__`).
**Cleared for `/speckit-implement`.**
