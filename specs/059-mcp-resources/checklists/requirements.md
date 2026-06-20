# Specification Quality Checklist: MCP Resources + Host-Token Auth

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

- **Small ADR (0007) at plan, no consult**: records that MCP resources reach the model ONLY via the
  Gateway (as synthetic per-server resource tools) + the config-token transport auth. No re-consult
  (pre-approved as a small ADR). **If the resource surface turns out to need a content-model /
  event-schema change (it should not — resources return existing TextBlock/ImageBlock tool results),
  STOP and ask the maintainer** (a 2nd boundary).
- **Additive + reuse-first**: reuses the MCP adapter discover/translate/invoke pipeline + the Gateway
  adapter SPI + per-server failure isolation; resource tools are registered alongside discovered
  tools and dispatched to `session.list_resources()`/`read_resource()`.
- **Default-unused byte-identical**: a server with no resources + no token behaves as today; no new
  dependency.
- **Public-safe**: the host-supplied token is never echoed in output/errors/logs (VII).
- **Deferred**: the interactive browser OAuth authorization-code/PKCE flow; resource
  subscriptions/notifications; MCP prompts.
- All items pass; spec is ready for `/speckit-plan` (which authors ADR 0007).
