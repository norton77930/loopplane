# Quickstart: Validating Open-Source Release Readiness (082)

Runnable validation scenarios per story. Prerequisites: repo checkout on the 082 branch, `uv` installed, Node not required. Details live in [contracts/](contracts/) and [data-model.md](data-model.md) — this guide does not duplicate them.

## US2 — Release machinery

```
uv run pytest tests/contract/test_release_sync.py tests/contract/test_release_workflow.py -q  # validator + workflow guards green
uv run python scripts/release_sync_check.py v0.4.0            # PASS: version + dated CHANGELOG + Verified board units
uv run python scripts/release_sync_check.py v9.9.9            # FAIL (non-zero) with precise diagnostics
```

Workflow: trigger `release.yml` via `workflow_dispatch` (dry-run) and confirm: validate + build + metadata check run, publish is skipped with a visible dry-run notice, no release is created. Expected outcome: green run, artifacts uploaded, nothing published.

## US1 — Installable package

```
uv build
uvx twine check dist/*                                        # metadata PASS
python -m venv <fresh-dir> && <fresh-venv> pip install "dist/loopplane-<ver>-py3-none-any.whl[web]"
<fresh-venv> python examples/host_quickstart.py               # credential-free quickstart succeeds
<fresh-venv> loopplane run "hello"                            # console script works
```

Expected: all succeed without the repo checkout on `sys.path`. (`pyproject.toml` URL/classifier edits are deferred until 078 is Verified; re-run `twine check` after they land.)

## US3 — Governance

Review-only: `GOVERNANCE.md` answers "who approves §E gates"; `CODEOWNERS` lists the load-bearing paths; `CONTRIBUTING.md` hazard map names R1/R4, the guard system, and the default-off rule. GitHub validates CODEOWNERS syntax on push — check the repo's CODEOWNERS errors page shows none.

## US4 — Documentation coverage

```
uv run pytest tests/contract/test_docs_links.py -q            # offline relative-link walk green
```

Manual: for each capability category in `docs/capabilities.md`, find its guide within one click from `docs/README.md`.

## US5 — Boundary gate

```
uv run pytest tests/contract/test_import_matrix.py -q         # matrix green incl. negative self-tests
```

Confirm the negative self-tests exist and fail on: seeded forbidden edge, undeclared package, TYPE_CHECKING edge used at runtime.

## US6a — webapi decomposition

```
uv run pytest tests/contract/test_webapi_route_snapshot.py -q # green BEFORE and AFTER the split
uv run pytest tests/contract/test_webapi_boundary.py -q
```

Expected: identical inventory + canonical OpenAPI equality across the split commit (see [contracts/webapi-route-snapshot.md](contracts/webapi-route-snapshot.md)).

## US7 — Audit refresh + backfill

Review the `ARCHITECTURE_AUDIT.md` diff: snapshot date/commit updated, stale rows corrected, every remaining gap row spot-checks true against `tests/`. Then `uv run pytest <new test files> -q` green; non-tautology proven once via a temporary local mutation (not committed).

## Unit completion (all stories)

```
uv run ruff format --check . && uv run ruff check .
uv run mypy
uv run pytest -q                                              # fresh full count reported literally
uv build
```

Plus: public-safety scan over all changed files (SC-007), and the §H completion report with literal results. Known flakes (`test_examples_smoke.py`, `test_us2_mcp`) re-run in isolation before judging.
