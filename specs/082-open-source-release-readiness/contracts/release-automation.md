# Contract: Tag-Triggered Release Automation (US2)

Normative contract for `.github/workflows/release.yml` and `scripts/release_sync_check.py`.

## Triggers

1. `push` of tags matching `v*` — the ONLY path that can reach the publish step.
2. `workflow_dispatch` — permitted for dry-run exercising only; validate and build MUST check out the requested existing tag, and the publish step MUST be structurally unreachable from this trigger.
3. No other event (PR, push to branches, schedule) may invoke this workflow.

## Jobs and ordering

1. **validate** — checkout; run `scripts/release_sync_check.py <tag>`; run the §G Python gates (`ruff format --check`, `ruff check`, `mypy`, `pytest -q`). Any failure stops the workflow (fail closed). The extracted CHANGELOG section is exposed as a job output/artifact for the release job.
2. **build** — `uv build`; metadata validation (`uvx twine check dist/*`); dists uploaded as workflow artifacts.
3. **publish** — gated: runs only when (a) the trigger is a `v*` tag push, (b) the repository is the canonical repo (not a fork), and (c) dry-run mode is off. Uses PyPI **trusted publishing** (OIDC; `id-token: write` on this job only; no long-lived secrets) with `skip-existing: true` so re-runs after partial failure are idempotent.
4. **release** — `gh release create <tag>` with the validated notes; `contents: write` on this job only. Also gated on non-fork.

## Dry-run mode

A single explicit condition (workflow input or repository variable) that skips `publish` while running everything else. Default state after merge: dry-run **on** until the maintainer configures the index-side trusted publisher (§E action). The mode's state MUST be visible in the run summary.

## Fail-closed requirements

- Sync mismatch (tag ≠ `__version__`, missing/invalidly dated CHANGELOG section, no referenced unit, or any referenced unit absent/non-`Verified` on the board) → no build, no publish, no release; diagnostics name the exact mismatch.
- Gate failure → no publish, no release.
- Publish failure → release job does not run; re-running the workflow for the same tag is safe (idempotent).
- No step may print tokens or claim success it did not verify.

## Permissions

Workflow default `permissions: contents: read`; jobs elevate only what they need (`id-token: write` publish; `contents: write` release). No `pull_request_target`, no ambient credentials in build/validate.

## Runbook coupling

`docs/release-process.md` documents the human-gated sequence (bump `__version__`, promote CHANGELOG, sync board per `docs/architecture/RELEASE_SYNC_RULES.md`, tag, watch the workflow, post-verify install). The workflow enforces the mechanically checkable subset; the runbook owns the rest. The release cut itself is §E-gated.
