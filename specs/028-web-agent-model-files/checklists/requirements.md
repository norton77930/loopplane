# Specification Quality Checklist: Web Agent Model Selection & File Attachments

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-19
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

- **Re-scoped to additive — no ADR — after a reference review.** This unit was first flagged as
  "governance-gated" (per-session model + file upload looked like they needed boundary ADRs).
  A read-only review of a working reference design plus the runtime's own seams showed both can
  be delivered **additively, without blurring a runtime boundary**, so **no constitution ADR is
  required** — it is now like unit 027:
  - **Model selection** is resolved **in the web/API layer**: a registry of pre-configured
    single-model hosts (one per unit-020 adapter) + per-session routing, with the session
    resuming from the **shared checkpoint store** (unit 021) across hosts. The runtime keeps
    **one model per run** (never made to switch internally), so Principle IV is untouched.
  - **File upload** is an **additive upload endpoint** (per-principal, unit 022) + a
    **read-upload tool inside the Tool Gateway** (Principle V explicitly permits new tools in the
    gateway). Files are **transient input read on demand** — **no content-model change**, so the
    content/prompt contract is unchanged.
- **The one thing that WOULD need an ADR is deliberately Out of Scope.** Embedding file/image
  content directly into the prompt (a multimodal content block) would touch the content boundary
  (Principle IV); it is **deferred to a later unit**. This unit delivers **tool-read** access,
  which already exceeds the reference (whose web path never feeds file content to the model).
- **Autopilot no longer pauses here.** Because nothing blurs a runtime boundary, this unit is
  **gate-free like 025–027/029** — the board/banner reflect the removal of the ADR gate.
- **Behavior-level requirements.** The FRs describe what the user can do (select a model, attach
  files the agent can read) and the additive guarantees (one model per run; files via a gateway
  tool, not embedded), not the endpoint shapes or UI libraries — a `plan.md` decision.
- **Additive & reversible (X), public-safe (VII), no SDK replacement (VIII).** The runtime core,
  the Tool Gateway (V), the Event Bus (VI), the content model, and existing endpoints are
  preserved.
- No `[NEEDS CLARIFICATION]` markers; all items pass on the first iteration. Ready for
  `/speckit-plan`.
