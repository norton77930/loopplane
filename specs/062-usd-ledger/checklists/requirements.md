# Specification Quality Checklist: Durable USD Ledger

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-21
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

- **ADR 0010 (authored at plan; covers 062+063)** — the four G22 Phase C forks are SETTLED at design
  (no re-consult): (1) a SEPARATE `loopplane.ledger` package (not CheckpointStore — wrong shape); (2)
  File+SQLite+Postgres backends; (3) cross-PROCESS atomicity only on Postgres (SQLite/File
  single-process-honest); (4) exact Decimal. (063's fork — extend BudgetChecker + fail-open — is also
  in ADR 0010.)
- **Reuse-first**: mirrors 060's `loopplane.checkpoint` (Protocol-over-backends, the three backends,
  the per-key `anyio.Lock`, `_connect()` table-create, ADR 0008's sync thread-bridge, the EXISTING
  `loopplane[postgres]` extra — no new dependency). Exact-Decimal money from 053/055.
- **Atomicity is the load-bearing property** (FR-002, SC-002): concurrent same-`(principal,month)`
  adds (real under 061's TenantHostPool) must never lose an increment — the concurrent test is the
  key one. Postgres `ON CONFLICT … RETURNING` is cross-process-safe; SQLite/File are
  single-process-honest (documented, not silent).
- **Money precision** (FR-004): exact `Decimal` (TEXT/NUMERIC), never float — float silently corrupts
  a money ledger.
- **Store only**: no enforcement / loop / budget / event change here (that is unit 063);
  default-unused. Offline-safe tests (a faithful Postgres stub; no running DB). DSN/principal_id are
  public-safe.
- **Public-safety reminder**: `test_committed_files_are_public_safe` scans git-tracked files; use
  benign placeholders in tests (no `secret = "..."` DSN literals — cf. the 060 → da618da fix).
- All items pass; spec is ready for `/speckit-plan` (which authors ADR 0010).
