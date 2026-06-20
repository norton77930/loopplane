# Specification Quality Checklist: Per-Principal Host Pool

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-20
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

- **Plan FORK (maintainer consult) + an ADR**: at the plan step STOP and ask the maintainer —
  **pool-above-host** (recommended: a per-principal `LoopPlaneHost` pool ABOVE the host, each host
  keeping its sequential `_active` invariant; per-principal in-flight caps) vs **relax the `_active`
  gate** (allow concurrent runs on one host — risky; the host's per-run state was not built for
  concurrency). The plan authors the ADR after the decision.
- **Additive + default-off byte-identical**: with no pool configured the web/API host behaves exactly
  as today (a single shared host; the existing 409 on a concurrent run); the existing tests pass
  unchanged. The pool is opt-in.
- **Reuse-first**: reuses the existing `LoopPlaneHost` (per-principal instances via a host factory) +
  the webapi principal→session mapping; the pool layers ABOVE the host so the per-host sequential
  invariant + host internals are UNCHANGED.
- **Bounded + contained**: per-principal in-flight cap (+ optional max-principals bound); one
  principal's host failure isolated from others.
- **Deferred (the G20 platform tail)**: resource fairness / fair scheduling / anti-noisy-neighbor;
  per-tenant quota; many-writer durability; cross-process/distributed pooling. This is the additive
  per-principal isolation SLICE only.
- All items pass; spec is ready for `/speckit-plan` (which consults the fork + authors the ADR).
