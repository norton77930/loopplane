# Implementation Plan: Open-Source Release Readiness

**Branch**: `082-open-source-release-readiness` (to be created from `main` when implementation starts; planning artifacts were authored without switching branches because the working tree currently carries unit 078's in-flight work) | **Date**: 2026-08-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/082-open-source-release-readiness/spec.md`; architecture analysis and constraints from [handoff.md](handoff.md)

## Summary

Make the repository publishable, governable, and navigable as an open-source project without changing runtime behavior. Seven prioritized, independently revertible stories: (P1) installable package + metadata completeness, tag-triggered release automation with fail-closed release-sync validation and trusted publishing; (P2) governance documents (`GOVERNANCE.md`, `CODEOWNERS`) plus a contributor hazard map, and consolidated thematic documentation guides covering units 021–081; (P3) a declarative default-deny import-boundary gate (closes risk R10), internal decomposition of the two oversized modules behind a route-snapshot invariance guard, and an architecture-audit refresh with verified test-debt backfill. Everything is additive tooling/docs/tests; the §E-gated actions (the actual release cut, any new extra or dev dependency, index-side publisher configuration) remain maintainer-only. Sequencing is constrained by in-flight unit 078, whose Stage-B reviews bind `pyproject.toml`/`uv.lock` and the root npm manifests byte-exactly (see Constraints).

## Technical Context

**Language/Version**: Python 3.12 (scripts, tests, packaging); GitHub Actions YAML; Markdown. No TypeScript changes.

**Primary Dependencies**: Existing toolchain only — hatchling (build backend), uv, ruff, mypy, pytest, GitHub Actions runners with `astral-sh/setup-uv@v6`. Release publishing uses PyPI **trusted publishing** (OIDC) via the standard PyPA publish action; GitHub Release creation uses the `gh` CLI already present on runners. Transient tools invoked via `uvx` (e.g. `twine check`) add no dependency. **No new runtime or dev dependency by default**; adopting `import-linter` (US5 alternative) or adding a convenience extra (US1) each requires §E maintainer approval first.

**Storage**: N/A (no runtime data model; declarative artifacts only — see [data-model.md](data-model.md)).

**Testing**: pytest for the new contract tests (release-sync validator unit tests, webapi route-snapshot guard, declarative import-boundary matrix, docs link-check via a stdlib-only test that walks relative Markdown links — no network); existing full §G gate suite as regression net; release workflow exercised in a no-publish dry-run mode.

**Target Platform**: Repository CI (ubuntu + windows, Python 3.12); PyPI as the distribution target.

**Project Type**: Monorepo tooling/docs/packaging unit over the existing Python workspace — no runtime feature, no frontend change.

**Performance Goals**: CI wall-time neutrality — the new checks (metadata validation, snapshot/matrix tests, link-check) add seconds, not minutes; the release workflow runs only on tags.

**Constraints**: FR-015 (byte-identical runtime: no default change, no schema change, no dependency change, no re-exports, never convert lazy/TYPE_CHECKING imports); FR-016 (078 no-touch set while 078 is not Verified: `pyproject.toml`, `uv.lock`, root `package.json`/`package-lock.json`, `apps/**`, `packages/**`, `src/loopplane/host/**`, `src/loopplane/controller/**`, `scripts/*desktop*.ps1`, `.github/workflows/desktop.yml`, `docs/adr/0015-*`, `specs/078-*/**`, desktop tests). Constitution VII public-safety on every new file. `.specify/feature.json` and the SPECKIT agent-context blocks stay pointed at 078 until the maintainer flips the active unit (see Deviations).

**Scale/Scope**: ~15 new files (1 workflow, 1 sync-check script, 2 governance files, 1 runbook, ~6 thematic guides, ~3 contract tests, router modules) + additive edits to `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/README.md`, `.github/workflows/ci.yml`; deferred edits to `pyproject.toml` and `docs/architecture/ARCHITECTURE_AUDIT.md` ordering per story sequencing.

## Constitution Check

*GATE: Evaluated before Phase 0 research; re-checked after Phase 1 design. No violations; no complexity waiver requested.*

| Principle | Status | Notes |
|---|---|---|
| I. Spec-First Development | PASS | All work traces to spec 082 + this plan/tasks. No ADR needed: no architecture boundary, event, gateway, or storage semantics change; US5 mechanically enforces rules already normative in `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`. |
| II. Greenfield Implementation | PASS | New tooling/docs written fresh; no legacy code copied. |
| III. Harness Before Loop Automation | PASS | No scheduler/loop automation added; release workflow is CI, not runtime. |
| IV. Runtime Boundary Clarity | PASS | No ownership change. US6a re-files webapi routes into routers with an invariance guard; US5 strengthens boundary enforcement. |
| V. Tool Gateway Ownership | PASS | Gateway untouched. |
| VI. Runtime Event Bus Ownership | PASS | Events untouched; no `SCHEMA_VERSION` / `RECORD_SCHEMA_VERSION` change. |
| VII. Public-Safe Documentation | PASS | Central requirement: every new file is written for a public repository; SC-007 mandates a scan; governance docs describe gates without internal names/paths. |
| VIII. No SDK Replacement | PASS | No framework introduced. |
| IX. Reference, Not Clone | PASS | Release/governance patterns follow public PyPA/GitHub norms, re-derived for this repo. |
| X. Testable Evolution | PASS | Each story independently revertible (docs-only stories revert completely; code stories are guarded by snapshot/matrix tests written first). Rollback notes below. |

**Human gates in play (§E)** — stop and obtain maintainer approval before: the actual release cut (version bump / CHANGELOG promotion / tag / publish), configuring the PyPI trusted publisher, adding any extra (`all`/`server`) or any dev dependency (`import-linter`), flipping `.specify/feature.json` / agent-context blocks to 082, and any board edit beyond the agreed 082 row registration.

## Project Structure

### Documentation (this feature)

```text
specs/082-open-source-release-readiness/
|-- spec.md              # feature specification (authored 2026-08-08)
|-- handoff.md           # architecture analysis + execution basis for the implementing agent
|-- plan.md              # this file
|-- research.md          # Phase 0 decisions
|-- data-model.md        # Phase 1: declarative artifact shapes
|-- quickstart.md        # Phase 1: validation guide
|-- contracts/
|   |-- release-automation.md      # tag-triggered workflow contract
|   |-- boundary-gate.md           # declarative import-matrix contract
|   `-- webapi-route-snapshot.md   # route-inventory invariance contract
`-- tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
.github/workflows/
|-- ci.yml                          # EXTEND: metadata validation (twine check via uvx) after uv build   [US1]
`-- release.yml                     # NEW: tag-triggered validate -> build -> publish -> gh release      [US2]

scripts/
`-- release_sync_check.py           # NEW: stdlib-only release-sync validator (local + CI)               [US2]

GOVERNANCE.md                       # NEW: roles, decision rights, meaning of maintainer gates           [US3]
CODEOWNERS                          # NEW: load-bearing paths -> maintainer review                       [US3]
CONTRIBUTING.md                     # EXTEND: hazard map (R1/R4 cycles, guards, SS-E gates, defaults)    [US3]
README.md                           # EXTEND: badges + install wording                                   [US1]
CHANGELOG.md                        # EXTEND: additive [Unreleased] entries for this unit               [all]

docs/
|-- README.md                       # EXTEND: index the thematic guides                                  [US4]
|-- release-process.md              # NEW: human-gated release runbook                                   [US2]
`-- guides/                         # NEW: consolidated thematic guides for units 021-081                [US4]
    |-- agent-tools-and-permissions.md
    |-- autonomy-and-multi-agent.md
    |-- cost-governance.md
    |-- platform-and-deployment.md
    `-- web-ui-product.md

tests/contract/
|-- test_release_sync.py            # NEW: unit tests for scripts/release_sync_check.py                  [US2]
|-- test_docs_links.py              # NEW: stdlib link-check over docs/ relative links                   [US4]
|-- test_import_matrix.py           # NEW: declarative default-deny boundary gate                        [US5]
`-- test_webapi_route_snapshot.py   # NEW: route-inventory invariance guard (written BEFORE the split)   [US6a]

src/loopplane/webapi/
|-- app.py                          # SHRINK: create_app() composition + shared helpers only             [US6a]
`-- routers/                        # NEW: per-domain APIRouter modules (sessions, streaming, ...)       [US6a]

docs/architecture/ARCHITECTURE_AUDIT.md   # REFRESH per its own conventions                              [US7]
tests/unit/...                      # deepen only refresh-confirmed gaps                                 [US7]

# DEFERRED until 078 is Verified:
pyproject.toml                      # URLs/classifiers (+ optional approved extra)                       [US1-deferred]
src/loopplane/host/capability_manager.py  # decomposition                                                [US6b]
docs/loopplane-agent-board.md       # ADR-0015 status-text check                                         [FR-009]
```

**Structure Decision**: Single-workspace additive layout. All new code lands in `scripts/`, `tests/contract/`, `.github/workflows/`, and `docs/`; the only `src` change in this unit is the US6a router re-filing inside `src/loopplane/webapi/`, executed behind a pre-written invariance guard. Nothing in the 078 no-touch set is modified before 078 is Verified.

## Phase 0: Research Output

See [research.md](research.md). Decisions: trusted publishing (OIDC) with a no-publish dry-run mode and `skip-existing` idempotency; stdlib-only `scripts/release_sync_check.py` as the single sync authority used locally and in CI; `gh` CLI for GitHub Release creation (no third-party action); truthful badge set (CI/license/Python now, PyPI version after first publish); boundary gate reuses the existing AST-walker pattern with a declarative matrix and package auto-discovery (import-linter rejected by default as a new dep); five thematic guides consolidating units 021–081 with the existing per-layer guides left as-is; router split shape = FastAPI `APIRouter` per domain mounted by `create_app()` with an inventory snapshot captured first; audit refresh follows the audit file's own evidence-tag and snapshot conventions; docs link-check is offline (relative links only).

## Phase 1: Design Output

- Declarative artifact shapes: [data-model.md](data-model.md)
- Release workflow contract: [contracts/release-automation.md](contracts/release-automation.md)
- Boundary-gate contract: [contracts/boundary-gate.md](contracts/boundary-gate.md)
- Route-snapshot contract: [contracts/webapi-route-snapshot.md](contracts/webapi-route-snapshot.md)
- Validation guide: [quickstart.md](quickstart.md)

## Implementation Strategy

Ordered to respect story priorities and the 078 constraint; each wave is independently revertible.

### Wave 1 — Release machinery (US2, runnable immediately)

Write `scripts/release_sync_check.py` test-first (`tests/contract/test_release_sync.py`): given a tag name, assert `loopplane.__version__` equality, a matching `CHANGELOG.md` section, and emit the extracted section for release notes; exit non-zero with a precise diagnostic on any mismatch. Then add `.github/workflows/release.yml` per the contract: `v*` tag trigger only, sync-check → gates → `uv build` → metadata check → (publish step guarded by dry-run condition until the maintainer configures the trusted publisher) → `gh release create` with the extracted notes. Extend `ci.yml` with the metadata check after its existing `uv build`.

### Wave 2 — Governance (US3, runnable immediately)

`GOVERNANCE.md` (roles, decision rights, §E gate map), `CODEOWNERS` (load-bearing paths, workflows, `docs/architecture/`), `CONTRIBUTING.md` hazard-map section (R1/R4 quarantined cycles with the "do not fix" rationale, boundary-guard system, §E gates, default-off/byte-identity, public-safety checklist, English docs). Cross-link from README.

### Wave 3 — Documentation coverage (US4, runnable immediately)

Five thematic guides under `docs/guides/` consolidating units 021–081 (tools & permissions; autonomy & multi-agent; cost governance; platform & deployment; web UI product), each anchored with unit numbers and deferring to `docs/capabilities.md` / `docs/api-reference.md`. Update `docs/README.md` index. Add `tests/contract/test_docs_links.py` (offline relative-link walker) so the index cannot silently rot.

### Wave 4 — Boundary gate (US5, coordinate landing with maintainer)

`tests/contract/test_import_matrix.py`: declarative matrix `{package -> allowed loopplane-import prefixes (+ TYPE_CHECKING / function-scoped exceptions)}` seeded from `TARGET_ARCHITECTURE_BOUNDARIES.md` and the 17 existing guards; package auto-discovery over `src/loopplane/*/`; default-deny for undeclared packages; self-test fixtures proving a seeded violation and an undeclared package both fail. Existing bespoke guards untouched.

### Wave 5 — webapi decomposition (US6a, coordinate landing with maintainer)

First land `tests/contract/test_webapi_route_snapshot.py` capturing the current inventory (method, path, endpoint name, response-model identity, sorted) as the checked-in expectation. Then re-file `app.py` route groups into `src/loopplane/webapi/routers/` modules mounted by `create_app()`, preserving its keyword surface and all behavior; the snapshot, `test_webapi_boundary.py`, and the full suite prove invariance. No outward contract change — triggering §E means the wave failed.

### Wave 6 — Audit refresh + test backfill (US7)

Refresh `docs/architecture/ARCHITECTURE_AUDIT.md` against the current tree per its own conventions (snapshot commit/date, evidence tags), correcting stale rows (e.g. controller/errors tests exist since 2026-07-07). Backfill only refresh-confirmed gaps with `test_<pkg>_core`-convention tests; prove non-tautology via a temporary local mutation check.

### Wave 7 — Deferred tail (after 078 is Verified; maintainer-triggered)

`pyproject.toml` URLs/classifiers (+ the approved extra, if any); US6b `capability_manager.py` decomposition; FR-009 board ADR-0015 status-text check; then the human-gated release cut per `docs/release-process.md` (recommended `v0.5.0` covering 064–081, plus 078 if Verified).

## Rollback and Default Preservation

- Docs/governance/workflow stories: a single revert fully restores the previous state; the release workflow is inert outside `v*` tags and cannot publish until the maintainer configures the trusted publisher.
- US5/US6a: guards are pure test additions; the router re-filing is one revertable commit proven byte-equivalent at the contract level by the pre-written snapshot.
- No default, schema, dependency, or event change anywhere in this unit; removing every 082 file leaves runtime behavior identical.
- `.superpowers/**`, `openspec/**`, build outputs, and 078's in-flight files are never staged.

## Deviations from the standard /speckit-plan mechanics (documented intentionally)

1. `setup-plan.ps1` was **not** executed: its feature resolution reads `.specify/feature.json` (currently `specs/078-desktop-cowork-parity` — the active unit) and persists any `SPECIFY_FEATURE_DIRECTORY` override back into that shared file. Running it would either target 078's plan or silently flip the active-feature pointer mid-078. Its effect (template → `specs/082-.../plan.md`, path resolution) was performed manually; `.specify/feature.json` is untouched.
2. The Phase-1 "agent context update" step and the optional `after_plan` agent-context hook are **deferred**: the SPECKIT managed blocks in `AGENTS.md`/`CLAUDE.md` point at 078's plan while 078 remains the board-active unit. Flip them (via `/speckit-agent-context-update`) only when the maintainer makes 082 the active unit.

## Post-Design Constitution Check

Re-evaluated after Phase 1: all ten principles remain PASS; no Complexity Tracking entries. The only unresolved items are, by design, the §E human gates listed above (release cut, publisher configuration, optional extra/dev-dep approvals, active-unit flip).
