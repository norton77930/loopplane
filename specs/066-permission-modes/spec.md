# Feature Specification: Named Permission Modes

**Feature Branch**: `066-permission-modes`

**Created**: 2026-06-21

**Status**: Draft — P1 (review backlog batch 064–072, unit 3/9)

**Input**: User description: "P1 (gap G10): named convenience permission modes (acceptEdits / bypassPermissions / dontAsk / plan) as preset PermissionRuleSets composed over the 039 DSL — a RuntimeConfig selector. Additive; default = today's behaviour byte-identical (composes existing deciders, no new gateway stage). Touches loopplane.governance + host/config."

## ⚠️ Boundary note (read first)

039 gave a declarative permission rule DSL (`PermissionRuleSet`: `{tool, match, decision}` rules +
a default, decisions `allow`/`deny`/`ask`), and 038 a plan mode — but a host must hand-author rules
for common postures. This unit adds four NAMED convenience modes as PRESET `PermissionRuleSet`s built
from the EXISTING 039 DSL primitives, selectable by one `RuntimeConfig.permission_mode` field.
**Additive** — the preset is just a `PermissionRuleSet` fed through the SAME `rule_dsl_policy` decider
at the SAME decide stage; **no new gateway stage, no new decider kind, no new event/schema**. Default
`permission_mode=None` is **byte-identical** to today (no preset built). `plan` reuses the existing
038 plan mode. Public-safe; no ADR.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select a named mode instead of hand-authoring rules (Priority: P1)

A host sets `permission_mode="acceptEdits"` (or `bypassPermissions` / `dontAsk` / `plan`) and gets the
corresponding posture without writing a `PermissionRuleSet` by hand.

**Why this priority**: G10 parity — the common postures (auto-accept edits, bypass prompts, never
ask, plan-first) are ergonomic presets; today they require bespoke rules.

**Independent Test** (offline, the decider + a scripted tool call): with `permission_mode=
"acceptEdits"`, a file-edit tool is allowed without a prompt while other tools follow the base posture;
`bypassPermissions` allows all; `dontAsk` resolves an otherwise-`ask` decision without prompting;
`plan` behaves as 038 plan mode; `None` is byte-identical to today.

**Acceptance Scenarios**:

1. **Given** `permission_mode="acceptEdits"`, **When** the agent calls a file-edit tool, **Then** it
   is allowed without an approval prompt; other tools follow the base default.
2. **Given** `permission_mode="bypassPermissions"`, **When** the agent calls any tool, **Then** it is
   allowed (the most permissive preset — a clear opt-in).
3. **Given** `permission_mode="dontAsk"`, **When** a decision would be `ask`, **Then** it is
   auto-resolved (no interactive prompt) per the mode's defined fallback.
4. **Given** `permission_mode="plan"`, **When** the agent runs, **Then** it behaves as the existing
   038 plan mode (read-only until approved).

---

### User Story 2 - Default-off byte-identical (Priority: P1)

With no `permission_mode` configured, behavior is exactly today (no preset, the existing
`permission_rules`/`plan_mode`/deciders unchanged).

**Why this priority**: The convenience must impose nothing on existing deployments.

**Independent Test**: `permission_mode=None` → no preset `PermissionRuleSet` is built; the decider
composition + events are byte-identical to today.

**Acceptance Scenarios**:

1. **Given** no `permission_mode`, **When** runs execute, **Then** behavior + the decider composition
   are byte-identical to today.
2. **Given** both `permission_mode` and explicit `permission_rules` are set, **When** assembled,
   **Then** a defined, documented precedence applies (no silent surprise; see Assumptions).

---

### Edge Cases

- **`None` (default)**: byte-identical; no preset built.
- **mode + explicit `permission_rules`**: a documented precedence (explicit rules win, or the mode is
  rejected as ambiguous — resolved at plan; never a silent merge).
- **invalid mode string**: a clean `ConfigError` at config validation (not a runtime crash).
- **`bypassPermissions`**: the most permissive — a deliberate, clearly-named opt-in (the spec/docs
  flag it as bypassing prompts); it does NOT disable the Gateway, only the permission decider posture.
- **`dontAsk`**: suppresses interactive prompts by resolving `ask`→ the mode's fallback (no prompt);
  the rest of the posture unchanged.
- **public-safety**: modes carry no secrets; the preset is plain rules.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add named permission-mode presets (`acceptEdits`, `bypassPermissions`, `dontAsk`,
  `plan`) built from the EXISTING 039 `PermissionRuleSet`/DSL primitives — each preset is a plain
  `PermissionRuleSet` (or, for `plan`, the existing 038 plan mode). No new decider kind / gateway
  stage.
- **FR-002**: Add a `RuntimeConfig.permission_mode` selector (a `str | None`, validated to the known
  modes); when set, assembly builds the corresponding preset + feeds it through the SAME
  `rule_dsl_policy` decider at the SAME decide stage (or sets `plan_mode` for `plan`).
- **FR-003**: Define each mode's semantics precisely: `acceptEdits` = auto-allow the file-edit/write
  tools, others follow the base default; `bypassPermissions` = allow all; `dontAsk` = resolve an
  otherwise-`ask` decision without an interactive prompt (the fallback documented); `plan` = the 038
  plan mode.
- **FR-004**: **Default-off byte-identical** — `permission_mode=None` builds no preset; the existing
  `permission_rules`/`plan_mode`/decider composition + events are unchanged.
- **FR-005**: Define a precedence when both `permission_mode` and explicit `permission_rules` are set
  (documented; never a silent merge). Invalid mode → a clean `ConfigError` at validation.
- **FR-006**: No new gateway stage / decider kind / Event-Bus / `SCHEMA_VERSION` / dependency change;
  no ADR. Public-safe.

### Key Entities *(include if feature involves data)*

- **PermissionMode**: a named preset (`acceptEdits`/`bypassPermissions`/`dontAsk`/`plan`) → a
  `PermissionRuleSet` (or plan mode).
- **RuntimeConfig.permission_mode**: `str | None = None` (the selector).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the four modes produces its defined posture via the existing decider; verified
  by scripted tool calls — 100% of covered cases.
- **SC-002**: `permission_mode=None` is byte-identical to today (the existing decider/permission
  suite passes); an invalid mode → `ConfigError`.
- **SC-003**: No new gateway stage / decider kind / schema bump / dependency; composes the existing
  039 DSL; the four gates + structural audits + the existing governance suite pass.

## Assumptions

- Reuses 039's `PermissionRuleSet`/`PermissionRuleSpec`/`rule_dsl_policy` + 038's plan mode + the
  config coercion/validation seam (`RuntimeConfig` + `validate_config`).
- **Precedence (proposed, finalized at plan)**: `permission_mode` is a convenience shorthand; if BOTH
  `permission_mode` and explicit `permission_rules` are set, the explicit `permission_rules` take
  precedence (the mode is a base) OR config validation rejects the combination — the plan picks the
  least-surprising rule and documents it.
- **Out of scope**: arbitrary user-defined named modes; per-tool granular mode overrides beyond the
  presets; changing the 039 DSL semantics; a frontend mode switcher; runtime mode switching
  mid-session (a mode is set at config/assembly time).
- Additive; default-off byte-identical; composes existing deciders; public-safe; offline-testable. No
  ADR (a config-level convenience over the established 039 governance seam).
