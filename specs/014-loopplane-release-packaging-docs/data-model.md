# Data Model: LoopPlane Release Packaging & Docs

This unit ships **release artifacts** (configuration and documentation), not runtime data. The "entities"
below are those artifacts and the **consistency invariants** the contract tests enforce. Nothing here is
a runtime type; nothing changes a public API.

## Packaging metadata (`pyproject.toml` `[project]`)

- **Fields (present)**: `name = "loopplane"`, `description`, `readme = "README.md"`,
  `requires-python = ">=3.12"`, `dependencies` (unchanged: `anyio`, `pydantic`, `jsonschema`),
  `optional-dependencies` (`mcp`, `otel`, `web` — unchanged).
- **Fields (added by this unit)**: `authors = [{name = "LoopPlane contributors"}]` (no PII),
  `keywords`, `classifiers` (Development Status, Intended Audience, `Programming Language :: Python :: 3.12`,
  `Typing :: Typed`; **no** `License ::` classifier yet), `[project.urls]` (public repository home),
  `dynamic = ["version"]`.
- **Removed**: the literal `version = "0.1.0"` under `[project]` (the duplicate — superseded by D2).
- **Invariants** (`test_packaging.py`): all listed present fields exist; `version` is **not** a literal
  under `[project]`; `dynamic` contains `"version"`; `dependencies` set is unchanged (no new runtime dep);
  `optional-dependencies` keys are preserved.

## Version source

- **Source of truth**: `loopplane.__version__` in `src/loopplane/__init__.py` (a plain string literal).
- **Derivation**: `[tool.hatch.version] path = "src/loopplane/__init__.py"` makes the packaging version
  read from it.
- **Invariants**: `loopplane.__version__` is a non-empty version string; `[tool.hatch.version].path`
  points at `__init__.py`; exactly one source (no `[project] version` literal).

## Type marker

- **Artifact**: `src/loopplane/py.typed` (empty PEP 561 marker).
- **Packaging**: declared so the wheel ships it (wheel `packages = ["src/loopplane"]` and/or a
  `force-include`/`artifacts` entry).
- **Invariants**: the file exists; the wheel build config ships it as package data.

## API reference entry

- **Shape**: per public package — the package name, a short intro, and its public names (each with a
  one-line description).
- **Source**: each `loopplane` package that declares `__all__` (discovered, currently 25).
- **Invariants** (`test_api_reference.py`): the set of documented packages **==** the set of packages that
  declare `__all__`; for each package, the set of documented public names **==** that package's `__all__`
  (per-package bijection — no drift, no omission); entries carry names + descriptions only (metadata-only).

## Docs index / examples index entry

- **Docs index** (`docs/README.md`): one link per `docs/*.md` guide (excluding the index itself).
- **Examples index** (`examples/README.md`): one row per `examples/*.py` — a one-line description + the
  `python examples/<name>.py` run command.
- **Invariants** (`test_docs_examples_index.py`): the set of linked guides **==** the set of `docs/*.md`
  files (minus the index); the set of listed examples **==** the set of `examples/*.py` files; every
  link/entry targets a file that exists (no dangling), and no file is missing from its index.

## README

- **Required sections**: overview; install; a quickstart link (→ `docs/getting-started.md`); a layer map;
  links to the docs (→ `docs/README.md`); a License section (naming the deferred license gate).
- **Invariants**: the quickstart link and the docs link resolve to files that exist (checked by the index
  test or a README link check); public-safe.

## Changelog

- **Shape**: Keep a Changelog — a top `# Changelog` heading and a `## [0.1.0]` release with an `### Added`
  summary covering the shipped layers (units 001–013).
- **Invariants** (`test_changelog.py`): the top heading and a version section exist; the released
  units/layers are referenced; no private reference / internal name / path / secret.

## Release-readiness checklist

- **Shape**: `docs/release-readiness.md` — an enumerated gate list: distribution builds; quality gates
  green; public-safety audit clean; **`LICENSE` present** (the deferred maintainer gate); changelog
  current.
- **Invariants**: the checklist enumerates these gates (referenced by `test_changelog.py` or a dedicated
  assertion); public-safe.

## CI gate definition

- **Shape**: `.github/workflows/ci.yml` — steps running ruff `format --check`, ruff `check`, mypy, pytest,
  and an offline `uv build`.
- **Invariants** (`test_ci_gates.py`): each canonical gate command and the build step appear; no secret is
  referenced.

## Public-safety audit

- **Scope**: every committed file (the existing repo-wide `test_committed_files_are_public_safe`) plus
  `PHASE14_TARGETS` (the new 014 docs + `specs/014-...`) scanned pre-commit.
- **Invariant**: **0 findings** across the tree (secrets, private paths, internal names, IPs, tokens).
