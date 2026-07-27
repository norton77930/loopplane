# Agent Controls Requirements Readiness Checklist: Web Agent Controls

**Purpose**: Formal reviewer gate for the completeness, clarity, consistency, and measurability of 077 requirements before planning
**Created**: 2026-07-27
**Feature**: [spec.md](../spec.md)

**Note**: These items assess the quality of the written requirements, not implementation behavior.

## Requirement Completeness

- [x] CHK001 Are all first-class control categories—execution posture, cost/budget, workspace/references, and follow-up suggestions—explicitly included and independently testable? [Completeness, Spec §User Stories 1–4]
- [x] CHK002 Are owner, non-owner, read-only, unavailable, disabled, and unsupported scenarios defined for each host-projected control category? [Coverage, Spec §FR-010, §FR-011, §FR-024, §FR-029]
- [x] CHK003 Does the specification explicitly bound Desktop and CLI work while preserving shared-consumer compatibility? [Scope, Spec §FR-033, §Assumptions]
- [x] CHK004 Are the frozen-history, protected-local-artifact, raw-openspec, staging, publication, and release exclusions stated as requirements rather than informal notes? [Completeness, Spec §FR-039, §FR-040]
- [x] CHK005 Are maintainer/ADR stop conditions documented for every architecture or durability boundary the feature could otherwise expand? [Completeness, Spec §FR-036]

## Plan And Permission Semantics

- [x] CHK006 Is the authority split between displayed posture, host-approved choices, and actual enforcement unambiguous? [Clarity, Spec §FR-002, §FR-005, §FR-006]
- [x] CHK007 Is per-run scope and non-durability of permission selection explicit enough to prevent browser mutation of durable session or host-global configuration? [Clarity, Spec §FR-006, §Assumptions]
- [x] CHK008 Are plan-entry semantics distinguished from plan-exit request and approval semantics? [Consistency, Spec §FR-007, §FR-008]
- [x] CHK009 Is deny-wins and approval precedence stated consistently across user scenarios, functional requirements, and success criteria? [Consistency, Spec §US1, §FR-007–009, §SC-002]
- [x] CHK010 Are stale, denied, unauthorized, and cross-principal plan-exit requests covered as explicit negative scenarios? [Coverage, Spec §US1 Acceptance 4–6, §Edge Cases]
- [x] CHK011 Does the specification define the read-only fallback when the host exposes posture but no mutable actions? [Completeness, Spec §US1 Acceptance 5, §FR-010]
- [x] CHK012 Are permission summaries bounded tightly enough to exclude raw matching rules, private identifiers, and configuration internals? [Security, Spec §FR-004]

## Cost And Budget Semantics

- [x] CHK013 Are known zero, known nonzero, unknown, partial, unavailable, and unpriced states all defined without conflation? [Clarity, Spec §FR-013, §FR-014, §SC-004]
- [x] CHK014 Are session-level and principal-month cost scopes distinguished and independently unavailable where necessary? [Completeness, Spec §FR-012, §Edge Cases]
- [x] CHK015 Is the distinction between displayed budget metadata and authoritative server-side enforcement explicit? [Consistency, Spec §FR-015, §FR-017]
- [x] CHK016 Are below-limit, near-limit, exceeded, and pre-turn refusal scenarios covered without requiring private limit values to be disclosed? [Coverage, Spec §US2 Acceptance 3–4, §Edge Cases]
- [x] CHK017 Are provider rates, estimation internals, ledger keys, and another principal's financial metadata explicitly excluded? [Security, Spec §FR-016]
- [x] CHK018 Can every cost-state success criterion be objectively evaluated without assuming missing data equals zero? [Measurability, Spec §SC-004]

## Workspace And Safe Reference Boundary

- [x] CHK019 Are owned context, host-allowed context, bound context, and projected bind actions distinguished consistently? [Clarity, Spec §US3, §FR-018, §FR-019]
- [x] CHK020 Is the safe reference metadata allow-list described clearly enough to prevent raw content, private paths, credentials, and provider metadata from leaking? [Security, Spec §FR-020, §FR-021]
- [x] CHK021 Are reference use requirements limited to already-authorized resource actions rather than creating browser-side execution or general file browsing? [Boundary, Spec §FR-022, §FR-023]
- [x] CHK022 Are missing, expired, malformed, unsupported, authorization-changed, and non-owned reference outcomes covered as non-disclosing exception flows? [Coverage, Spec §FR-024, §Edge Cases]
- [x] CHK023 Is behavior defined when no safe reference projection exists, without weakening workspace controls or inventing durable content? [Completeness, Spec §US3 Acceptance 6, §Assumptions]
- [x] CHK024 Is cross-principal artifact sharing and any new artifact persistence boundary explicitly excluded and linked to the human/ADR gate? [Consistency, Spec §FR-023, §FR-036]

## Follow-Up Suggestion Semantics

- [x] CHK025 Is deterministic suggestion generation bounded to already-visible state and separated from assistant-authored output? [Clarity, Spec §FR-025, §FR-026]
- [x] CHK026 Are generation, selection, editing, dismissal, and explicit send states all addressed? [Coverage, Spec §US4 Acceptance 1–5, §FR-027]
- [x] CHK027 Is the prohibition on hidden model, tool, network, turn, and cost effects measurable? [Measurability, Spec §FR-026, §SC-006]
- [x] CHK028 Is adopted suggestion text required to follow exactly the same authorization and execution path as manually entered text? [Consistency, Spec §FR-028]
- [x] CHK029 Are stale suggestions after locale, session, posture, or workspace changes recognized as an edge case? [Coverage, Spec §Edge Cases]

## UX, Accessibility, And Compatibility

- [x] CHK030 Are loading, empty, read-only, unavailable, unpriced, disabled, pending, denied, and failed states named consistently? [Completeness, Spec §FR-029]
- [x] CHK031 Are keyboard, focus, announcements, reduced motion, forced colors, localization, and reflow requirements defined for all control categories? [Accessibility, Spec §FR-030, §FR-031, §SC-008]
- [x] CHK032 Are preservation requirements explicit for draft, stream, approval, messages, inspection, session, and scroll state while controls open or close? [Compatibility, Spec §FR-032]
- [x] CHK033 Are supported locales and document-language behavior stated consistently with measurable presentation criteria? [Consistency, Spec §FR-031, §SC-008]
- [x] CHK034 Are the navigation-depth and return-to-conversation outcomes objectively measurable? [Measurability, Spec §SC-007]

## Security, Architecture, And Delivery Consistency

- [x] CHK035 Are principal ownership and non-disclosure requirements applied consistently to list, detail, action, approval, cost, binding, and reference flows? [Security, Spec §FR-011, §FR-016, §FR-024, §SC-003]
- [x] CHK036 Are Tool Gateway, Runtime Event Bus, permission, approval, checkpoint, pricing, budget, dependency, and default-preservation boundaries stated without creating overlapping ownership? [Architecture, Spec §FR-028, §FR-034]
- [x] CHK037 Are public-safe error and sensitive-field exclusions complete across permission, budget, context, and reference outcomes? [Security, Spec §FR-004, §FR-016, §FR-021, §FR-024, §FR-035]
- [x] CHK038 Are fresh backend, Web, Desktop, browser, architecture, ownership, openspec-exclusion, and public-safety evidence requirements explicit and literal? [Completeness, Spec §FR-037, §FR-038, §SC-010]
- [x] CHK039 Does the specification clearly prevent a failed or skipped required gate from being silently treated as Verified? [Release Gate, Spec §US5 Acceptance 4, §FR-038]
- [x] CHK040 Are rollback, feature isolation, and documentation convergence identifiable as mandatory planning deliverables under the project's testable-evolution rules? [Gap, Constitution Principle X]
- [x] CHK041 Does the browser-selectable mode boundary explicitly exclude modes that bypass authorization or human approval? [Security, Spec §FR-042]
- [x] CHK042 Is authoritative accepted/effective posture defined as host-projected ephemeral active/last-run metadata rather than client draft state or checkpointed configuration? [Clarity, Spec §FR-003, §FR-043]
- [x] CHK043 Are non-image upload handoff bounds, eligibility, ownership timing, `read_upload` action availability, pre-model rejection, and Gateway-only later execution requirements explicit? [Security, Spec §FR-022, §FR-044]

## Notes

- Review completed on 2026-07-27: all 43 requirement-quality items pass after adding FR-041 for rollback/docs convergence, FR-042 for browser mode safety, FR-043 for authoritative ephemeral accepted posture, and FR-044 for bounded Gateway-safe non-image upload handoff.
- No critical ambiguity requires a user decision before planning; architecture discoveries that cross FR-036 remain explicit maintainer/ADR stop gates.
- Any later regression blocks planning or implementation when it affects scope, ownership, security, durability, approval ordering, or enforcement precedence.
