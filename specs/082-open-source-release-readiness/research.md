# Phase 0 Research: Open-Source Release Readiness

All Technical Context unknowns resolved. Format: Decision / Rationale / Alternatives considered.

## R1. Package publishing mechanism

- **Decision**: PyPI **trusted publishing** (OIDC) from a dedicated GitHub Actions release workflow, using the standard PyPA publish action, with `skip-existing` enabled for idempotent re-runs. Until the maintainer configures the index-side trusted publisher, the workflow runs in a no-publish dry-run mode (build + validate + notes only).
- **Rationale**: No long-lived credentials in the repository or its secrets; idempotency makes partial-failure recovery safe; the dry-run mode lets the workflow merge and be exercised before the maintainer completes the §E-gated index configuration. The name `loopplane` was verified unclaimed on PyPI on 2026-08-08 (JSON API 404) — reservation is a maintainer action.
- **Alternatives**: API-token + `twine upload` (rejected: long-lived secret, manual rotation); manual local publishing (rejected: unrepeatable, no audit trail).

## R2. Release-sync validation

- **Decision**: A single stdlib-only script `scripts/release_sync_check.py`, unit-tested, used both locally (runbook) and as the first job of the release workflow. Given a `vX.Y.Z` ref it asserts: `loopplane.__version__ == X.Y.Z`; `CHANGELOG.md` contains a `[X.Y.Z]` section with a date; and it prints that section to stdout for release notes. Non-zero exit with a precise diagnostic on any mismatch. Board-row expectations from `docs/architecture/RELEASE_SYNC_RULES.md` are validated as far as they are mechanically checkable; the rest stays in the runbook checklist.
- **Rationale**: One authority for the sync rules, testable in pytest, no YAML-embedded logic duplicated across workflows, no new dependency.
- **Alternatives**: Inline workflow shell steps (rejected: untestable, drifts); a third-party changelog action (rejected: new supply-chain surface for trivial logic).

## R3. GitHub Release creation

- **Decision**: `gh release create` in the workflow, fed by the section extracted by `release_sync_check.py`.
- **Rationale**: `gh` ships on hosted runners; avoids adding a third-party action for a one-liner.
- **Alternatives**: `softprops/action-gh-release` (workable, rejected to minimize third-party actions); manual releases (rejected).

## R4. README badges

- **Decision**: Add now: CI workflow status, MIT license, Python 3.12+. Add after first publish: PyPI version badge. Wording in Install stays truthful ("publication pending" until it isn't).
- **Rationale**: Badges must never claim what is not live (Constitution VII honesty norm applied outward).
- **Alternatives**: Full badge set immediately (rejected: PyPI badge would 404/mislead).

## R5. Convenience extra

- **Decision**: Defer to the maintainer (§E: new extras). Recommendation recorded: `all` = union of the nine existing extras. Fallback if not approved: an extras matrix table in README ("which extras for which deployment").
- **Rationale**: Extras change the installable surface — explicitly §E-gated; the docs fallback removes the usability pain either way. Also note: any `pyproject.toml` edit is deferred until 078 is Verified (Stage-B byte binding), so this decision is not on the critical path.
- **Alternatives**: Add `all` unilaterally (forbidden by §E); do nothing (rejected: install ergonomics is a known friction).

## R6. Import-boundary gate (risk R10)

- **Decision**: A declarative, table-driven pytest contract test (`tests/contract/test_import_matrix.py`) reusing the AST-walking approach proven in `tests/contract/test_tools_boundary.py`: matrix maps each `loopplane` package to allowed `loopplane.*` import prefixes with explicit TYPE_CHECKING / function-scoped exception annotations; packages are auto-discovered from `src/loopplane/*/`; an undeclared package fails closed. Negative self-tests (seeded violation fixture; synthetic undeclared package) prove the gate is live. The 17 existing bespoke guards keep running unchanged; retirement is a later unit.
- **Rationale**: Closes "new package ships unguarded" with zero new dependencies; the matrix doubles as machine-checked documentation of `TARGET_ARCHITECTURE_BOUNDARIES.md`; negative self-tests follow the repo's established anti-false-green practice.
- **Alternatives**: `import-linter` (clean, but a new dev dependency → §E; recorded as the approved-alternative if the maintainer prefers it); grimp (same objection); do nothing (rejected: R10 stands).

## R7. Thematic documentation guides

- **Decision**: Five consolidated guides under `docs/guides/` — agent tools & permissions (033, 034, 036, 038, 039, 044–047, 052, 054, 065–066, 069); autonomy & multi-agent (013, 043, 048–051); cost governance (040–042, 053, 055, 062–064, 068); platform & deployment (011, 022, 056–061, 067, 071–072); web UI product (018, 023, 025–032, 074–077, 080–081). Provider units (035, 037, 070) extend the EXISTING `docs/model-providers.md` rather than a new guide; other categories already served by ≤020 layer guides (runtime core, hosts, desktop) are verified via the index-mapping check instead of new pages. Guides carry unit anchors and defer to `docs/capabilities.md` / `docs/api-reference.md` (trust ladder). `docs/README.md` indexes them. An offline relative-link walker test keeps the index honest.
- **Rationale**: One page per unit (60+ pages) would be unmaintainable; five thematic on-ramps match how outside users actually approach the product. Offline link-check avoids network flakiness and new deps.
- **Alternatives**: Per-unit pages (rejected: volume, drift); "read capabilities.md" alone (rejected: reference table, not an on-ramp); external docs site (out of scope).

## R8. webapi decomposition shape

- **Decision**: FastAPI `APIRouter` modules under `src/loopplane/webapi/routers/` (sessions, streaming/live, interaction, capabilities, inspect, cost, misc: models/uploads/commands), mounted by `create_app()` which keeps its exact keyword surface and shared helpers. Before any re-filing, land `tests/contract/test_webapi_route_snapshot.py` capturing the sorted route inventory (HTTP method, path, endpoint name, response-model identity) as the checked-in expectation.
- **Rationale**: Router-per-domain is idiomatic FastAPI and directly answers risk R11; snapshot-first makes "byte-identical outward contract" a test outcome instead of a review claim.
- **Alternatives**: Leave as-is (rejected: 1.27k-line hotspot named by the risk register); split by HTTP verb or file-size heuristics (rejected: arbitrary seams).

## R9. Architecture-audit refresh method

- **Decision**: Refresh `docs/architecture/ARCHITECTURE_AUDIT.md` following its own conventions (read-only snapshot, evidence tags `[RO-VERIFIED]`/`[INFERRED]`/`[UNVERIFIED]`, snapshot commit + date), correcting rows proven stale (controller/errors/engineering test files exist since 2026-07-07) and re-verifying the test-gap table against `tests/`. Backfill tests only for gaps the refresh confirms.
- **Rationale**: The audit is past its own ~10-unit refresh window; backfilling against a stale gap list wastes effort on solved problems (verification-before-work).
- **Alternatives**: Backfill from the frozen table (rejected: at least one row already disproven); delete the audit (rejected: it is load-bearing for onboarding).

## R10. Link-checking approach

- **Decision**: `tests/contract/test_docs_links.py` — stdlib-only walker over `docs/**/*.md` (plus README) validating relative links and intra-repo anchors; external URLs are collected but not fetched.
- **Rationale**: Deterministic, offline, zero deps; external-URL fetching in CI is flaky and a different concern.
- **Alternatives**: lychee/markdown-link-check (rejected: new toolchain deps for marginal gain).
