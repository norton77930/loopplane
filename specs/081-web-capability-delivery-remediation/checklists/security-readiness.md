# Security & Delivery Readiness Checklist: Web Capability Delivery Remediation

**Purpose**: Formal reviewer/release-gate checklist for the completeness, clarity, consistency, and measurability of 081 security and delivery requirements
**Created**: 2026-07-27
**Feature**: [spec.md](../spec.md)

**Note**: This checklist validates requirement quality, not implementation behavior. Use it during plan/task review and again before declaring 081 ready for implementation.

## Requirement Completeness

- [x] CHK001 Are the complete admissible and forbidden browser-managed MCP endpoint classes specified, including transport/scheme pairing, host presence, stdio, userinfo, query, fragment, and malformed port syntax? [Completeness, Spec §FR-001–FR-004, Research §Decision 1]
- [x] CHK002 Are endpoint requirements defined for browser requests, direct domain calls, persistence writes, legacy stored records, reconnect, and activation paths? [Coverage, Spec §FR-003–FR-006, Edge Cases]
- [x] CHK003 Are all terminal managed-MCP lifecycle paths documented, including update, delete, structural invalidity, policy denial, connection failure, state-write failure, registry-replacement failure, and successful reconnect? [Completeness, Spec §FR-007–FR-011, Contract: Managed MCP Runtime lifecycle]
- [x] CHK004 Are requirements present for immediate new-resolution removal, in-flight completion, final-lease shutdown, and exactly-once closure as separate lifecycle outcomes? [Completeness, Spec §FR-007–FR-009, SC-002]
- [x] CHK005 Are the allowed-context provider's input, safe output fields, absence/default behavior, provider failure behavior, duplicate-ID behavior, and owner/provider collision behavior all specified? [Completeness, Spec §FR-012–FR-016, Data Model §Allowed Workspace Context]
- [x] CHK006 Are safe-detail requirements defined separately for shared memory, skill, MCP, and workspace context rather than relying on one vague generic rule? [Completeness, Spec §FR-017–FR-020, User Story 3]
- [x] CHK007 Are working-tree ownership requirements defined for tracked, staged, untracked, mixed-hunk, local-artifact, and unknown-file cases? [Completeness, Spec §FR-025–FR-026, Contract: Delivery Convergence]
- [x] CHK008 Are required fresh gates, manual/browser evidence, failure/skip reporting, documentation synchronization, and rollback evidence all explicitly included in completion requirements? [Completeness, Spec §FR-027–FR-030, SC-007–SC-009]

## Requirement Clarity

- [x] CHK009 Is "immediately remove" defined by the observable boundary of new owner-scoped resolution before the mutation returns, rather than by eventual cleanup? [Clarity, Spec §FR-007–FR-008, Plan §Performance Goals]
- [x] CHK010 Is "public-safe" clarified with an explicit forbidden-disclosure set covering submitted endpoint data, credentials, private paths, authentication material, owner identity, and raw exceptions? [Clarity, Spec §FR-005, FR-018–FR-019]
- [x] CHK011 Is the difference between structural endpoint validity and host endpoint-policy approval explicit and unambiguous? [Clarity, Spec §FR-003–FR-006, Research §Decision 1]
- [x] CHK012 Is the canonical identity and fail-closed treatment of duplicate or colliding workspace contexts specified without an implicit owner-wins/provider-wins fallback? [Clarity, Spec §FR-016, Data Model §Collision rules]
- [x] CHK013 Is the phrase "bounded metadata" defined through an explicit allowed-field set for each shared capability type? [Clarity, Spec §FR-018–FR-019, Data Model §Shared Capability Detail Projection]
- [x] CHK014 Is action-driven interaction authority clearly distinguished from scope labels, visual badges, and editable owner forms? [Clarity, Spec §FR-017–FR-021, Contract: Shared details]
- [x] CHK015 Is the approved sync-to-async Python host API change precisely bounded to managed-MCP upsert/delete while explicitly preserving HTTP routes and JSON envelopes? [Clarity, Spec §Clarifications, Plan §Human approval record]

## Requirement Consistency

- [x] CHK016 Are endpoint rejection requirements consistent across the spec, research, data model, MCP contract, and quickstart without allowing query/fragment in one artifact and forbidding them in another? [Consistency, Spec §FR-001–FR-006]
- [x] CHK017 Are adapter retirement requirements consistent with Gateway sole ownership and the prohibition on host-side tool resolution, invocation, or direct shutdown? [Consistency, Spec §FR-009–FR-011, Plan §Constitution Check]
- [x] CHK018 Are allowed-context bind requirements consistent with principal/session non-disclosure and with the independent mutation/runtime-activation gates? [Consistency, Spec §FR-012–FR-016, FR-022]
- [x] CHK019 Are shared-detail requirements consistent with the decision to preserve existing HTTP response shapes and keep owner details complete? [Consistency, Research §Decision 5, Contract: Unchanged contracts]
- [x] CHK020 Are remediation-history requirements consistent with the rule that 076/080 spec/tasks stay frozen while 081 owns all new requirements, tasks, evidence, and rollback guidance? [Consistency, Spec §FR-025, Assumptions]
- [x] CHK021 Are documentation synchronization requirements consistent with release rules distinguishing live board/CHANGELOG/API updates from release-boundary version/README/capabilities work? [Consistency, Spec §FR-029, Plan §Constraints]

## Acceptance Criteria Quality

- [x] CHK022 Can every unsafe endpoint category be objectively mapped to a rejection-before-persistence/connection criterion with zero leaked submitted values? [Measurability, SC-001]
- [x] CHK023 Can lifecycle acceptance objectively distinguish new-resolution removal, in-flight completion, and exactly-once shutdown for update, delete, and failed reconnect? [Measurability, SC-002]
- [x] CHK024 Does the two-principal matrix define all security-sensitive operations that must produce zero cross-principal access or inference? [Coverage, SC-003]
- [x] CHK025 Can allowed-context success and non-disclosure be measured for approved, unapproved, duplicate, collided, provider-failure, and non-owner-session cases? [Measurability, SC-004, Edge Cases]
- [x] CHK026 Can shared-detail safety be objectively evaluated through explicit absence of mutable controls and forbidden fields for all four capability types? [Measurability, SC-005]
- [x] CHK027 Are responsive/accessibility criteria tied to enumerated widths, locales, themes, keyboard reachability, focus behavior, reduced motion, forced colors, and overflow rather than a vague "responsive" claim? [Measurability, SC-006, Quickstart §5]
- [x] CHK028 Is fresh-evidence success defined so historical counts, hidden failures, and unreported skips cannot satisfy completion? [Measurability, SC-007, Spec §FR-027–FR-028]
- [x] CHK029 Is the zero-local-artifact/zero-unclassified-change delivery criterion objectively reviewable across staged and untracked candidates? [Measurability, SC-008, Contract: Ownership inventory]

## Scenario and Edge-Case Coverage

- [x] CHK030 Are primary, alternate, exception, recovery, and non-functional scenarios all represented for managed-MCP admission and lifecycle? [Coverage, User Story 1, Edge Cases]
- [x] CHK031 Are provider absence, exception, invalid record, duplicate identity, owner collision, authorization change, and cross-principal session cases all addressed for allowed contexts? [Coverage, User Story 2, Edge Cases]
- [x] CHK032 Are shared resources with Open, without Open, with Bind, and with forbidden owner-only fields all covered by requirements? [Coverage, User Story 3]
- [x] CHK033 Are rollback requirements defined separately for runtime mutation/activation risk and presentation-only regression? [Recovery Coverage, Contract: Rollback, Quickstart §9]
- [x] CHK034 Is known intermittent-test handling specified without permitting a passing isolated rerun to erase the original full-suite failure? [Exception Coverage, Spec Edge Cases, FR-028]

## Security and Boundary Requirements

- [x] CHK035 Is the threat boundary explicit that browser-managed MCP authentication material is out of scope and cannot be encoded in endpoint URLs? [Security, Assumption]
- [x] CHK036 Are deny-by-default and fail-closed requirements explicit for endpoint policy absence/errors, provider errors/collisions, unknown contexts, and non-owned sessions? [Security, Spec §FR-005–FR-006, FR-015–FR-016]
- [x] CHK037 Are requirements explicit that no Event Bus, checkpoint schema, Gateway SPI/stage order, dependency, or default-value change is permitted? [Boundary, Spec §FR-024, Plan §Constraints]
- [x] CHK038 Is Gateway sole dispatch/lifecycle ownership traceable from requirements through plan and contracts without any competing host or UI execution path? [Traceability, Spec §FR-011, Plan §Constitution Check]
- [x] CHK039 Is default-off/byte-identical behavior measurable when the allowed-context provider is absent and mutation/runtime activation remain disabled? [Security/Compatibility, Spec §FR-012, FR-022–FR-024]
- [x] CHK040 Are public-safety requirements defined for documentation and delivery inventory as well as runtime/UI responses? [Security Completeness, Spec §FR-005, FR-019, FR-026–FR-029]

## Dependencies, Assumptions, and Delivery Governance

- [x] CHK041 Is the existing authentication, principal ownership, session ownership, endpoint policy, and Gateway lifecycle behavior explicitly identified as a dependency rather than re-specified inconsistently? [Dependency, Spec §Assumptions, Plan §Primary Dependencies]
- [x] CHK042 Is the maintainer approval record for the public Python async API change documented with date, exact scope, and unchanged contracts? [Governance, Spec §Clarifications, Plan §Human approval record]
- [x] CHK043 Is the stop-and-ask boundary explicit for any later HTTP schema, persistence schema, default, dependency, Gateway, Event Bus, or checkpoint expansion? [Governance, Plan §Human approval record, Research §ADR conclusion]
- [x] CHK044 Are commit, push, release, version, tag, and deployment exclusions documented so implementation authorization cannot be mistaken for publication authorization? [Governance, Spec §Assumptions, Plan §Constraints]
- [x] CHK045 Is the dependency ordering explicit that 081 must be Verified before 077 implementation may begin? [Dependency, Spec §FR-030, SC-009]

## Notes

- Check items off only after reviewing the written spec, plan, contracts, data model, quickstart, and tasks for the stated quality property.
- Record requirement gaps or conflicting citations inline; resolve them before implementation rather than treating this checklist as runtime QA.
- Formal depth: standard release gate. Primary audience: peer reviewer and maintainer before implementation and before final verification.
- Final implementation review on 2026-07-27: all 45 requirement-quality items remain satisfied; no unresolved security, boundary, evidence, or delivery-governance gap was found.
