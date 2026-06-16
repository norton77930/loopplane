# Release readiness checklist

The gates that must pass before tagging a LoopPlane release. Each is reproducible
from the committed tree, offline, and most are enforced by a contract test.

**Scope.** This covers units **000–024** — the original runtime + release roadmap
(000–019, shipped as **v0.1.0**, MIT) plus the completed four-phase **gap-closure** plan
(020–024) that took LoopPlane from an embeddable skeleton to a usable product: real model
providers, a pluggable checkpoint persistence layer, per-principal web authentication with
a login UI, and a desktop packaging pipeline. All units are `Verified` on `main`; the gates
below hold at this state.

## Gates — Python package

- [ ] **Distribution builds** — `uv build` produces an sdist and a wheel; the wheel
  ships `loopplane/py.typed` and every subpackage. (`tests/contract/test_packaging.py`)
- [ ] **Quality gates green** — `ruff format --check`, `ruff check`, `mypy` (strict),
  and the full `pytest` suite pass locally and in CI.
  (`.github/workflows/ci.yml`, `tests/contract/test_ci_gates.py`)
- [ ] **Public-safety audit clean** — the repository-wide scan reports zero findings:
  no secret, private path, internal name, IP, or token in any committed file.
  (`tests/contract/test_public_safety.py`)
- [ ] **Docs consistent** — the API reference matches every package's `__all__`, and
  the docs/examples indexes match the file tree.
  (`tests/contract/test_api_reference.py`, `tests/contract/test_docs_examples_index.py`)
- [ ] **Changelog current** — `CHANGELOG.md` records the release under its version
  (entries through unit 024). (`tests/contract/test_changelog.py`)
- [x] **LICENSE present** — the project is licensed under **MIT**: a `LICENSE` file
  is at the repository root, `pyproject.toml` declares `license = "MIT"` with
  `license-files = ["LICENSE"]` (PEP 639; the wheel carries `License-Expression: MIT`),
  and the README's License section links it. (`tests/contract/test_packaging.py`)

## Gates — frontend apps (isolated JS toolchains)

- [ ] **Web app** — `apps/web`: `tsc --noEmit` (strict), `vitest run`, and `vite build`
  pass; the SPA reaches the runtime only through the public `/v1` web API and embeds no
  secret. (`.github/workflows/web.yml`)
- [ ] **Desktop app** — `apps/desktop`: `tsc --noEmit` (strict) and `vitest run` pass; the
  packaging pipeline (the PyInstaller freeze spec, the electron-builder config, and the
  unit-tested spawn resolver) is in place. (`.github/workflows/desktop.yml`)

## Gap-closure status (units 020–024) — COMPLETE

- **Phase A — model providers (020)**: Anthropic + OpenAI adapters over the model
  boundary, each behind its own optional extra.
- **Phase B — persistence (021)**: a `CheckpointStore` interface with a filesystem default
  and an optional standard-library SQLite backend.
- **Phase C — web auth (022) + login UI (023)**: per-principal authentication and session
  ownership scoping over the web/API host, plus a token login screen in the web app.
- **Phase D — desktop packaging (024)**: a PyInstaller-frozen sidecar + an electron-builder
  config + a spawn resolver, so the desktop app can ship without a system Python.

## Out of scope (reserved)

Reserved, maintainer-initiated steps — **not** part of this checklist:

- Publishing / uploading the wheel to a package index (e.g. PyPI).
- Producing and **signing/notarizing** the per-OS desktop installers — the packaging
  pipeline (unit 024) exists; the actual cross-platform build + signing is reserved.
- A hosted documentation site, release automation, auto-update, and app-store distribution.
