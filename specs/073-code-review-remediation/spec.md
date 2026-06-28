# Feature Specification: Code Review Remediation

**Feature Branch**: `073-code-review-remediation`

**Created**: 2026-06-23

**Status**: Draft

**Input**: User description: "Fix the findings from
`docs/code-review-001-072.md`, using Spec Kit flow where appropriate, and begin
implementation directly."

## Boundary Note

This unit converts the 001-072 code review findings into a traceable remediation
feature. It is not new product scope. It repairs verified behavior, CI
reliability, public-safety gaps, and auditability issues found after unit 072.

The unit may touch Python runtime/tooling, web and desktop app gates, CI
configuration, tests, docs, and Spec Kit audit artifacts only as needed to close
the findings. It must not add unrelated roadmap capabilities, change earlier
public contracts without a documented reason, copy private reference material,
or modify raw `openspec/`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Mainline Gates (Priority: P1)

A maintainer can run the same local and CI gates used by the project and trust
that dependency installation, Python checks, web checks, and desktop checks
exercise the current code rather than failing from stale metadata or incomplete
workflow triggers.

**Why this priority**: The review found that `uv sync --locked` fails before
the Python suite can run, and that desktop checks are not triggered by web
changes even though desktop imports web source.

**Independent Test**: Can be tested by running locked dependency sync, Python
gates, web gates, desktop gates, and inspecting workflow path triggers.

**Acceptance Scenarios**:

1. **Given** dependency metadata is checked out fresh, **When** locked sync is
   run, **Then** it succeeds without modifying lock metadata.
2. **Given** the desktop app imports shared web source, **When** web source
   changes in CI, **Then** the desktop typecheck and test workflow is eligible
   to run.
3. **Given** the desktop renderer is built against current web components and
   state, **When** desktop typecheck and tests run, **Then** they pass.

---

### User Story 2 - Public-Safe Tool Errors (Priority: P1)

A user or model consuming tool output never sees secrets, signed URLs, private
runtime details, raw exception text, or traceback-like diagnostic details from
MCP adapter failures or web fetch failures.

**Why this priority**: The review found model-visible error paths that echo raw
MCP exception messages and full URLs, including possible query-string secrets.

**Independent Test**: Can be tested offline with injected MCP and web-fetch
failures containing secret-looking values and asserting that only normalized,
public-safe messages cross the boundary.

**Acceptance Scenarios**:

1. **Given** an MCP tool call raises an exception containing sensitive text,
   **When** the adapter returns a tool error, **Then** the sensitive text and raw
   exception detail are absent from model-visible output.
2. **Given** an MCP resource read raises an exception containing sensitive text,
   **When** the adapter returns a resource error, **Then** the sensitive text and
   raw exception detail are absent from model-visible output.
3. **Given** a web fetch URL contains sensitive query parameters, **When** the
   request fails validation, times out, receives a non-success status, or hits a
   transport failure, **Then** the model-visible error omits query secrets and
   raw transport detail.

---

### User Story 3 - Bounded Web Fetch Resource Use (Priority: P2)

A host operator can enable web fetch without allowing a very large response to
be fully retained in adapter memory or cache before output truncation happens.

**Why this priority**: The review found that output truncation happens after
the web fetch adapter already materializes and caches the full response body.

**Independent Test**: Can be tested with an injected large response and by
asserting the adapter returns bounded content and does not cache the oversized
full body.

**Acceptance Scenarios**:

1. **Given** a web response exceeds the configured fetch output bound, **When**
   the adapter processes it, **Then** the returned content is bounded and clearly
   marked as truncated.
2. **Given** an oversized response is fetched, **When** the session cache is
   inspected through repeated fetches, **Then** only bounded content is reused.
3. **Given** a normal response is within the bound, **When** it is fetched,
   **Then** existing successful fetch behavior is preserved.

---

### User Story 4 - Traceable Spec Kit Audit State (Priority: P2)

A future autopilot or reviewer can compare board status, feature task state, and
review remediation state without being misled by historical unchecked task
boxes or untracked review findings.

**Why this priority**: The review found many older verified units whose
`tasks.md` checkboxes are still unchecked, weakening Spec Kit auditability.

**Independent Test**: Can be tested by running an audit that reports verified
units with unchecked historical tasks and distinguishes documented legacy
exceptions from current incomplete work.

**Acceptance Scenarios**:

1. **Given** a verified unit has historical unchecked tasks, **When** the audit
   runs, **Then** the result is explicit and traceable rather than silently
   conflicting with the board.
2. **Given** a current or future verified unit has unchecked tasks without an
   approved legacy note, **When** the audit runs, **Then** it fails or reports a
   blocking inconsistency.
3. **Given** the 073 remediation tasks are complete, **When** a reviewer reads
   the board and tasks, **Then** the remediation status is consistent.

---

### User Story 5 - Frontend And Desktop Hardening Follow-Up (Priority: P3)

A maintainer sees cleaner frontend test output, explicit Electron renderer
security settings, and a documented decision for the current web production
bundle size warning.

**Why this priority**: These are lower-priority review findings that improve
signal and hardening after the blocking and public-safety issues are fixed.

**Independent Test**: Can be tested by running web tests without React
`act(...)` warnings, inspecting Electron security settings, and verifying the
bundle-size warning has either been reduced or explicitly deferred with a
tracked rationale.

**Acceptance Scenarios**:

1. **Given** web tests run, **When** test output is inspected, **Then** current
   React `act(...)` warnings from `AppRoot` tests are gone.
2. **Given** the Electron window is created, **When** renderer preferences are
   inspected, **Then** isolation/security intent is explicit in source.
3. **Given** the web production bundle still exceeds the warning threshold,
   **When** final review is performed, **Then** the warning is either addressed
   or documented as a non-blocking follow-up with rationale.

### Edge Cases

- Existing untracked review report file must not be lost while creating 073
  artifacts.
- Fixing desktop/web drift must not break the web app's current tests or build.
- Sanitizing errors must not remove enough context to distinguish timeout,
  transport, validation, status, and adapter failure classes.
- Web fetch truncation must handle multibyte text safely enough for public
  output and must preserve normal cache behavior for bounded responses.
- Spec audit cleanup must not blindly mark historical tasks complete without
  evidence.
- Optional Spec Kit hooks may be reported or run only when safe; managed
  `AGENTS.md` blocks must not be hand-edited.
- `openspec/` must remain untouched and uncommitted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST include a traceable Spec Kit feature for the
  review remediation work, with spec, plan, tasks, and validation guidance.
- **FR-002**: Locked dependency synchronization MUST succeed without requiring
  uncommitted lockfile changes.
- **FR-003**: Desktop renderer typecheck and tests MUST pass against the current
  web component and state contracts.
- **FR-004**: Desktop CI MUST be eligible to run when web source changes can
  affect desktop compilation or tests.
- **FR-005**: MCP adapter tool-call and resource-read failures MUST return
  normalized public-safe errors without raw exception type, raw exception
  message, tracebacks, credentials, tokens, or secret-like values.
- **FR-006**: Web fetch validation, timeout, transport, and non-success errors
  MUST avoid exposing full raw URLs or query-string secrets in model-visible
  output.
- **FR-007**: Web fetch MUST bound response content before caching or returning
  it, while preserving successful behavior for responses within the bound.
- **FR-008**: The repository MUST provide an auditable way to reconcile or flag
  verified Spec Kit units whose historical task files still contain unchecked
  items.
- **FR-009**: Web frontend tests SHOULD be updated so current React `act(...)`
  warnings no longer appear in normal test output.
- **FR-010**: Electron renderer security preferences SHOULD explicitly state
  context isolation and Node integration intent.
- **FR-011**: The Vite production bundle-size warning SHOULD be either resolved
  or documented as an accepted follow-up with rationale.
- **FR-012**: Every behavior change in this remediation unit MUST have focused
  tests or an explicit verification command.
- **FR-013**: The remediation MUST pass public-safety checks and MUST NOT touch
  or commit raw `openspec/`.

### Key Entities

- **Review Finding**: A defect or risk recorded in
  `docs/code-review-001-072.md`, with priority, evidence, and recommended fix.
- **Remediation Task**: A traceable Spec Kit task that closes one or more review
  findings with tests and validation.
- **Model-Visible Error**: Any error text returned through tool output, runtime
  events, web responses, UI rendering, checkpoints, or history that may be seen
  by a user or model.
- **Spec Audit Exception**: A documented, public-safe explanation for historical
  unchecked task boxes that should not be treated as current incomplete work.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv sync --locked`, Python lint/type/test gates, web gates, and
  desktop gates all pass in the final review environment.
- **SC-002**: Regression tests prove MCP failures and web fetch failures do not
  leak injected secret-like values into model-visible output.
- **SC-003**: Regression tests prove oversized web fetch responses are bounded
  before cache reuse, while normal bounded responses still succeed.
- **SC-004**: CI workflow path configuration covers web changes that can break
  desktop compilation.
- **SC-005**: Spec audit output either has zero unapproved verified-unit task
  inconsistencies or documents approved legacy exceptions in a durable,
  public-safe artifact.
- **SC-006**: Final public-safety scans over changed files find no committed
  private paths, raw internal references, credentials, tokens, or secrets.

## Assumptions

- The remediation feature is unit 073 and continues on `main` without creating
  a new branch, matching current LoopPlane autopilot practice.
- The existing code-review report remains part of the working change until the
  user decides whether to commit it.
- The P0 and P1 findings are blocking for reliable final review; P2/P3 findings
  may be completed after the blocking fixes but still belong to this goal.
- Historical unchecked tasks should not be mass-marked complete unless there is
  evidence. A durable audit/exemption mechanism is acceptable when evidence is
  not available.
- Optional Spec Kit agent-context hooks are not required to proceed when their
  known PowerShell YAML fallback issue prevents a clean update.
