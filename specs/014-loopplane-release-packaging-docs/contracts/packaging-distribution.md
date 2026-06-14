# Contract: Packaging & Distribution

Defines the packaging contract for the `loopplane` distribution: complete metadata, a single-source
version, shipped type information, and a buildable sdist + wheel — **without a new runtime dependency or
any public-API change** (FR-001–FR-004; NFR-001/002).

## Packaging metadata (`pyproject.toml` `[project]`)

MUST declare, for a public distribution:

- `name = "loopplane"`, `description`, `readme = "README.md"`, `requires-python = ">=3.12"`.
- `authors` — public-safe, **no personal email/PII** (project-level attribution).
- `keywords` and trove `classifiers` (Development Status; Intended Audience; `Programming Language ::
  Python :: 3.12`; `Typing :: Typed`). The `License ::` classifier is **deferred** with the license
  decision (see `docs-and-release-audit.md` → Release-readiness).
- `[project.urls]` — the public repository home (no private host/path).
- `dependencies` and `optional-dependencies` (`mcp`, `otel`, `web`) — **unchanged** (no new runtime dep).

MUST NOT: add a runtime dependency; carry a literal `version` under `[project]` (superseded by the
single-source version); embed a secret, private path, internal name, or IP.

## Single-source version

- The version's single source of truth is `loopplane.__version__` in `src/loopplane/__init__.py`.
- `[project]` declares `dynamic = ["version"]` and `[tool.hatch.version] path = "src/loopplane/__init__.py"`
  so the packaging version derives from it.
- Guarantee: reading the version from the code (`loopplane.__version__`) and from the built distribution
  metadata yields the **same** value — there is exactly one source.

## Type information (PEP 561)

- `src/loopplane/py.typed` exists (empty marker).
- The wheel build ships `py.typed` and **every** `loopplane` subpackage (explicit wheel `packages` /
  `force-include` as needed), so downstream type-checkers treat `loopplane` as typed.

## Build outputs

- `uv build` (offline; no new dependency) produces a source distribution **and** a wheel from the
  committed tree. `python -m build` is a documented alternative (requires the `build` dev tool).
- The build requires **no** network and **no** environment-specific configuration.
- The build does **not** bind a `LICENSE` file, so it succeeds before the license decision (the license
  is a deferred maintainer gate).

## Verification (`tests/contract/test_packaging.py`)

1. All required metadata fields are present; `dependencies` is unchanged; `optional-dependencies` keys are
   preserved (no new runtime dependency).
2. No literal `version` under `[project]`; `dynamic` includes `"version"`; `[tool.hatch.version].path`
   points at `src/loopplane/__init__.py`; `loopplane.__version__` is a non-empty version string.
3. `src/loopplane/py.typed` exists and is declared as shipped package data; every `loopplane` subpackage
   imports.
4. (Build smoke — `quickstart.md`) `uv build` produces an sdist + wheel offline and the wheel contains
   `loopplane/py.typed`.
