# Specification Quality Checklist: JWKS Unknown-Kid Refresh Hardening

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

- **P1, no ADR** — a security hardening of the EXISTING 056 `_JwksResolver` in `webapi/auth_jwt.py`
  only; behind the existing `loopplane[oauth]` extra; no new dependency / boundary.
- **DEFAULT-SAFE, not default-off**: this is a security fix, so the throttle + negative cache are ON
  by default; the LEGITIMATE path is preserved (a known cached kid is byte-identical; a real new kid
  after rotation is resolved by the first throttle-permitted refresh). The only behavioural change is
  that an unknown-kid SPRAY no longer triggers a fetch per request.
- **The three mechanisms**: (1) a cross-request refresh throttle (≤ 1 fetch / `refresh_min_interval`);
  (2) single-flight (a concurrent burst shares one fetch); (3) a short negative-kid cache.
- **The one tuning the plan picks**: the default `refresh_min_interval` — chosen so it never blocks a
  legitimate TTL-driven refresh (e.g. ≤ `cache_ttl`) while bounding the spray.
- **Public-safety**: a throttled/rejected kid yields the same opaque reject as today (no leak about
  why); the kid/DSN/token are never echoed.
- All items pass; ready for `/speckit-plan`.
