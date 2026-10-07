# Implementation Evidence: Weighted Tenant Turns

Date: 2026-09-07. Status: Verified; all 19 tasks complete.
No commits, branches, worktrees, remotes, releases or deployments were created
during that session. On 2026-10-08 the unit was committed on
`087-weighted-tenant-turns`. No push, release, or deployment was made.

## Spec Kit and authorization

The maintainer approved unit 087 and requested the Spec Kit flow. Completed specify,
quality checklist (11/11), plan/research/data-model/contracts/quickstart, 18 planned
tasks and the verification-fixture correction T019.
Read-only analyze reviewed all 15 functional requirements and five success criteria:
100% task coverage, zero blocking inconsistencies, no unmapped tasks. Hard-cap
precedence and degradation limitations are explicit. No artifact in Verified 086
was retro-edited. Scope does not authorize changing old defaults or outward contracts.

The optional agent-context hook was executed through the repository extension.
Windows PowerShell quoting and unavailable YAML modules prevented its first attempts;
a session-only parser restricted to the exact observed three-value configuration
enabled the same script to refresh AGENTS.md and its required CLAUDE.md mirror.
No integration script/config or managed block was hand-edited.
No before/after implementation hooks are registered in `.specify/extensions.yml`.

## Focused RED and corrections

- Initial weighted tests: collection failed with missing `fairness_weighted` module.
- First implementation: 19 passed, 1 failed; full-cap polling exposed delayed removal
  of a departed tenant's score. Immediate removal fixed it; 20 passed.
- Durable RED: collection failed with missing `fairness_weighted_postgres` module.
  After implementation, both weighted suites: 26 passed.
- Independent read-only design review reproduced holder-conflict cleanup stealing
  the original principal's permit. A focused regression failed before cleanup was
  scoped to principal plus holder. A second RED check showed a driver ValueError
  bypassing safe error normalization; only internal policy mismatch is now preserved.
  Combined result after both fixes and public cross-worker/outage tests: 32 passed.
- Import matrix RED: two missing module declarations. Added only their Phase-1
  fairness/permit edges; no host/webapi/tool dependency was allowed.
- Latest focused weighted + 072/085/086 + admission + matrix run: **88 passed,
  1 existing Starlette deprecation warning**, 17.01 seconds. Includes held-lease
  heartbeat, healthy/outage cap 2 with a waiting third caller and cancelled admission.

## Review inputs and scope

Requested behavior: 087 spec/plan/tasks, including ratio/FIFO/cap/readiness/recovery
and configuration criteria. Standards: constitution, TARGET architecture boundaries,
handoff rules, plus Python/architecture/performance review guidance.
Both inputs are available and reviewed separately. Reused the existing public
admission and permit contracts; weighting/cleanup lives in new isolated modules.
The shared pure selector serves memory and durable stores. Internal durable helpers
are within the same fairness concern; no Phase-1 import of host or transport is added.

## Validation limits

- Repository validation passed as recorded below; this is not a release/deployment.
- SQL stub tests model persistence and transaction rollback, not live Postgres
  network/locking/load behavior. No live Postgres deployment was tested.
- Coordinator state uses a serialized snapshot with O(queued work) processing per
  selection/operation; bounded polling and database timeouts are not a throughput SLA.
- Shared weighted state is static-policy and isolated from legacy 086 state;
  activation requires a consistent, drained worker group. No live reconfiguration.
- Frontend and packaging deployment are outside this backend-only change.

## Final gates

- Ruff format: 588 files already formatted. Ruff check initially found three long
  lines in the new files; formatting-only corrections applied and lint passed.
- Mypy: Success, no issues found in 230 source files.
- `uv lock --check --offline`: resolved 68 packages; dependency/lock and legacy
  fairness/loop/webapi app diffs are empty. `git diff --check` passed.
- Changed/untracked public-safety scan: 24 files, zero violations using the
  repository built-in and local patterns; no matching source content was printed.
- First full `pytest -q`: **2382 passed, 33 skipped, 1 failed**, 786.24 seconds.
  The failure was the unchanged `test_concurrent_run_returns_conflict` fixture's
  missing `platform_fairness` attribute. Isolated rerun reproduced the AttributeError;
  `git diff --exit-code` confirmed that test and admission/router paths matched HEAD.
  T019 replaces the incomplete stub with the existing real host fixture and patches
  only `run()` to raise the same conflict. The original 409 assertions remain intact.
  This corrects verification setup, not product behavior.
- Fixture regression: `pytest tests/integration/test_webapi_us1.py -q`:
  **4 passed, 1 existing warning**, 2.83 seconds.
- Final full `pytest -q --durations=5`: **2383 passed, 33 skipped, 1 existing
  Starlette deprecation warning**, 848.66 seconds, exit 0. No product/test source
  changed after this run; only final status and evidence documentation was updated.
- Final `ruff format --check --no-cache .`: **588 files already formatted**;
  `ruff check --no-cache .`: **All checks passed**; `git diff --check`: exit 0.
- Quickstart Python construction example executed successfully.
- After final board/task updates, `pytest` with
  `tests/contract/test_spec_task_audit.py`, `tests/contract/test_docs_links.py`,
  `tests/contract/test_api_reference.py`, `tests/contract/test_import_matrix.py`
  and `tests/contract/test_public_safety.py`, using `-q`: **39 passed**,
  97.35 seconds, exit 0. The changed/untracked scan also remained 24 files,
  zero violations after the final handoff text was added.

## Changed paths and handoff

- New runtime: `src/loopplane/fairness_weighted.py` and
  `src/loopplane/fairness_weighted_postgres.py`.
- New tests: `tests/unit/test_weighted_tenant_turns.py`,
  `tests/unit/test_weighted_tenant_postgres.py`, `tests/weighted_pg_stub.py`.
- Extended verification: `tests/unit/test_webapi_admission.py`,
  `tests/contract/test_import_matrix.py`, `tests/integration/test_webapi_us1.py`.
- Documentation: all nine files in `specs/087-weighted-tenant-turns/`,
  `docs/api-reference.md`, `docs/capabilities.md`, `docs/gap-analysis.md`,
  `docs/loopplane-agent-board.md`.
- Spec Kit pointers: `.specify/feature.json`, generated `AGENTS.md` and `CLAUDE.md`.

Existing defaults, dependencies, legacy fairness/loop/webapi product paths and
Verified 086 artifacts remain unchanged. No blocking review findings remain.
Changes are left uncommitted on the existing branch for maintainer inspection.
Any subsequent live deployment, policy rollout or new roadmap unit requires its
own authorized scope; offline Postgres checks do not discharge live validation.
