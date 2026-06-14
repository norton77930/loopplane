# Release readiness checklist

The gates that must pass before tagging a LoopPlane release. Each is reproducible
from the committed tree, offline, and most are enforced by a contract test.

## Gates

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
- [ ] **Changelog current** — `CHANGELOG.md` records the release under its version.
  (`tests/contract/test_changelog.py`)
- [x] **LICENSE present** — the project is licensed under **MIT**: a `LICENSE` file
  is at the repository root, `pyproject.toml` declares `license = "MIT"` with
  `license-files = ["LICENSE"]` (PEP 639; the wheel carries `License-Expression: MIT`),
  and the README's License section links it. (`tests/contract/test_packaging.py`)

## Out of scope (reserved)

Publishing or uploading to a package index, signed releases, a hosted documentation
site, release automation, and multi-distribution packaging are reserved extension
points — not part of this checklist.
