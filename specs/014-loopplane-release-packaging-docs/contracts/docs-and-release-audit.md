# Contract: Docs, CI & Release Audit

Defines the documentation, CI-gate, and release-audit contracts: a **drift-proof** public API reference,
consistent docs/examples indexes, a public-safe changelog and release-readiness checklist, the canonical
CI gates, and a clean repository-wide public-safety audit (FR-010–FR-042; NFR-003/004).

## Public API reference (`docs/api-reference.md`)

- Documents **every** `loopplane` package that declares `__all__` (the public surface — currently 25:
  the 12 roadmap layer packages plus the Phase-1 foundation packages).
- For each package: a short intro and its public names, **each** with a one-line description.
- Metadata-only: names + descriptions, never private internals, source, values, or private references.

**Drift rule (`tests/contract/test_api_reference.py`)**: discover the packages that declare `__all__`;
import each; assert the set of documented packages **==** that set, and for each package the set of
documented public names **==** its `__all__` (per-package **bijection**). Any added/removed/renamed public
name that the doc does not mirror — and any documented name not in `__all__` — fails the test. This also
guards NFR-001: a change to any layer's public surface would break the build until reconciled.

## Docs index & examples index

- `docs/README.md` links **every** `docs/*.md` guide (excluding itself).
- `examples/README.md` lists **every** `examples/*.py` with a one-line description and a
  `python examples/<name>.py` run command.

**Consistency rule (`tests/contract/test_docs_examples_index.py`)**: the linked guide set **==** the
`docs/*.md` set (minus the index); the listed example set **==** the `examples/*.py` set; every link/entry
targets an existing file (no dangling) and no file is missing from its index.

## README & getting-started

- `README.md`: overview; install; a quickstart link → `docs/getting-started.md`; a layer map; a docs link
  → `docs/README.md`; a License section (naming the deferred license gate). Public-safe.
- `docs/getting-started.md`: install the package, run the smallest end-to-end example, and link out to the
  per-layer guides and examples.

## CI gates (`.github/workflows/ci.yml`)

- Runs the canonical gates: ruff `format --check`, ruff `check`, `mypy` (strict), and `pytest` — plus an
  **offline `uv build`** job (build only; no upload). On Python 3.12, no secret, deterministic.
- The same gate commands are documented for local use.

**Rule (`tests/contract/test_ci_gates.py`)**: the workflow contains each canonical gate command and the
build step; no secret is referenced.

## Changelog (`CHANGELOG.md`)

- Keep a Changelog structure: a `# Changelog` heading and a `## [0.1.0]` release with an `### Added`
  summary covering the shipped layers (units 001–013). Public-safe.

**Rule (`tests/contract/test_changelog.py`)**: the heading and version section exist; the released
units/layers are referenced; no private reference / internal name / path / secret.

## Release-readiness checklist (`docs/release-readiness.md`)

- Enumerates the gates that MUST pass before release: the distribution builds; the quality gates are
  green; the public-safety audit is clean; a **`LICENSE` file is present** (the deferred maintainer gate);
  the changelog is current. Public-safe.

## Public-safety audit

- The existing `tests/contract/test_public_safety.py::test_committed_files_are_public_safe` scans **every**
  committed file; `PHASE14_TARGETS` (the new 014 docs + `specs/014-...`) is scanned pre-commit.
- **Pass state**: 0 findings (no secret, private path, internal name, IP, or token) across the tree
  (FR-040, SC-004).

## Non-breaking guarantee (cross-cutting, NFR-001/002)

- No layer's public `__all__` and no runtime module is edited; the only code additions are the version
  literal (kept) and `src/loopplane/py.typed`.
- The runtime `dependencies` set is unchanged (no new runtime dependency); `test_packaging.py` asserts it.
