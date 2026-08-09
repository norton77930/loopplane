# Contract: Declarative Import-Boundary Gate (US5)

Normative contract for `tests/contract/test_import_matrix.py` (closes risk R10).

## Declaration

- One matrix, defined in the test module, is the single source of truth: `{package -> BoundaryMatrixEntry}` per [data-model.md](../data-model.md) §1 (runtime / TYPE_CHECKING-only / function-scoped allow-sets + owning-rule note).
- Seeded from `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` and the 17 existing bespoke guards. Where they disagree with current code, current code + existing guards win and the discrepancy is reported (not silently absorbed).

## Discovery and default-deny

- Packages are discovered mechanically from `src/loopplane/*/` plus top-level modules (`context`, `errors`, `fairness`, `__init__`).
- A discovered package with no matrix entry → **fail** (default-deny). A matrix entry with no corresponding package → **fail** (orphan). This is the property the bespoke guards lack: a new package cannot ship unguarded.

## Enforcement semantics

- AST-based (reuse the proven walker approach from `tests/contract/test_tools_boundary.py`): classify each `loopplane.*` import as runtime / TYPE_CHECKING / function-scoped and check it against the corresponding allow-set.
- Failures name file, line, the offending edge, and the owning rule note — actionable for an outside contributor.
- The gate MUST NOT import the packages under test (static analysis only), so it cannot be affected by optional-extra availability.

## Negative self-tests (anti-false-green)

Required in the same module: (a) a seeded forbidden edge on synthetic source fails; (b) a synthetic undeclared package fails; (c) a TYPE_CHECKING-only edge used at runtime fails. Follows the repository's established practice that AST guards must prove they can fail.

## Relationship to existing guards

Purely additive in this unit: the 17 bespoke guard tests are not modified, weakened, or retired here. Retirement is a separate later unit after the matrix has soaked.

## Approved alternative

If the maintainer approves the dev dependency (§E), `import-linter` contracts may replace the hand-rolled walker — the declaration, default-deny, and negative self-test requirements above still apply unchanged.
