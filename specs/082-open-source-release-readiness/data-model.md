# Data Model: Open-Source Release Readiness

This unit introduces no runtime data model. Its "entities" are declarative artifacts consumed by tests and CI. Shapes below are normative for the implementing tasks; exact field names may be refined at implementation as long as the semantics hold.

## 1. BoundaryMatrixEntry (US5 — `tests/contract/test_import_matrix.py`)

One entry per discovered `loopplane` package (auto-discovery over `src/loopplane/*/` plus top-level modules).

| Field | Type | Semantics |
|---|---|---|
| `package` | str | Package name relative to `loopplane` (e.g. `gateway`, `webapi`) or top-level module (`context`, `errors`, `fairness`) |
| `allow_runtime` | set[str] | `loopplane.*` prefixes importable at runtime (module top level) |
| `allow_type_checking` | set[str] | Prefixes importable only under `TYPE_CHECKING` |
| `allow_function_scoped` | set[str] | Prefixes importable only inside function bodies (lazy) |
| `notes` | str | Pointer to the owning rule (e.g. `TARGET_ARCHITECTURE_BOUNDARIES.md` block, R1/R4) |

**Validation rules**: every discovered package MUST have exactly one entry (missing → fail; orphan entry for a non-existent package → fail); any import not matched by the applicable allow-set → fail naming file, line, edge, and rule. Matrix content is seeded from `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` and the 17 existing guard tests; discrepancies discovered while seeding are reconciled in favor of current code + existing guards and noted in the completion report.

## 2. RouteSnapshotEntry (US6a — `tests/contract/test_webapi_route_snapshot.py`)

Captured from the assembled FastAPI app **before** the router split; fields chosen to be refactor-neutral (module moves must not change them) yet contract-sensitive.

| Field | Type | Semantics |
|---|---|---|
| `methods` | sorted list[str] | HTTP methods |
| `path` | str | Route path including `api_prefix` |
| `name` | str | Endpoint function `__name__` (module-independent) |
| `response_model` | str \| None | Response model class name |
| `status_code` | int \| None | Declared status code |

**Validation rules**: the sorted entry list MUST be byte-identical before/after the split; additionally the canonicalized `app.openapi()` JSON (sorted keys) MUST compare equal — the OpenAPI document is the actual outward contract, and its equality is the §E non-trigger proof.

## 3. ReleaseSyncResult (US2 — `scripts/release_sync_check.py`)

| Field | Type | Semantics |
|---|---|---|
| `tag` | str | Input ref, `vX.Y.Z` form required |
| `version` | str | `X.Y.Z` parsed from tag |
| `init_version_ok` | bool | `loopplane.__version__ == version` |
| `changelog_section_ok` | bool | `CHANGELOG.md` has a `[X.Y.Z]` section with a valid calendar date |
| `board_status_ok` | bool | every three-digit unit referenced by the released section exists on the board with status `Verified` |
| `changelog_coverage_ok` | bool | the reverse direction: every unit the board marks `Verified` has a `- **NNN**` entry somewhere in `CHANGELOG.md`. **Added after this unit landed** (2026-08-22), not part of its delivery — the unit's own landing exposed the gap when units 079 and 083 shipped undocumented and passed every gate |
| `notes` | str | The extracted CHANGELOG section (stdout on success; consumed by `gh release create`) |
| exit code | int | 0 only if all checks pass; non-zero with one-line diagnostics per failure |

**Validation rules**: no network, stdlib only; unit-status board rules are mechanically checked. API-reference/capability/gap-analysis currency and ADR-reference review stay in the runbook checklist, and the script says so in its failure-help text.

## 4. GuideIndexEntry (US4 — `docs/README.md` + `docs/guides/`)

| Field | Semantics |
|---|---|
| Guide title + path | One of the five thematic guides under `docs/guides/` |
| Covered units | Unit-number anchors listed in the guide header |
| Authority links | Each guide links `docs/capabilities.md` and `docs/api-reference.md` as the normative sources |

**Validation rules**: every capability category in `docs/capabilities.md` maps to at least one indexed guide (manual check recorded in the completion report); all relative links resolve (`tests/contract/test_docs_links.py`).
