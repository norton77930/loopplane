# Specification Quality Checklist: Named Permission Modes

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **P1, no ADR** — named presets built from the EXISTING 039 DSL, selected by one `RuntimeConfig`
  field; the preset is fed through the SAME `rule_dsl_policy` decider at the SAME decide stage. No new
  gateway stage / decider kind / event / schema.
- **Reuse-first**: 039 `PermissionRuleSet`/`rule_dsl_policy`; 038 plan mode; the config coercion +
  `validate_config` seam.
- **Two decisions for plan**: (1) each mode's EXACT preset (`acceptEdits` = which tool names count as
  edits; `dontAsk`'s ask-fallback = allow vs deny; `bypassPermissions` = default allow-all); (2) the
  precedence when both `permission_mode` and explicit `permission_rules` are set (explicit wins, or
  reject — pick the least-surprising + document).
- **Default-off byte-identity** (`permission_mode=None` → no preset) is the load-bearing invariant.
- **bypassPermissions** is the most permissive — flag it clearly; it changes only the permission
  decider posture, NOT the Gateway (tools still run through the Gateway).
- All items pass; ready for `/speckit-plan`.
