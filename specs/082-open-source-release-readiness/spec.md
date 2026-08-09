# Feature Specification: Open-Source Release Readiness

**Feature Branch**: `082-open-source-release-readiness`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Analyze whether the current CLI + Web + Cowork (desktop) architecture is suitable for open-sourcing the project, inventory the functional scope, and specify the adjustments needed, in phases, so an implementing agent has an authoritative basis to execute."

## Context

A three-track architecture review (Python core; Web/Desktop/shared-presentation frontends; documentation and release state) concluded on 2026-08-08 that the runtime architecture is **sound and suitable for open-sourcing as-is**: layering, boundary guards, ADR discipline, and default-preservation rules are stronger than most public projects. The gaps are concentrated in (a) distribution and release mechanics, (b) governance visibility for outside contributors, (c) documentation coverage for units 021–081, and (d) a small set of internal-scale debts (oversized modules, missing static boundary gate, test-debt in two load-bearing packages). The full analysis, evidence paths, and sequencing rationale live in [handoff.md](handoff.md), which is a companion artifact of this unit.

This unit deliberately does **not** touch the two in-flight/reserved units: 078 (desktop cowork parity, active with uncommitted work) and 079 (CLI remote parity, blocked on 078). UI-sharing completion (moving Web components into `packages/cowork-presentation`) is 078's remaining scope (tasks T062/T063/T066) and is out of scope here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and run from a published package (Priority: P1)

An external developer discovers the project, installs `loopplane` (plus chosen extras) from a public package index into a clean Python 3.12 environment without cloning the repository, and completes the credential-free quickstart.

**Why this priority**: Distribution is the single largest gap between "public repository" and "usable open-source project". `README.md` currently states that installing is from a clone only and that index publication is a future step.

**Independent Test**: Build the wheel/sdist locally, install the built artifact into a fresh venv (index publication itself is a human-gated action), then run the quickstart example and the `loopplane` console script. Succeeds without a repository checkout.

**Acceptance Scenarios**:

1. **Given** a clean Python 3.12 venv and the built wheel, **When** installing the wheel with the `web` extra plus one provider extra, **Then** installation resolves without the repository checkout, `import loopplane` succeeds, and the `loopplane` console script runs.
2. **Given** the built distribution, **When** validating its metadata (e.g. `twine check` or equivalent), **Then** license, project URLs (Homepage, Repository, Changelog, Issues), and classifiers (including operating-system coverage) are present and render correctly.
3. **Given** `README.md`, **When** an outside reader follows the Install section, **Then** index-install is described as the primary path (with truthful "pending first publish" wording until publication happens), clone-install is the contributor path, and CI/license/Python badges are present and truthful.

---

### User Story 2 - One-command tagged release (Priority: P1)

A maintainer cuts a release by pushing a `vX.Y.Z` tag. Automation validates release synchronization (a `X.Y.Z` section exists in `CHANGELOG.md`, `loopplane.__version__` equals the tag, board release rules in `docs/architecture/RELEASE_SYNC_RULES.md` are satisfied), builds the distributions, publishes them to the package index (trusted publishing / OIDC, no long-lived secrets), and creates a GitHub Release carrying the changelog extract. Any synchronization violation fails closed and publishes nothing.

**Why this priority**: Sixteen verified units (064–077, 080–081) currently sit in `[Unreleased]` with the latest tag at `v0.4.0`. Releasing must become cheap and safe or it will keep lagging behind verified work.

**Independent Test**: Exercise the workflow in a dry-run/no-publish mode against a test tag; assert fail-closed behavior on a synthetic desynchronization (e.g. tag without a matching CHANGELOG section).

**Acceptance Scenarios**:

1. **Given** a tag whose CHANGELOG section, `__version__`, and board rows are synchronized, **When** the tag is pushed, **Then** distributions are built and published and a GitHub Release with the changelog extract is created in one automated run.
2. **Given** a tag with no matching CHANGELOG section (or `__version__` mismatch), **When** the workflow runs, **Then** it fails closed with a clear diagnostic and nothing is published.
3. **Given** a partially failed publish, **When** the workflow is re-run for the same tag, **Then** the run is idempotent (already-published artifacts are skipped, not duplicated, and do not fail the run).

**Human gate**: The actual next release cut (version bump, CHANGELOG promotion, board sync, tag) remains a maintainer-only action per approval-gate §E ("Releases"). This story delivers the machinery and a documented runbook, not the release itself.

---

### User Story 3 - Governance and contributor safety (Priority: P2)

An outside contributor can find who decides what (`GOVERNANCE.md`), which paths route to maintainer review (`CODEOWNERS`), and — critically — a "hazard map" in `CONTRIBUTING.md` that explains the deliberately kept compromises so newcomers do not "fix" them: the two TYPE_CHECKING-quarantined import cycles (`context ⇄ tools`, `host ⇄ tools`; risks R1/R4 in `docs/architecture/RISK_REGISTER.md`), the boundary-guard tests, the human-approval gates (§E of `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`), and the default-off / byte-identical rule.

**Why this priority**: The repository's strongest asset — its governance discipline — is currently written for inside agents, not outside contributors. The most likely first PR from an outsider is precisely one that converts a lazy import to top-level or "cleans up" a guarded edge.

**Independent Test**: Review-only walkthrough — given a synthetic contribution that converts a lazy import to top-level, `CONTRIBUTING.md` and the PR template point the contributor at the forbidding rule before CI even runs; `CODEOWNERS` routes changes to load-bearing paths (`src/loopplane/model/`, `src/loopplane/errors.py`, `src/loopplane/events/`, `src/loopplane/context.py`, `src/loopplane/gateway/`, `src/loopplane/host/assembly.py`, workflows, `docs/architecture/`) to maintainer review.

**Acceptance Scenarios**:

1. **Given** the published repository, **When** a contributor reads `GOVERNANCE.md`, **Then** roles, decision rights, and the meaning of "maintainer approval" gates referenced across the docs are unambiguous.
2. **Given** a PR touching a load-bearing path, **When** it is opened, **Then** `CODEOWNERS` requests maintainer review automatically.
3. **Given** `CONTRIBUTING.md`, **When** a contributor plans a change that would trip a §E gate or a boundary guard, **Then** the hazard map names the rule, the reason, and the required approval path.
4. **Given** the agent board after 078's board transition, **When** its ADR-0015 status text is checked, **Then** any remaining "Proposed" wording is aligned with the ADR file's Accepted status (docs-only; no completion-status change). Skip if 078's own closure already fixed it.

---

### User Story 4 - Public documentation coverage (Priority: P2)

The documentation index (`docs/README.md`) currently lists per-layer guides only up to unit 020; the majority of the product (units 021–081: providers, tools, permissions, cost governance, platform/web deployment, extensibility, web UX) is discoverable only via `docs/capabilities.md`, `docs/api-reference.md`, and the CHANGELOG. Deliver **consolidated thematic guides** (not one page per unit) and update the index so every capability category is reachable from the index.

**Why this priority**: For an open-source audience, undiscoverable features do not exist. The inventory (`docs/capabilities.md`) is complete but is a reference table, not an on-ramp.

**Independent Test**: For each capability category in `docs/capabilities.md`, a guide covering it is reachable from `docs/README.md` within one click; a link-check over `docs/` passes.

**Acceptance Scenarios**:

1. **Given** `docs/README.md`, **When** a reader looks for any capability category from `docs/capabilities.md`, **Then** a covering thematic guide is linked from the index.
2. **Given** any new guide, **When** it describes behavior, **Then** it carries unit-number anchors and defers to `docs/api-reference.md` and `docs/capabilities.md` per the source-of-truth ladder (guides are navigational, not a new authority).

---

### User Story 5 - Declarative import-boundary gate (Priority: P3)

One table-driven contract test derives the allowed-import matrix for **all** `loopplane` packages, auto-discovers new packages, and fails closed (default-deny) for packages with no declared allowlist — closing risk R10 ("boundaries lack a static gate"). The existing 17 bespoke AST guard tests keep running unchanged in this unit; retiring them is a separate later cleanup.

**Why this priority**: Today a brand-new package ships with no import guard by default; each guard is hand-written. One declarative contract makes the boundary system legible to outside contributors and closes the coverage hole.

**Independent Test**: Seed a forbidden edge (temporary test fixture) and observe the gate fail; add a synthetic undeclared package and observe the gate fail; current code passes.

**Acceptance Scenarios**:

1. **Given** the gate, **When** a forbidden import edge is introduced anywhere under `src/loopplane`, **Then** the gate fails naming the edge and the owning rule.
2. **Given** the gate, **When** a new package appears without a declared allowlist entry, **Then** the gate fails closed (demands an explicit declaration) rather than silently allowing.
3. **Given** the current codebase, **When** the gate runs, **Then** it passes, and the declared matrix is consistent with `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`.

**Constraint**: Prefer no new dependency (reuse the existing AST machinery from `tests/contract/test_tools_boundary.py`). Adopting `import-linter` instead is allowed only with maintainer approval (§E, new dev dependency).

---

### User Story 6 - Internal decomposition of oversized modules (Priority: P3)

Contributor-scale refactoring of the two oversized modules, with zero outward-contract change:

- (a) Split `src/loopplane/webapi/app.py` (~1.27k lines, ~60 routes) into per-domain routers (sessions, streaming/live, interaction, capabilities, inspect, cost, uploads/models/commands), keeping `create_app(...)` signature and the outward HTTP/SSE/WS contract byte-identical.
- (b) Decompose `src/loopplane/host/capability_manager.py` (~1.5k lines, largest file in the repository) into cohesive submodules preserving public export semantics. **Ordered strictly after 078 reaches Verified** (same package as 078's live edits).

**Why this priority**: Both files work; the cost is onboarding and review ergonomics, so this ranks below distribution/governance. R11 in the risk register already names the webapi hotspot.

**Independent Test**: A route-inventory/contract snapshot test written **before** the split proves the outward contract is unchanged after it.

**Acceptance Scenarios**:

1. **Given** a contract snapshot (route inventory: method, path, response model identity) captured before the split, **When** the split lands, **Then** the snapshot comparison passes unchanged and `tests/contract/test_webapi_boundary.py` still passes.
2. **Given** the split, **When** the full §G gate suite runs, **Then** results are green with no new skips attributable to this story.
3. **Given** story (b), **When** it is scheduled, **Then** 078 is already Verified on the board; otherwise the story does not start.

---

### User Story 7 - Architecture-audit refresh and verified test-debt backfill (Priority: P3)

`docs/architecture/ARCHITECTURE_AUDIT.md` is a frozen snapshot (2026-07-06) that is due for refresh under its own "every ~10 units" rule and is already provably stale in places: its test-gap table claims `controller/` lacks a dedicated test file, but `tests/unit/test_controller_core.py`, `test_controller_capability_seams.py`, `test_errors_core.py`, and `test_engineering_core.py` all exist today (added the day after the snapshot). This story (a) refreshes the audit against the current tree, and (b) backfills only the test gaps the refresh **confirms** (candidates from the stale table: depth on the controller's checkpoint recording boundary and dispatcher paths, `engineering/`, `memory/`, `skills/`), following the `tests/unit/test_<pkg>_core.py` convention. No production-code change is required by this story.

**Why this priority**: For an open project, both an out-of-date audit and genuinely thin load-bearing coverage invite well-meaning but risky refactors — but backfilling against a stale gap list would waste effort on solved problems, so verification comes first.

**Independent Test**: The refreshed audit's claims are spot-checkable against the tree; new test files run green in isolation and in the full suite; the behaviors newly exercised (e.g. dispatcher paths, checkpoint recording boundary, resume behavior including the default `working_scope=None` path) are listed in the completion report.

**Acceptance Scenarios**:

1. **Given** the refreshed audit, **When** its test-gap table is compared with `tests/`, **Then** every listed gap is real (no stale entries), and the snapshot date/commit is updated per the audit's own refresh rules.
2. **Given** the new tests, **When** the full suite runs, **Then** it is green and the new files follow the G7 naming conventions.
3. **Given** a deliberate mutation of a newly covered behavior (temporary local check), **When** the new tests run, **Then** at least one fails (coverage is real, not tautological).

---

### Edge Cases

- Tag pushed while `CHANGELOG.md` / `__version__` / board are out of sync → release workflow fails closed; nothing is published (no partial release).
- Publish succeeds for one artifact and fails for another (network flake) → re-run is idempotent; already-published files are skipped without error.
- The package-index name is claimed by a third party before the maintainer reserves it → the availability assumption is invalidated; stop and record a naming decision with the maintainer (do not improvise a name).
- Router split accidentally renames/reorders a route or changes a response model → the contract snapshot guard fails before review.
- The boundary gate's auto-discovery meets a package created mid-flight by 078/079 → the gate demands an explicit allowlist entry (fail closed), never silently allows.
- A thematic guide contradicts `docs/api-reference.md` → the guide is wrong by definition (trust ladder); guides must defer and link, not restate normatively.
- Release workflow triggered by a non-tag event or a fork → it must not attempt any publish step.

## Requirements *(mandatory)*

### Functional Requirements

**Distribution & release (US1, US2)**

- **FR-001**: Package metadata MUST be completed for public consumption: project URLs (Changelog, Bug Tracker/Issues, Documentation alongside the existing Homepage/Repository) and classifiers (including operating-system coverage), following current PyPA guidance for the already-present SPDX license expression. No dependency or extra changes are implied by this requirement.
- **FR-002**: A convenience extra (e.g. `all` or `server`) MAY be added ONLY with explicit maintainer approval (§E gate: new extras). If not approved, the README MUST instead document the extras matrix (which extras combine for which deployment).
- **FR-003**: CI MUST validate build + metadata (`uv build` plus a metadata check such as `twine check`) on every push, extending the existing `.github/workflows/ci.yml` (which already runs `uv build`).
- **FR-004**: A release workflow MUST exist that, on `v*` tag push only: validates release synchronization per `docs/architecture/RELEASE_SYNC_RULES.md` (CHANGELOG section exists, `__version__` matches, board rules), builds distributions, publishes via trusted publishing (OIDC; no long-lived tokens), and creates a GitHub Release with the changelog extract. It MUST fail closed on any validation failure, MUST be idempotent on re-run, and MUST NOT publish from non-tag events or forks. Until the maintainer configures the index-side trusted publisher, the workflow MUST support a no-publish dry-run mode so it can be merged and exercised safely.
- **FR-005**: A release runbook MUST be written (extend `docs/release-readiness.md` or add `docs/release-process.md`, linked from the docs index) covering the human-gated steps: version bump, CHANGELOG promotion, board sync, tag, post-publish verification.
- **FR-006**: `README.md` MUST gain truthful badges (CI, license, Python version) and an Install section that presents index-install as the primary path once the first publish happens; wording MUST remain truthful in the interim ("pending first publish").

**Governance (US3)**

- **FR-007**: `GOVERNANCE.md` MUST document roles, decision rights, and the concrete meaning of the "maintainer approval" gates referenced across the repository (mapping to §E of `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`). A `CODEOWNERS` file MUST route load-bearing paths (see US3) to maintainer review.
- **FR-008**: `CONTRIBUTING.md` MUST gain a hazard-map section covering: the two sanctioned TYPE_CHECKING cycles (R1/R4) and why they must not be "fixed", the boundary-guard test system, the §E approval gates, the default-off/byte-identical rule, the English-docs and public-safety (Constitution VII) requirements.
- **FR-009**: After 078's board transition, IF the agent board still describes ADR 0015 as Proposed, the text MUST be aligned with the ADR file's Accepted status. Docs-only; MUST NOT alter any completion-status value; skip if already fixed by 078's closure.

**Documentation (US4)**

- **FR-010**: Consolidated thematic guides MUST cover the capability categories spanning units 021–081, and `docs/README.md` MUST index them. Guides MUST carry unit anchors and defer to `docs/capabilities.md` / `docs/api-reference.md` as authorities.

**Internal hardening (US5, US6, US7)**

- **FR-011**: A single declarative, table-driven boundary contract test MUST cover all `src/loopplane` packages with auto-discovery and default-deny for undeclared packages, consistent with `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`. Existing bespoke guards MUST remain untouched in this unit.
- **FR-012**: The webapi router split MUST be preceded by a contract snapshot test (route inventory) that proves the outward contract is unchanged after the split; `create_app(...)` keyword surface MUST be preserved. This is explicitly an internal refactor — triggering §E ("outward web/API contract changes") means the story has failed its own requirement.
- **FR-013**: `capability_manager.py` decomposition MUST NOT start before 078 is Verified on the board, and MUST preserve public export semantics (`loopplane.host` surface unchanged).
- **FR-014**: The architecture-audit refresh MUST follow the audit file's own snapshot/refresh conventions (read-only evidence tags, snapshot date/commit), and any backfilled tests MUST target refresh-confirmed gaps only, follow G7 naming conventions, and MUST NOT require production-code changes.

**Global constraints (all stories)**

- **FR-015**: All work MUST preserve: runtime behavior (no default-value change), `SCHEMA_VERSION` / `RECORD_SCHEMA_VERSION`, the dependency set (no new runtime dependency; dev-dependency additions need §E approval), public-safety (Constitution VII — no internal paths/names/secrets), and English as the documentation language.
- **FR-016**: While 078 is not Verified, this unit MUST NOT byte-change the 078-sensitive set: `pyproject.toml`, `uv.lock`, root `package.json` / `package-lock.json` (Stage-B accepted inputs), `apps/**`, `packages/**`, `src/loopplane/host/**`, `src/loopplane/controller/**`, `scripts/*desktop*.ps1`, `.github/workflows/desktop.yml`, `docs/adr/0015-*`, `specs/078-*/**`, and desktop-related tests. Sequencing per story: see Assumptions.

### Key Entities

Not applicable — this unit changes packaging, automation, documentation, and test structure; it introduces no new runtime data model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean Python 3.12 venv, installing the built wheel (with `web` + one provider extra) and running the credential-free quickstart succeeds without a repository checkout; the command transcript is recorded in the completion report.
- **SC-002**: The release workflow demonstrates, in recorded runs: (a) a synchronized dry-run tag producing artifacts + release notes, and (b) a synthetic desync failing closed with nothing published.
- **SC-003**: All §G verification gates (ruff format/check, mypy, full pytest, `uv build`; frontend typecheck/tests untouched by this unit remain at baseline) are green at unit completion, reported as literal fresh counts.
- **SC-004**: The webapi route/contract snapshot is identical before and after the router split (test-enforced), and no §E gate was triggered.
- **SC-005**: The boundary gate demonstrably catches (in tests) both a seeded forbidden edge and an undeclared new package, while the current tree passes.
- **SC-006**: Every capability category in `docs/capabilities.md` is reachable from `docs/README.md` within one click; a docs link-check passes.
- **SC-007**: A public-safety scan over all files added/changed by this unit finds zero internal paths, private names, or secrets.

## Assumptions

- The package-index name `loopplane` appeared unclaimed on 2026-08-08 (PyPI JSON API returned 404 for the project). Name reservation and the first publish are maintainer-only actions; if the name is taken meanwhile, stop and record a naming decision.
- Making the repository public, configuring the index-side trusted publisher, and cutting the next release (recommended: `v0.5.0` covering units 064–081, plus 078 if Verified by then) are maintainer-only actions outside agent scope (§E: Releases).
- 078 is in flight on its own branch with uncommitted work, including a known WIP defect in `apps/desktop/electron/main.ts` (invalid `*,` parameter syntax; mismatched call site) that belongs to 078, not to this unit. 079 is reserved and untouched.
- Story sequencing relative to 078: **US1's `pyproject.toml` edits are deferred until 078 is Verified** (Stage-B binds `pyproject.toml`/`uv.lock` bytes) while US1's other tasks (CI metadata check, README, install validation) may start immediately; **US2, US3, US4** create new standalone files (workflows, governance docs, guides) plus README/CHANGELOG-additive edits and may start immediately; **US5, US6a, US7** touch `src`/`tests` outside 078's files and may start immediately, but landing order versus 078's Stage-C delivery review should be coordinated with the maintainer to avoid enlarging 078's review surface; **US6b** is hard-blocked on 078 Verified.
- The `.superpowers/` directory and other untracked local artifacts are never staged or committed (per the repository's staging discipline).
- The implementing agent follows the Spec Kit flow for this unit (plan → tasks → analyze → implement) and the completion-report format of `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` §H.

## Out of Scope

- 079 CLI remote parity; all remaining 078 work (including Web→`packages/cowork-presentation` extraction T062/T063/T066 and the desktop WIP fix).
- Runtime feature roadmap items from `docs/gap-analysis.md` §C4 (distributed multi-worker tail, docker sandbox, MCP interactive OAuth, metering/billing, IDE/voice/output-styles).
- Flipping the repository to public and performing the actual index publication (maintainer actions).
- Retiring the 17 bespoke AST guards (later cleanup after the declarative gate has soaked).
