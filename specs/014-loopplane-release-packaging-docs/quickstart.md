# Quickstart & Validation: LoopPlane Release Packaging & Docs

Runnable validation that the release artifacts are consistent, public-safe, and buildable — all offline.
See [contracts/](./contracts) for the rules and [data-model.md](./data-model.md) for the invariants.

## Prerequisites

- Python 3.12+, the dev tooling installed (`uv sync`), and the repository checked out.
- No network access is required for any step below.

## 1. Quality gates (the canonical four)

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

**Expected**: all four pass — the same gates CI runs (SC-003).

## 2. Packaging consistency + version + typing (US1)

```powershell
uv run pytest tests/contract/test_packaging.py -q
```

**Expected**: green — metadata complete; **no** literal `[project] version` (single source via
`loopplane.__version__`); `src/loopplane/py.typed` present and shipped; every `loopplane` subpackage
imports (SC-001/006).

## 3. Build the distribution (offline)

```powershell
uv build
```

**Expected**: a source distribution and a wheel are produced under `dist/` with no network access and no
new runtime dependency; the wheel contains `loopplane/py.typed` (FR-004; SC-001). *(Built artifacts in
`dist/` are not committed.)*

## 4. Drift-proof API reference (US2)

```powershell
uv run pytest tests/contract/test_api_reference.py -q
```

**Expected**: green — every `loopplane` package that declares `__all__` is documented in
`docs/api-reference.md`, and each package's documented public names **==** its `__all__` (no drift, every
layer represented), metadata-only (SC-002).

## 5. Docs & examples indexes (US3)

```powershell
uv run pytest tests/contract/test_docs_examples_index.py -q
```

**Expected**: green — `docs/README.md` links every `docs/*.md` guide; `examples/README.md` lists every
`examples/*.py`; no missing or dangling entry; the README's quickstart/docs links resolve (SC-005).

## 6. CI gate definition (US4)

```powershell
uv run pytest tests/contract/test_ci_gates.py -q
```

**Expected**: green — `.github/workflows/ci.yml` runs format-check + lint + strict types + tests + an
offline build, with no secret (SC-003).

## 7. Release-readiness: changelog + public-safety audit (US5)

```powershell
uv run pytest tests/contract/test_changelog.py tests/contract/test_public_safety.py -q
```

**Expected**: green — the changelog has the recognized structure and covers units 001–013; the
release-readiness checklist enumerates the gates; the **repository-wide** public-safety audit reports
**0 findings** across the tree, and `PHASE14_TARGETS` is clean (SC-004/005).

## 8. Full suite

```powershell
uv run pytest
```

**Expected**: the entire suite is green, including every prior layer's tests and the new 014 contract
tests — confirming the release artifacts were added **without** changing any runtime behavior (NFR-001).

## Notes

- `python -m build` is a documented alternative to `uv build` (requires `pip install build`).
- **License is deferred**: the build succeeds without a `LICENSE`; adding the license (file + `license`
  field + classifier) is the single maintainer gate in [`docs/release-readiness.md`](../../docs/release-readiness.md).
