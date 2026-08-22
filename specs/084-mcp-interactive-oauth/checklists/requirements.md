# Specification Quality Checklist: MCP Interactive OAuth

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-22
**Updated**: 2026-08-22 — clarification session closed (Q1 = A, Q2 = B, Q3 = B)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *qualified, see Note 1*
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders — *qualified, see Note 1*
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — *all three resolved in the 2026-08-22 clarification
      session; see Note 2*
- [x] Requirements are testable and unambiguous — *the conditionals previously carried by FR-005 and
      FR-007 are now closed*
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic — *SC-007/SC-008/SC-012 are governance criteria stated
      in repository terms; see Note 1*
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification — *qualified, see Note 1*

## Notes

**Note 1 — deliberate house-style exception on implementation detail.** This repository's specs
ground themselves in the existing seam with file and line references; unit 059's spec does the same
(`adapter.py:130-181`). All such detail here is confined to the "Boundary note (read first)" section
and the Assumptions, both of which exist to bound the design. Every FR and every SC is stated
behaviourally and can be evaluated without reading source.

**Note 2 — all four design questions from the maintainer's brief are settled in the spec.**

- *Who opens the browser?* → the host (FR-001), never the runtime.
- *How is the callback received?* → the host, and **no component under `src/loopplane` may bind a
  listening socket** (FR-005). Desktop's Electron main process runs the loopback listener, so the
  one-click experience is delivered without the runtime ever listening.
- *What happens headless / in CI?* → fail closed (FR-015, FR-009): no connection, no unauthenticated
  attempt, no fallback to the 059 static token. Renewal of an already-authorized server still works
  unattended (FR-008), which is what keeps scheduled and long-running work viable.
- *Does this add a dependency?* → expected no; `loopplane[mcp]` already carries `httpx` and
  `pyjwt[crypto]` transitively via `mcp>=1`, and the flow composes the SDK's own `mcp.client.auth`.
  FR-018 makes any deviation a GATE-§E stop rather than a silent addition.

Token storage is settled in the spec rather than deferred to implementation: FR-007 (interface only,
in-memory default, **nothing written to disk by `src/loopplane`**), FR-010 (per-(principal, server)
isolation), FR-011 (discardable, so sign-out is possible), FR-021 (Desktop persists through the
ADR 0016 keystore path, outside the profile root so a backup cannot contain it by construction).

**Note 3 — R2 gates recorded in the spec, not left to the plan to remember.**

- **ADR 0019** authored at plan and **approved before implementation** (FR-017). Not retroactive.
- **Both `code-reviewer` and `architecture-reviewer`** at final review (FR-019) — no longer
  conditional, because Q2 = B extends the managed-MCP capability surface (FR-020).
- **`tests/contract/test_public_safety.py`** enumerates files via `git ls-files`, so it covers
  **tracked** files only. Any fixture carrying a token-shaped literal must be git-tracked before that
  scan counts as evidence — the same false-green that units 051 and 082 hit.
- **`tests/contract/fixtures/capability_surface.json`** pins the managed-capability signatures, so
  FR-020 requires that fixture to be regenerated deliberately rather than incidentally.
- **GATE-§E** applies to any new dependency or extra (FR-018).

**Note 4 — scope grew with Q2 = B, deliberately.** The unit now spans the runtime, the host
capability surface, the Desktop sidecar, and the Electron main process. Web is untouched. That is the
cost of making the capability reachable by someone who does not write Python, and it is the reason
`architecture-reviewer` is mandatory.
