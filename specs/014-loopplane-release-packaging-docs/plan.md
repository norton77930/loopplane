# Implementation Plan: LoopPlane Release Packaging & Docs

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-loopplane-release-packaging-docs/spec.md`

## Summary

Bring the completed roadmap (the Phase-1 runtime foundation, the Host Interface, and the eleven additive
layers 003–013) to **public release quality** — *without changing any runtime behavior or any
established public contract*. This is a **packaging, documentation, verification, and CI** unit. It
finalizes the packaging metadata, consolidates the version to a **single source of truth**, ships a PEP
561 `py.typed` marker, and adds a **drift-proof public API reference**, a release-quality README, a
getting-started guide, docs/examples indexes, a public-safe changelog, a release-readiness checklist,
and a repository-wide public-safety audit — and verifies the existing CI runs the canonical quality
gates. The **only code-level additions** are the `py.typed` marker and the version single-sourcing; every
layer's public surface (`__all__`) and all runtime behavior are untouched. Design detail lives in
[research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts), and
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–13). Build backend: **hatchling** (already
configured). Tooling standardized on **uv** (the CI already uses `uv sync` / `uv run`).

**Primary Dependencies**: **No new runtime dependency** (NFR-002). The runtime deps stay `anyio`,
`pydantic`, `jsonschema`; the optional extras (`mcp`, `otel`, `web`) are preserved. The distribution is
built with **`uv build`** (built into the existing uv toolchain — adds nothing), with `python -m build`
documented as an alternative. Docs, the API reference, and CI use existing dev tooling (ruff, mypy,
pytest) only.

**Storage**: None — this unit ships files (packaging config, docs, a marker, tests), not runtime state.

**Testing**: pytest. New **contract** suites under `tests/contract/` verify, deterministically and
offline, the packaging metadata, the API-reference/docs/examples consistency (drift-proof), the CI gate
definition, and the changelog structure; the existing repo-wide public-safety scan is the final audit.
No new runtime code path is added, so there is nothing new to unit/integration test beyond consistency.

**Target Platform**: A cross-platform, embeddable Python library distributed as an sdist + wheel; the CI
matrix is ubuntu + windows on Python 3.12 (already in place).

**Project Type**: single library package — packaging + documentation hardening over the existing tree
(no new `src/loopplane/<layer>/` package, no frontend, no transport).

**Performance Goals**: Not a throughput target; **determinism / reproducibility** of every artifact from
the committed tree (NFR-003), **drift-proof** docs (SC-002/005), and a **clean public-safety audit**
(SC-004) are the goals.

**Constraints**: strictly additive and **non-breaking** — no established public contract (001/002 or any
layer `__all__`) and no runtime behavior changes (NFR-001); **no new runtime dependency** (NFR-002);
every artifact reproducible offline with no environment-specific config (NFR-003); public-safe + English
(NFR-004); consistency verified by in-process tests (NFR-005).

**Scale/Scope**: packaging metadata + version single-sourcing + a `py.typed` marker; six documentation
artifacts (README, getting-started, docs index, API reference, examples index, release-readiness
checklist) + a changelog; CI verification (+ an offline build job); four–five contract test modules and a
`PHASE14` public-safety target. **No layer public API is modified; no runtime behavior changes.**

## Scope of Changes (what this unit MAY touch)

This unit is *packaging and documentation*, so — unlike the layer units — it edits a few repository-level
configuration and doc files. These are **not** public API contracts and are explicitly in scope:

- `pyproject.toml` — packaging **metadata** (authors, keywords, classifiers, URLs) and **version
  single-sourcing** (`dynamic = ["version"]` + `[tool.hatch.version]`), plus an explicit wheel
  `packages`/`force-include` so `py.typed` and every subpackage ship. *No runtime dependency is added.*
- `src/loopplane/__init__.py` — remains the **single source** of `__version__` (already present; kept as
  the canonical literal). No public symbol is added or changed.
- `src/loopplane/py.typed` — **new** empty PEP 561 marker (the only new source file).
- `README.md`, `CHANGELOG.md`, `docs/*.md`, `examples/README.md` — documentation.
- `.github/workflows/ci.yml` — **verified** to run the canonical gates; an offline `uv build` job is
  added as packaging hardening. The gate set is unchanged.

**Explicitly NOT touched**: any layer's public surface (`src/loopplane/<layer>/__init__.py` `__all__`),
any runtime module's behavior, or the 001/002 public contracts (NFR-001).

## Architecture & Boundaries

There is no new runtime component and no new dependency direction. The unit adds a **documentation /
verification overlay** that reads the existing public surface and asserts the release artifacts stay
consistent with it:

```text
existing public packages (each declares __all__)   docs/*.md guides     examples/*.py
        │  (read-only)                                   │  (read-only)        │ (read-only)
        ▼                                                ▼                     ▼
docs/api-reference.md  ──drift-checked──▶  test_api_reference.py   docs index / examples index
pyproject.toml + __init__ + py.typed  ──consistency──▶  test_packaging.py   (single version, typed)
CHANGELOG.md / release-readiness.md   ──structure/coverage──▶  test_changelog.py
whole committed tree  ──repo-wide audit──▶  test_committed_files_are_public_safe  (0 findings)
```

- The API reference, the docs index, and the examples index are **derived from and checked against** the
  code and the file tree — a drift (a listed name absent from `__all__`, a guide/example missing from its
  index, an index entry pointing at a missing file) is a **test failure** (SC-002/005).
- The version has a **single source** (`loopplane.__version__`); packaging derives from it (FR-002).
- Every committed artifact is metadata-only and public-safe; the repo-wide audit is the release gate
  (FR-040, SC-004).

## Project Structure

### Documentation (this feature)

```text
specs/014-loopplane-release-packaging-docs/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── packaging-distribution.md   # packaging metadata + single-source version + py.typed + build outputs
│   └── docs-and-release-audit.md   # API-reference/index drift rules + changelog + CI gates + public-safety audit
├── checklists/requirements.md
└── tasks.md                        # Deferred to /speckit.tasks (NOT created by this plan)
```

### Repository artifacts (created/modified during implementation, not by this plan)

```text
pyproject.toml                       # metadata + dynamic version + wheel packages/py.typed (no new runtime dep)
src/loopplane/__init__.py            # single-source __version__ (kept)
src/loopplane/py.typed               # NEW PEP 561 marker (empty)

README.md                            # release-quality: overview, install, quickstart link, layer map, docs links, license
CHANGELOG.md                         # NEW Keep a Changelog summary of units 001–013 (public-safe)
docs/
├── README.md                        # NEW docs index — links every per-layer guide
├── getting-started.md               # NEW getting-started: install + smallest end-to-end example + links
├── api-reference.md                 # NEW public API reference — every loopplane package's __all__ + one-liners
└── release-readiness.md             # NEW release-readiness checklist (incl. the deferred license gate)
examples/README.md                   # NEW examples index — every examples/*.py with a one-liner + run command

.github/workflows/ci.yml             # verified gates + offline `uv build` job

tests/contract/
├── test_packaging.py                # metadata completeness; single-source version; py.typed shipped; packages discoverable
├── test_api_reference.py            # every package with __all__ is documented; listed names == __all__ (no drift); metadata-only
├── test_docs_examples_index.py      # docs index ↔ docs/*.md; examples index ↔ examples/*.py (no missing/dangling)
├── test_changelog.py                # changelog structure + covers units 001–013 + public-safe
├── test_ci_gates.py                 # CI workflow runs format-check + lint + strict types + tests (+ build)
└── test_public_safety.py            # + PHASE14_TARGETS (the new 014 docs + specs/014 dir)
```

**Structure Decision**: no new package — this capstone hardens the **existing** tree. The version stays
single-sourced in `src/loopplane/__init__.py`; packaging metadata, the `py.typed` marker, the docs, the
changelog, the CI build job, and the contract tests are layered on without touching any layer's public
API or any runtime behavior. Every artifact is reproducible offline and verified by a contract test.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| PA — Packaging, version, typing (US1) | `pyproject.toml` metadata + `dynamic` version from `__init__` + wheel `packages`/`py.typed`; `src/loopplane/py.typed`; `test_packaging.py` | metadata complete; single-source version (no `[project] version` literal); `py.typed` shipped; every subpackage importable; `uv build` produces sdist+wheel offline (SC-001/006) | Revert pyproject/py.typed |
| PB — Public API reference (US2) | `docs/api-reference.md`; `test_api_reference.py` | every `loopplane` package with `__all__` is documented and listed names **==** `__all__` (no drift); every layer represented; metadata-only (SC-002) | Revert PB |
| PC — Getting-started navigation (US3) | `README.md`, `docs/getting-started.md`, `docs/README.md`, `examples/README.md`; `test_docs_examples_index.py` | docs index ↔ `docs/*.md`; examples index ↔ `examples/*.py`; README links quickstart + docs; no missing/dangling entry (SC-005) | Revert PC |
| PD — CI gates (US4) | `.github/workflows/ci.yml` verified + offline `uv build` job; documented local gates; `test_ci_gates.py` | CI runs format-check + lint + strict types + full tests (+ build) offline, no secret; local commands documented (SC-003) | Revert CI job |
| PE — Release-readiness: audit + changelog (US5) | `CHANGELOG.md`, `docs/release-readiness.md`; `PHASE14_TARGETS`; `test_changelog.py` | changelog structure + covers 001–013 + public-safe; checklist enumerates gates; repo-wide audit 0 findings (SC-004/005) | Revert PE |
| PF — Final verify | full `pytest`, `uv build` smoke, public-safety scan; board → Verified | full suite green; dist builds; scan clean; board updated | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| A public contract or runtime behavior changes (breaking) | The only code additions are `py.typed` + version single-sourcing; **no layer `__all__` or runtime module is edited**; a contract test asserts every package's public names are unchanged by checking the API reference equals each `__all__` (NFR-001, SC-006) |
| A new runtime dependency creeps in | Build via `uv build` (no new tool); CI/docs use existing dev tooling; `test_packaging.py` asserts the runtime `dependencies` set is unchanged (NFR-002, SC-006) |
| API reference / index drift | `test_api_reference.py` enforces a per-package name bijection with `__all__`; `test_docs_examples_index.py` enforces index ↔ file-tree consistency — drift fails the build (SC-002/005) |
| Version drift between code and packaging | A single source (`__init__.__version__`) with hatchling `dynamic` version; `test_packaging.py` asserts no literal `[project] version` and that `loopplane.__version__` resolves (FR-002, SC-001) |
| `py.typed` not shipped in the wheel | Explicit wheel `packages`/`force-include`; `test_packaging.py` asserts the marker exists and is declared as package data (FR-003) |
| License chosen unilaterally, or a missing license breaks the build | The build does **not** bind a `LICENSE` file (so it builds now); the license (SPDX id + `LICENSE` + `license` field + classifier) is the **single deferred maintainer gate** in `release-readiness.md`; README's License section points to it (Assumptions; FR-041) |
| A secret / private path / internal name / IP leaks into a committed artifact | The repo-wide `test_committed_files_are_public_safe` scans every tracked file; `PHASE14_TARGETS` scans the new 014 docs pre-commit; authors/URLs use public-safe, non-PII values (NFR-004, SC-004) |
| Scope creep into publishing / signing / hosted docs / release automation | Out-of-scope list + reserved extension points; this unit builds the dist locally and verifies gates only — it never uploads, signs, or hosts |

**Rollback posture**: every artifact is **additive** and file-scoped — small, task-scoped commits, each
phase (PA–PE) independently revertible. Reverting any artifact leaves the runtime, every layer's public
API, and the existing CI gates untouched; no runtime dependency is added to remove. The version literal
and `py.typed` are the only code touch-points and are trivially revertible.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every artifact cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | All docs/packaging written fresh from the public surface; no legacy code or private reference copied |
| III | Agent Harness Before Loop Automation | PASS | No runtime feature added — packaging/docs only; names every reserved extension point (publish/sign/host/automate) |
| IV | Runtime Boundary Clarity | PASS | No runtime boundary touched; only `__version__` + `py.typed` added; no component responsibility changes |
| V | Tool Gateway Ownership | PASS | No tool is resolved, authorized, or executed; the unit reads files and asserts consistency |
| VI | Runtime Event Bus Ownership | PASS | No event is emitted or consumed; no live bus is touched |
| VII | Public-Safe Documentation | PASS | The unit's core purpose — a repo-wide public-safety audit (0 findings), metadata-only docs, no secret/path/name/IP, PHASE14 scan (NFR-004, SC-004) |
| VIII | No SDK Replacement | PASS | No framework introduced; packaging via the existing hatchling/uv toolchain; runtime core untouched |
| IX | Reference, Not Clone | PASS | API reference + docs re-derived from the project's own public `__all__` and file tree; no external excerpts |
| X | Testable Evolution | PASS | Each phase has a contract test + a validation gate + a rollback note; every artifact is additive and revertible; drift + public-safety are first-class checks |

**Post-design re-check**: PASS — packaging metadata, the version single-sourcing, the `py.typed` marker,
the docs, and the CI build job introduce no public-contract change, no runtime-behavior change, and no new
runtime dependency. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify, and no new dependency to record — table intentionally empty.
