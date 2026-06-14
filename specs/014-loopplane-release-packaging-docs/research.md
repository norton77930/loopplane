# Phase 0 Research: LoopPlane Release Packaging & Docs

All decisions resolve to **public-safe, deterministic, offline, no-new-runtime-dependency** outcomes over
the **existing** tree. Starting state (verified): hatchling backend; `pyproject.toml` already has
name/version(`0.1.0`)/description/readme/requires-python/deps/extras; `src/loopplane/__init__.py` already
defines `__version__ = "0.1.0"`; a CI workflow already runs the four gates on ubuntu+windows/py3.12 via
uv; README is minimal; **no** `LICENSE`, `CHANGELOG.md`, or `py.typed`.

## D1 — Distribution build mechanism

- **Decision**: Build the sdist + wheel with **`uv build`** (the repo already standardizes on uv;
  CI uses `uv sync`/`uv run`). It needs **no new dependency** and runs offline.
- **Rationale**: uv has a built-in build frontend; using it avoids adding the `build` package and keeps
  the build identical to the CI toolchain.
- **Alternatives considered**: `python -m build` (clean, standard, but requires adding `build` as a dev
  tool — documented as a fallback, not the default); invoking hatchling directly (lower-level, no
  benefit over `uv build`).

## D2 — Single-source version

- **Decision**: Make **`src/loopplane/__init__.py` the single source** of the version. Set
  `[project] dynamic = ["version"]` and `[tool.hatch.version] path = "src/loopplane/__init__.py"` so the
  packaging version is **derived from** `__version__`. The literal `version = "0.1.0"` line under
  `[project]` is removed (it is the current duplicate).
- **Rationale**: A code-first single source works in a bare checkout (a plain literal, no install needed),
  is hatchling-native, and removes the drift between the two current `0.1.0` literals.
- **Alternatives considered**: keep the literal in `pyproject.toml` and derive `__version__` at runtime
  via `importlib.metadata.version("loopplane")` — rejected: it raises `PackageNotFoundError` in a
  non-installed source tree and makes the in-code version depend on install metadata.
- **Test**: `test_packaging.py` asserts there is **no** `version = "..."` under `[project]`, that
  `dynamic` includes `version`, that `[tool.hatch.version].path` points at `__init__.py`, and that
  `loopplane.__version__` is a non-empty version string.

## D3 — Ship type information (`py.typed`)

- **Decision**: Add an empty `src/loopplane/py.typed` (PEP 561) and ensure the wheel ships it and **every**
  subpackage via an explicit `[tool.hatch.build.targets.wheel] packages = ["src/loopplane"]` (and a
  `force-include`/`artifacts` entry for `py.typed` if hatchling does not include it by default).
- **Rationale**: Downstream type-checkers only treat `loopplane` as typed when the marker ships inside the
  installed package.
- **Test**: `test_packaging.py` asserts the marker file exists and that the wheel build config declares it
  as package data (and, in the build smoke, that it appears in the built wheel).

## D4 — Drift-proof public API reference

- **Decision**: `docs/api-reference.md` documents **every `loopplane` package that declares `__all__`**
  (currently 25 — the 12 roadmap layer packages plus the Phase-1 foundation packages: `controller`,
  `gateway`, `events`, `model`, `memory`, `checkpoint`, `artifacts`, `approval`, `observability`, `loop`,
  `tools`, `skills`, `adapters.mcp`). Each package gets a short intro and a list of its public names, each
  with a one-line description. `test_api_reference.py` **discovers** the packages with `__all__`, imports
  each, and asserts the reference lists **exactly** that package's `__all__` (set equality per package) —
  so neither the code nor the doc can silently drift.
- **Rationale**: `__all__` is the package's own public-export declaration; a per-package bijection with the
  doc is the strongest, fully deterministic anti-drift guarantee (SC-002) and guarantees every shipped
  layer is represented.
- **Alternatives considered**: documenting only the 12 named layers (rejected — would leave public
  foundation exports undocumented and the "every shipped layer" guarantee weaker); subset check `listed ⊆
  __all__` (rejected — allows the doc to omit names, i.e., silent under-documentation).
- **Public-safety**: names + one-line descriptions only — never private internals, source, or values.

## D5 — Docs index, examples index, getting-started, README

- **Decision**: `docs/README.md` is the docs index (renders when browsing `docs/` on the host), linking
  **every** `docs/*.md` guide. `examples/README.md` lists **every** `examples/*.py` with a one-line
  description and its `python examples/<name>.py` run command. `docs/getting-started.md` shows install +
  the smallest end-to-end example + links out. `README.md` becomes release-quality (overview, install,
  quickstart link, a layer map, docs links, a License section). `test_docs_examples_index.py` asserts each
  index lists exactly the files present (no missing entry, no entry pointing at a missing file).
- **Rationale**: Indexes checked against the file tree stay correct as the repo evolves; the host renders
  `README.md` files as folder landing pages.

## D6 — License (deferred to the maintainer)

- **Decision**: This unit does **not** select or author a software license. The build does **not** bind a
  `LICENSE` file (so `uv build` succeeds now with no license decision). The license is the **single
  deferred maintainer gate**, captured in `docs/release-readiness.md` (add `LICENSE`, set
  `license = {file = "LICENSE"}` / the SPDX id, add the `License ::` classifier). `README.md` has a
  "License" section that names this pending decision.
- **Rationale**: A software license is a legal/IP decision that is genuinely the maintainer's, not an
  automatable default. Deferring it keeps the autopilot unblocked while keeping the package buildable.
- **Consequence for FR-001**: the "license reference" is satisfied as a documented checklist gate +
  README section, not a binding `pyproject` license field this unit sets.

## D7 — Public-safe packaging metadata (authors, URLs, classifiers, keywords)

- **Decision**: Use **public-safe, non-PII** metadata: `authors = [{name = "LoopPlane contributors"}]`
  (no personal email), project URLs pointing at the public repository home, trove `classifiers`
  (Development Status, Intended Audience, Programming Language :: Python :: 3.12, Typed; **no** `License ::`
  classifier until the license is chosen), and descriptive `keywords` (agent, runtime, loop, tool-gateway,
  events). `requires-python = ">=3.12"`, `readme = "README.md"` stay.
- **Rationale**: A public package needs authors/URLs/classifiers; using project-level attribution avoids
  committing a personal email (PII) and keeps the metadata public-safe (Constitution VII). The maintainer
  can personalize attribution later.
- **Test**: `test_packaging.py` asserts these fields are present and that no obvious PII/secret pattern
  appears (covered also by the repo-wide public-safety scan).

## D8 — Changelog format

- **Decision**: `CHANGELOG.md` follows **Keep a Changelog** with a single `0.1.0` release summarizing the
  shipped layers (units 001–013) at a high level under `### Added`, public-safe.
- **Rationale**: A recognized, parseable structure; `test_changelog.py` asserts the top heading, a version
  entry, coverage of the released units/layers, and no private reference.

## D9 — CI readiness (verify + harden the existing workflow)

- **Decision**: The existing `.github/workflows/ci.yml` already runs the four canonical gates (ruff
  `format --check`, ruff `check`, mypy, pytest) on ubuntu+windows/py3.12 via uv. This unit **verifies**
  it and **adds an offline `uv build` job** (build the sdist+wheel — no upload) as packaging hardening.
  Local gate commands are documented (in `getting-started.md` / `release-readiness.md`).
  `test_ci_gates.py` parses the workflow and asserts the four gate commands (and the build) are present.
- **Rationale**: The gates already exist; the unit's job is to verify + encode them as a checked contract
  and confirm the package builds in CI. No secret, deterministic, offline.
- **Alternatives considered**: a publish/upload job — **reserved** (out of scope); a docs-build/site job —
  reserved.

## Cross-cutting

- **Determinism / offline (NFR-003)**: every artifact is reproducible from the committed tree; the build
  and gates run offline; no network or environment-specific config.
- **Non-breaking (NFR-001)**: no layer `__all__`, no runtime module, and no 001/002 contract is edited;
  the API-reference bijection doubles as a guard that the public surface is unchanged.
- **Public-safe (NFR-004)**: the repo-wide audit + `PHASE14_TARGETS` + non-PII metadata keep every
  committed file public-safe.
