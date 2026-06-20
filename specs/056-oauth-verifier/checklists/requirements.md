# Specification Quality Checklist: OAuth/JWT Verifier

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

- **Additive — no ADR**: a new verifier implementation behind the EXISTING unit-022 `Authenticator`
  async seam (`Callable[[str | None], Awaitable[Principal | None]]`, injected via
  `create_app(authenticator=…)`, default `DENY_ALL`). Crosses no runtime boundary — wholly in
  `loopplane.webapi`; inherits the 022 admit/deny/raise→401 + no-credential-echo contract unchanged.
- **Plan DECISION (maintainer consult, FR-008)**: the JWT library + optional-extra name (PyJWT[crypto]
  vs joserfc/authlib → `loopplane[oauth]`) and whether to ship a thin in-tree OIDC-discovery/JWKS
  helper vs a documented BYO recipe. The plan step STOPs to ask the maintainer before implementing.
- **Security is the load-bearing surface**: the negative matrix (alg=none, HS/RS confusion, wrong
  iss/aud, expired, nbf, unknown kid, tampered sig) — a too-LENIENT verifier is the danger, entirely
  in the new code; offline-tested with a local self-signed keypair + in-memory JWKS (no network).
- **Default-off / fail-closed**: no authenticator → `DENY_ALL` byte-identical; the JWT dep is
  import-guarded behind a new optional extra; any verifier/JWKS fault → deny/401, never admit/echo.
- Out of scope: interactive authorization-code/browser login (token-in assumed), opaque-token
  introspection, session cookies, multi-IdP federation beyond a configured issuer set.
- All items pass; spec is ready for `/speckit-plan` (which STOPs to consult the JWT-lib decision).
