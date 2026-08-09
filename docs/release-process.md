# Release process (runbook)

How a LoopPlane release is cut. Cutting a release is a **maintainer-only action**: the
version bump, the changelog promotion, the tag, and the publish are human-approval gates
(see [`GOVERNANCE.md`](../GOVERNANCE.md) and §E of
[`architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`](architecture/AI_HANDOFF_OPERATING_TEMPLATE.md)).
Automation validates and executes; it never decides that a release should happen.

Two documents sit next to this one:

- [`release-readiness.md`](release-readiness.md) — the gate checklist a release must
  satisfy.
- [`architecture/RELEASE_SYNC_RULES.md`](architecture/RELEASE_SYNC_RULES.md) — which
  artifact must be synchronized at which event. This runbook executes those rules.

## What the automation does

`.github/workflows/release.yml` runs on a `v*` tag push (and on `workflow_dispatch` for
dry-run exercising only, which structurally cannot publish):

| Job | Does | Fails closed by |
| --- | --- | --- |
| `validate` | `scripts/release_sync_check.py <tag>`, then `ruff check`, `ruff format --check`, `mypy`, `pytest -q`; extracts the changelog section as release notes | stopping the whole chain — nothing is built |
| `build` | `uv build`, then `uvx twine check --strict dist/*`; uploads the distributions | stopping before publish |
| `publish` | PyPI **trusted publishing** (OIDC, no long-lived token) with `skip-existing: true` | only runs for a `v*` tag push on the canonical repository with dry run off |
| `release` | `gh release create` (or `edit`) with the extracted notes | skipped whenever `publish` is skipped or fails |

`scripts/release_sync_check.py` is the single authority for the mechanical part of the
sync rules and can be run locally at any time:

```sh
uv run python scripts/release_sync_check.py v0.5.0
```

It checks that the tag is a `vX.Y.Z` ref, that `__version__` in
`src/loopplane/__init__.py` equals the tag's version, that `CHANGELOG.md` has a
released section with a valid calendar date in `## [X.Y.Z] - YYYY-MM-DD` form, and that
every three-digit unit referenced by that section is **Verified** on the agent board; on
success it prints that section (the release notes) to stdout. The remaining sync rules —
`docs/api-reference.md` currency, `docs/capabilities.md` / `docs/gap-analysis.md` currency,
and the ADR references of the changelog section — stay in the human preflight below.

## One-time maintainer setup

1. **Reserve the project name** on PyPI (the name is claimed by the first publish; verify
   it is still available before relying on it).
2. **Configure the trusted publisher** for the project on PyPI: owner and repository of
   this repository, workflow file name `release.yml`. If you restrict it to a GitHub
   deployment environment, add a matching `environment:` key to the `publish` job — the
   workflow ships without one, so the default (no environment restriction) works as is.
3. **Leave dry run on until step 2 is done.** The workflow reads the repository variable
   `LOOPPLANE_RELEASE_DRY_RUN`; publish runs only when it is exactly `false`. Unset (the
   default), empty, or `true` all mean dry run. The resolved mode is printed in every run
   summary.
4. Optionally exercise the pipeline first: run the workflow via `workflow_dispatch` with
   an existing tag. It validates and builds, prints the dry-run notice, publishes
   nothing, and creates no release.

## Preflight (before touching the version)

- [ ] Every unit in the release is **Verified** on `docs/loopplane-agent-board.md` (the
      only completion authority).
- [ ] `CHANGELOG.md` `[Unreleased]` describes every included unit, and references the
      ADRs the release ships.
- [ ] `docs/api-reference.md` reflects every public-surface change in the release.
- [ ] `docs/capabilities.md` and `docs/gap-analysis.md` are brought up to the released
      line, and their "deferred / still open" lists are re-audited.
- [ ] The README's high-level claims still match reality (README is tied to release
      boundaries only; it never enumerates per-unit features).
- [ ] Local gates are green: `uv run ruff format --check .`, `uv run ruff check .`,
      `uv run mypy`, `uv run pytest -q`, `uv build`.
- [ ] The frontend gates in [`release-readiness.md`](release-readiness.md) are green for
      any release that includes app changes.
- [ ] Version number decided: MINOR for a batch of new-capability units, PATCH for
      remediation/fixes, MAJOR reserved for contract breaks.

## Cutting the release

1. **Bump the version.** Edit `__version__` in `src/loopplane/__init__.py` to `X.Y.Z`.
   This is the single source of truth; `pyproject.toml` reads it through hatch.
2. **Promote the changelog.** Rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and
   open a fresh, empty `## [Unreleased]` above it. Do not reorder existing entries.
3. **Sync the board** per `docs/architecture/RELEASE_SYNC_RULES.md`.
4. **Verify locally, before tagging:**

   ```sh
   uv run python scripts/release_sync_check.py vX.Y.Z
   uv run pytest -q
   uv build
   uvx twine check --strict dist/*
   ```

5. **Commit** the bump + promotion as one release commit, and push it to `main`.
6. **Tag and push the tag:**

   ```sh
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

7. **Watch the run.** Confirm in the run summary that the dry-run line says what you
   expect, that `validate` and `build` are green, and that `publish` either ran (dry run
   off) or was skipped (dry run on).

## Post-publish verification

```sh
python -m venv .release-check
.release-check/bin/pip install "loopplane[web]==X.Y.Z"
.release-check/bin/python examples/host_quickstart.py
.release-check/bin/loopplane --help
```

(On Windows the venv scripts live in `.release-check\Scripts\`.) Then check that the
GitHub Release for `vX.Y.Z` exists and carries the changelog section as its notes.

## Failure modes

| Symptom | Meaning | Action |
| --- | --- | --- |
| `validate` fails on the sync check | tag, `__version__`, and changelog disagree | fix the tree, delete and re-push the tag; nothing was published |
| `validate` fails on a gate | the release is not green | fix, re-cut; nothing was published |
| `build` fails `twine check` | distribution metadata is invalid | fix packaging metadata, re-cut |
| `publish` fails partway | some files reached the index | re-run the workflow for the same tag: `skip-existing: true` skips what already landed |
| `publish` was skipped unexpectedly | dry run is still on, or the run is not a `v*` tag push on the canonical repository | check the run summary's mode line and the repository variable |
| The release notes are wrong | the changelog section is wrong | fix `CHANGELOG.md`, then re-run the workflow for the tag — the `release` job updates the existing release in place |

A published version is immutable: a bad release is corrected by a new PATCH release (and,
if genuinely broken, by yanking the bad version on the index). Never re-tag a published
version.

## Recommended next release

`v0.5.0` covering units **064–081** (the current `[Unreleased]` line), plus unit 078 if it
is Verified by then. That is a MINOR bump: a batch of additive capability units with no
contract break. Timing is the maintainer's call.
