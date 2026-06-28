# Research: Code Review Remediation

## Decision: Use a Single 073 Remediation Feature

**Decision**: Track all review fixes under `073-code-review-remediation`.

**Rationale**: The input is a single code review report over units 001-072, and
the fixes cut across CI, Python adapters, web, desktop, and docs. A single
remediation feature keeps traceability without pretending these are new product
capabilities.

**Alternatives considered**:

- Separate feature per finding: too much artifact overhead and harder to review
  as one quality push.
- Direct hotfix without Spec Kit: conflicts with the repository constitution
  and the user's request to think through Spec Kit flow.

## Decision: Fix Desktop Against Current Web Contracts

**Decision**: Update the desktop renderer to consume current web app state and
components rather than recreating deleted `Conversation`, `Prompts`, or
`Timeline` components.

**Rationale**: The review found desktop imports stale web components and fields.
Restoring old components would reintroduce an obsolete UI contract. The safer
repair is to align desktop with current web primitives or simplify its shell to
current supported state.

**Alternatives considered**:

- Re-add compatibility wrappers in web: larger surface and likely hides future
  drift.
- Remove desktop web imports entirely: may be too large for this remediation
  unless current alignment proves fragile.

## Decision: Run Desktop CI on Web Source Changes

**Decision**: Add `apps/web/**` to the desktop workflow path triggers.

**Rationale**: Desktop imports `@web/*`; therefore web changes can break desktop
typecheck and tests. CI should reflect that dependency until shared UI is moved
to a separate package.

**Alternatives considered**:

- Extract shared UI package now: useful long term, but too broad for this
  remediation.

## Decision: Normalize Model-Visible Error Text

**Decision**: MCP and web-fetch failures should return stable, class-specific
messages without raw exception messages, raw URLs, tracebacks, or secret-like
values.

**Rationale**: These outputs can reach the model, UI, event history, or
checkpoints. Public-safety is more important than embedding diagnostic detail in
returned content.

**Alternatives considered**:

- Redact only known secret keys: brittle and misses signed URLs or arbitrary
  exception payloads.
- Keep raw details in tool output for debugging: conflicts with public-safe and
  model-visible error boundaries.

## Decision: Bound Web Fetch Before Cache Reuse

**Decision**: Bound the fetched body in `src/loopplane/tools/web.py` before it
is cached or returned.

**Rationale**: Gateway output truncation cannot prevent adapter-level memory or
cache retention. A boundary in the web tool keeps the cache safe and makes the
behavior testable with an injected fetcher.

**Alternatives considered**:

- Rely only on Gateway truncation: does not address adapter/cache memory
  pressure.
- Full streaming refactor: valuable but likely bigger than necessary for the
  immediate finding if the current fetcher returns text.

## Decision: Document Spec Task Drift Through an Audit

**Decision**: Add a contract-level audit and explicit exception document for
historical verified units whose `tasks.md` files still have unchecked boxes.

**Rationale**: The review found drift between board status and historical task
files. Blindly marking tasks complete would fabricate evidence. An audit plus
exception list makes the drift explicit and prevents new unchecked verified
units from slipping through.

**Alternatives considered**:

- Mark all historical tasks complete: not defensible without per-task evidence.
- Do nothing: leaves future autopilot and reviews with contradictory signals.
