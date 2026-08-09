# 082 Open-Source Release Readiness — Implementation Evidence

Bounded evidence for unit 082. This file records what was executed and what was
deliberately deferred. It is **not** an approval authority: every §E human gate still
requires the maintainer's own record, and completion status lives only on
`docs/loopplane-agent-board.md`.

## 0. Execution context and deviations

**Clean 082 worktree run.** On 2026-08-09 the maintainer explicitly instructed the agent
to execute the continuation queue, authorizing T001. A dedicated worktree was created on
branch `082-open-source-release-readiness` from `origin/main` commit
`e2214f517b38e8be89cd38cbe92a010df13785c5`; `HEAD`, `origin/main`, and the merge base were
identical before transfer. Only the 082 file inventory in §8 was copied from the dirty 078
checkout. No 078 WIP, `.superpowers/**`, or `openspec/**` path was transferred.

1. **T001 executed; no publication action occurred.** The maintainer's user-role
   instruction was to read the continuation handoff and execute its §3 queue. Under that
   instruction, the A-stage local work copied the existing release workflow into this
   worktree and downloaded Twine plus the wheel's `[web,anthropic]` extras for validation.
   No separate user-role confirmation or outward-action approval was received. Nothing was
   staged, committed, pushed, dispatched, tagged, released, or published.
2. **T002 executed without changing the active-feature controls.** One 082
   `Implementation in progress` row was added to `docs/loopplane-agent-board.md`.
   `.specify/feature.json` and the SPECKIT-managed blocks still point to 078, as required.
3. **Fresh local gates were executed on the clean branch.** T006 passed. The current
   A-stage change-set also passed Ruff, mypy, the full Python suite, build, Twine metadata,
   and the implemented quickstart sections. T038 remains unchecked because US5/US6/US7
   are still blocked on the maintainer's landing-order decision; those future changes will
   require one final re-run before unit completion.
4. **Windows worktree-path deviation.** The repository configures
   `--basetemp=tmp/pytest`. A first run failed because the fresh worktree had no `tmp/`
   parent; after creating it, path-heavy capability-store tests failed because the nested
   `.claude/worktrees/...` path made their atomic temporary filenames exceed the legacy
   Windows path limit. The full suite was therefore re-run inside the same worktree with a
   Windows `\\?\` long-path basetemp. That run is the valid result; all failed setup runs
   are retained in §8 rather than hidden.

## 1. FR-016 / 078 no-touch verification

The 078-sensitive set MUST NOT be byte-changed by this unit while 078 is not Verified:
`pyproject.toml`, `uv.lock`, root `package.json` / `package-lock.json`, `apps/**`,
`packages/**`, `src/loopplane/host/**`, `src/loopplane/controller/**`,
`scripts/*desktop*.ps1`, `.github/workflows/desktop.yml`, `docs/adr/0015-*`,
`specs/078-*/**`, and desktop-related tests (`tests/**/test_desktop*`,
`tests/helpers/desktop_*`). Also never touched: `.superpowers/**`, `openspec/**`,
`.specify/feature.json`, or the SPECKIT managed blocks in `AGENTS.md` / `CLAUDE.md`.
`docs/loopplane-agent-board.md` was changed only for T002: one additive 082 roadmap row;
its 078 row, §4 active-feature table, completion statuses, and control pointers were not
changed.

Result: see §7 (file inventory) and §8 (current `git status` review). **No file from the
FR-016 no-touch set was created, modified, or deleted by this pass.**

## 2. Story evidence — US1 (install and run from a published package)

Executed: T004 (CI metadata validation), T005 (README), T006 (fresh install).
Deferred: T007 `[DEFER-078]`, T008 `[DEFER-078] [GATE-§E]`.

### T004 — `.github/workflows/ci.yml`

Added one step after the existing `Build distribution` step, on the ubuntu leg of the
existing matrix only (`if: matrix.os == 'ubuntu-latest'`), running
`uvx twine check --strict dist/*`. Trigger set, permissions, matrix, and every existing
step are unchanged. `twine` is fetched transiently by `uvx`; it is **not** added to any
dependency group (`pyproject.toml` is in the FR-016 no-touch set and was not edited).

Verified that the new step is green today, without writing into the repository's `dist/`
directory: the distributions were built into a scratch directory outside the repository
and checked there.

```
$ uv build --out-dir <scratch>
Building source distribution...
Building wheel from source distribution...
(exit 0; loopplane-0.4.0.tar.gz + loopplane-0.4.0-py3-none-any.whl)

$ uvx twine check --strict <scratch>/*
Checking <scratch>/loopplane-0.4.0-py3-none-any.whl: PASSED
Checking <scratch>/loopplane-0.4.0.tar.gz: PASSED
(exit 0)
```

Scope note: this validates **distribution metadata**, which comes entirely from the
untouched `pyproject.toml`. It is deliberately **not** the SC-001 install validation
(T006) — the built artifacts contain 078's working-tree code, so nothing about their
runtime contents is claimed here.

### T005 — `README.md`

Additive, structure-preserving edit: three truthful badges (CI workflow status, MIT
license, Python 3.12+ — **no** PyPI badge, because nothing is published yet), an Install
section that states index install is "pending the first publish" and keeps the clone path
as the working install, an extras matrix table, and links to `GOVERNANCE.md` /
`CONTRIBUTING.md`. Every other section retains its original wording and order.

Companion edit required by the repository's own sync rule
(`docs/architecture/RELEASE_SYNC_RULES.md`: "Positioning/installation change → README +
`docs/getting-started.md` together"): the same two-sentence install-status wording was
mirrored into `docs/getting-started.md` so the two install sections do not diverge. No
other part of that file changed.

### T006 — install validation: PASS on clean 082 branch

The wheel was built from the clean `origin/main`-based worktree, checked by Twine, and
installed into a newly created Python 3.12.9 virtual environment with both the `web` and
`anthropic` extras. The quickstart and console script were then run from a child working
directory with the repository root absent from `sys.path`.

```
$ uv build
Successfully built dist\loopplane-0.4.0.tar.gz
Successfully built dist\loopplane-0.4.0-py3-none-any.whl

$ uvx twine check --strict dist/*
Checking dist\loopplane-0.4.0-py3-none-any.whl: PASSED
Checking dist\loopplane-0.4.0.tar.gz: PASSED

$ uv venv --python 3.12 <fresh-venv>
Using CPython 3.12.9

$ uv pip install --python <fresh-venv-python> "<wheel>[web,anthropic]"
Resolved 25 packages
Installed 25 packages
loopplane==0.4.0 (from the built wheel)

$ <fresh-venv-python> examples/host_quickstart.py
repo_on_sys_path_before=False
  1  user-input
  2  assistant-output-increment
  3  turn-completed
  4  tool-call-started
  5  tool-call-completed
  6  assistant-output-increment
  7  turn-completed
  8  run-terminated
ended: natural-completion

$ <fresh-venv> loopplane run "hello"
LoopPlane demo model: no provider is configured, so this is a canned offline response.
[run natural-completion, 1 turn(s)]

installed_version=0.4.0
module=<fresh-venv>\Lib\site-packages\loopplane\__init__.py
repo_on_sys_path=False
```

All generated environments, distributions, and temporary test directories were removed
after validation.

### T007 / T008 — `pyproject.toml`: DEFERRED

`[DEFER-078]`. 078's accepted Stage-B reviews bind the exact bytes of `pyproject.toml`
and `uv.lock`; editing them before 078 is Verified forces 078 back through its review
gates (handoff.md §4). T008 additionally needs a recorded §E maintainer approval for a
new extra. Both stay unchecked in `tasks.md`.

## 3. Story evidence — US2 (one-command tagged release)

Executed: T009, T010, T011, T012, T013 (local half).

### T009 → T010 — test-first order (RED then GREEN)

`tests/contract/test_release_sync.py` was written **before**
`scripts/release_sync_check.py` and executed against the missing script to prove the test
can fail. Literal result of the RED run:

```
$ uv run pytest tests/contract/test_release_sync.py -q
=================================== ERRORS ====================================
____________ ERROR collecting tests/contract/test_release_sync.py _____________
tests\contract\test_release_sync.py:46: in <module>
    checker = _load_script()
tests\contract\test_release_sync.py:42: in _load_script
    spec.loader.exec_module(module)
E   FileNotFoundError: [Errno 2] No such file or directory:
E   '<repo>/scripts/release_sync_check.py'          (path abbreviated)
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 3.87s
```

That is the required red state: the module under test does not exist yet.

After implementing `scripts/release_sync_check.py` (Python standard library only, no
network, no import of the `loopplane` package — it parses `src/loopplane/__init__.py`
textually so it works in a checkout without an installed environment):

```
$ uv run pytest tests/contract/test_release_sync.py -q
......................                                                   [100%]
22 passed in 1.01s
```

(22 = 16 test functions, one of which is parametrized over 7 rejected refs.)

A subsequent focused code review found two release fail-closed gaps: the validator did not
mechanically enforce the board's `Verified` status for units named by release notes, and no
committed test guarded the workflow's security-sensitive conditions. The repair followed a
second RED → GREEN slice:

```
$ uv run pytest tests/contract/test_release_sync.py \
    tests/contract/test_release_workflow.py tests/contract/test_docs_links.py -q
7 failed, 35 passed in 2.37s
```

The RED failures covered non-Verified/missing board units, invalid calendar dates, the
missing dispatch-tag checkout, and the new result field. The implementation now extracts
three-digit unit bullets from the released CHANGELOG section, requires every referenced
unit to be present and `Verified` on `docs/loopplane-agent-board.md`, validates dates with
the standard library, and keeps stdout empty on every failure. The new offline
`tests/contract/test_release_workflow.py` permanently guards tag-only/canonical-repo/dry-run
publish conditions, job dependencies, least-privilege permissions, OIDC/no-secret posture,
idempotent publish, and dispatch checkout of the requested tag for both validate and build.

```
$ uv run pytest tests/contract/test_release_sync.py \
    tests/contract/test_release_workflow.py tests/contract/test_docs_links.py -q
42 passed in 1.62s
```

Focused review then pressure-tested the guards rather than accepting substring coverage.
Three bounded repairs followed: exact conjunctive publish/release conditions; plural and
explicit `Unit`/`Units` references with a fail-closed no-unit case; exact job-level
permission maps including scalar `write-all` detection; and both dot/bracket GitHub secret
contexts. Each parser path has a synthetic anti-false-green test. The last focused run was:

```
$ uv run pytest tests/contract/test_release_sync.py \
    tests/contract/test_release_workflow.py tests/contract/test_docs_links.py -q
47 passed in 1.80s
```

The required code-review claim passed after these repairs: **PASS**, with no remaining
blocking finding for release fail-closed behavior, workflow guards, dispatch tag checkout,
or docs-walker coverage.

### T011 — `.github/workflows/release.yml`

Written to `contracts/release-automation.md`. Contract-by-contract mapping:

| Contract clause | Implementation |
| --- | --- |
| `v*` tag push is the only path to publish | `on.push.tags: ['v*']`; the publish job's `if` requires `github.event_name == 'push'` and `startsWith(github.ref, 'refs/tags/v')` |
| `workflow_dispatch` allowed, structurally cannot publish | dispatch is a trigger, but the publish job's `if` demands a `push` event **and** a `v*` tag ref, which a dispatch run never has; validate and build both check out the input tag so dry-run evidence covers that tag's committed tree |
| jobs validate → build → publish → release | four jobs chained with `needs:` in that order |
| fail closed | `validate` runs `scripts/release_sync_check.py` first, then ruff/mypy/pytest; any failure stops the chain (`needs:` gating), so nothing is built, published, or released |
| workflow-level `permissions: contents: read` | declared at workflow level; `validate`/`build` inherit it |
| per-job elevation only | `publish` adds `id-token: write`; `release` adds `contents: write` |
| trusted publishing, no long-lived secret | `pypa/gh-action-pypi-publish@release/v1` over OIDC; the workflow contains **no `secrets.` reference at all** — `gh release create` uses the ephemeral runner-provided `${{ github.token }}` |
| idempotent re-run | `skip-existing: true` on the publish action |
| fork guard | every side-effecting job requires `github.repository == 'norton77930/loopplane'` |
| dry-run default ON | `vars.LOOPPLANE_RELEASE_DRY_RUN` — publish requires the value to be exactly `false`; unset (the default after merge) means dry-run, so publish is skipped |
| dry-run state visible in the run summary | `validate` and `publish` write the resolved mode to `$GITHUB_STEP_SUMMARY` |
| `gh release create` fed by the validator's notes | `validate` writes the extracted section to `release-notes.md` and uploads it as an artifact; `release` downloads it and passes `--notes-file release-notes.md` |

### T012 — `docs/release-process.md`

The §E-gated human runbook: preconditions, the one-time maintainer setup for the PyPI
trusted publisher, the bump/promote/board-sync/tag sequence, how to watch the workflow,
post-publish verification, the fail-closed and re-run semantics, and the recommended
`v0.5.0` scope (units 064–081, plus 078 if Verified by then).

### T013 — local validation (SC-002, local half)

Diagnostics go to stderr; the extracted release notes go to stdout, so the notes can be
captured cleanly. Both streams are shown.

```
$ uv run python scripts/release_sync_check.py v0.4.0
exit=0
--- stderr ---
[ok] tag v0.4.0 -> version 0.4.0
[ok] src/loopplane/__init__.py __version__ == 0.4.0
[ok] CHANGELOG.md section [0.4.0] found and validly dated
[ok] every released unit is Verified on docs/loopplane-agent-board.md
PASS: release sync checks passed for v0.4.0
Reminder - the non-mechanical release-sync checks stay with the human runbook
(docs/release-process.md, docs/architecture/RELEASE_SYNC_RULES.md):
docs/api-reference.md + capabilities + gap-analysis currency, and the ADR references
of the CHANGELOG section.
--- stdout (78 lines; first line shown) ---
## [0.4.0] - 2026-06-21
```

```
$ uv run python scripts/release_sync_check.py v9.9.9
exit=1
--- stdout (must be empty) ---
--- stderr ---
[ok] tag v9.9.9 -> version 9.9.9
[fail] src/loopplane/__init__.py __version__ is 0.4.0, expected 9.9.9 for tag v9.9.9
[fail] CHANGELOG.md has no released, dated section [9.9.9] (promote [Unreleased] first)
FAIL: 2 release-sync check(s) failed for v9.9.9; nothing may be published.
Reminder - the non-mechanical release-sync checks stay with the human runbook
(docs/release-process.md, docs/architecture/RELEASE_SYNC_RULES.md):
docs/api-reference.md + capabilities + gap-analysis currency, and the ADR references
of the CHANGELOG section.
```

Note that on failure stdout is empty: no release notes are produced for a tag that failed
validation, so a downstream step cannot accidentally consume them.

**Deferred (not dropped):** the `workflow_dispatch` dry-run half of SC-002 requires the
branch to exist on the remote. This pass performed no git mutation, so no workflow run
exists. Complete the workflow-run evidence at push/PR time and paste the run URL plus the
step-summary dry-run notice here.

## 4. Story evidence — US3 (governance and contributor safety)

Executed: T014, T015, T016. Deferred: T017 `[DEFER-078]`.

- **T014 `GOVERNANCE.md`** — roles and decision rights, the concrete §E gate map (what
  each gate covers, who approves, how approval is recorded), the trust ladder, how
  decisions are recorded (ADRs, specs, the board), and the escalation path.
- **T015 `.github/CODEOWNERS`** — routes the load-bearing paths named in spec US3
  (`src/loopplane/model/`, `errors.py`, `events/`, `context.py`, `gateway/`,
  `host/assembly.py`), plus `.github/workflows/`, `docs/architecture/`, `docs/adr/`,
  `.specify/memory/constitution.md`, and the release/packaging surface, to the maintainer.
  Placed in `.github/` beside the existing issue and PR templates. Syntax is
  GitHub-validated only after push — check the repository's CODEOWNERS errors page then.
- **T016 `CONTRIBUTING.md`** — appended a "Hazard map" section (plus a short pointer from
  the existing "Project conventions" list). It covers the two sanctioned TYPE_CHECKING
  cycles (R1 `context ⇄ tools`, R4 `host ⇄ tools`) and why converting a lazy import is
  forbidden, the boundary-guard test system, the §E approval gates, the
  default-off/byte-identity rule, the public-safety (Constitution VII) checklist, and the
  English-docs rule. Existing sections were not rewritten or reordered.
- **T017** — `[DEFER-078]`. The ADR-0015 board-status text check must run after 078's
  board transition, and `docs/loopplane-agent-board.md` is outside this pass's allowed
  file set. Unchecked.

## 5. Story evidence — US4 (public documentation coverage)

Executed: T018–T024.

Five thematic guides were written under `docs/guides/`, each stating its covered unit
numbers in the header and deferring to `docs/capabilities.md` and `docs/api-reference.md`
as the authorities (trust ladder — the guides are navigational, never normative):

| Guide | Covered units |
| --- | --- |
| `docs/guides/agent-tools-and-permissions.md` | 033, 034, 036, 038, 039, 044, 045, 046, 047, 052, 054, 065, 066, 069 |
| `docs/guides/autonomy-and-multi-agent.md` | 013, 043, 048, 049, 050, 051 |
| `docs/guides/cost-governance.md` | 040, 041, 042, 053, 055, 062, 063, 064, 068 |
| `docs/guides/platform-and-deployment.md` | 011, 022, 056, 057, 058, 059, 060, 061, 067, 071, 072 |
| `docs/guides/web-ui-product.md` | 018, 023, 025–032, 074, 075, 076, 077, 080, 081 |

### T023 — capability-category → guide mapping (recorded per task)

Every row of the "Functional scope, by layer" table in `docs/capabilities.md` maps to a
guide reachable in one click from `docs/README.md`:

| `docs/capabilities.md` layer (units) | Reachable from `docs/README.md` via |
| --- | --- |
| Runtime core (001, 002, 021, 060) | `quickstart.md`, `embedding-host.md` (existing) + `guides/platform-and-deployment.md` for the Postgres backend |
| Loop engineering & automation (003–006) | `loop-engineering.md`, `scheduling.md`, `packs.md`, `human-review.md` (existing) |
| Knowledge, governance & observability (007–010) | `memory-recall.md`, `tool-gateway-advanced.md`, `sandbox-policy-governance.md`, `observability-debug.md` (existing) |
| Multi-agent & autonomy (013, 043, 048–051) | `guides/autonomy-and-multi-agent.md` (new) + `multi-agent-orchestration.md` (existing) |
| Model providers (020, 035, 037, 045, 070) | `model-providers.md` (existing, **extended** by this unit with the 035/037/045/070 rows that were missing) |
| Agent-capability tools (033, 034, 036, 044, 046, 047, 054, 069) | `guides/agent-tools-and-permissions.md` (new) |
| Autonomy & workflow governance (038, 039, 066) | `guides/agent-tools-and-permissions.md` (new) |
| Execution safety (052) | `guides/agent-tools-and-permissions.md` (new) + `sandbox-policy-governance.md` (existing) |
| Cost governance (053, 055, 062–064, 068) | `guides/cost-governance.md` (new) |
| Cost & efficiency (040–042) | `guides/cost-governance.md` (new) |
| Extensibility (015, 016) | `hooks.md`, `plugins.md` (existing) |
| Host surfaces (011, 012, 017–019, 022, 023, 056, 065) | `web-api-host.md`, `desktop-studio-host.md`, `cli.md`, `web-frontend.md`, `desktop-gui.md` (existing) + `guides/platform-and-deployment.md` (auth/OAuth) and `guides/agent-tools-and-permissions.md` (slash commands) |
| Transports & platform (057–061, 067, 071, 072) | `guides/platform-and-deployment.md` (new) |
| Web UI product experience (025–032, 074–077, 080–081) | `guides/web-ui-product.md` (new) |
| Packaging & release (014, 024, 073) | `release-readiness.md` (existing) + `release-process.md` (new) |

`docs/model-providers.md` was the one existing guide with missing rows: it documented
unit 020 only. A "Later provider units" section was appended covering 035 (OpenRouter /
Ollama over the OpenAI wire format), 037 (native Gemini), 045 (structured output), and
070 (Gemini thought-signature round-trip), each deferring to `capabilities.md` /
`api-reference.md`. Nothing in the unit-020 body was rewritten.

### T024 — `tests/contract/test_docs_links.py`

Stdlib-only, offline walker over `docs/**/*.md` plus `README.md`, `CONTRIBUTING.md`,
`GOVERNANCE.md`, `CHANGELOG.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`: every inline or
reference-style relative Markdown link must resolve **inside the repository**, every
intra-document `#anchor` must match a heading slug (GitHub-style slugging), and every
cross-document `file.md#anchor` must match a heading in the target file. External
`http(s)` and `mailto:` links are collected and asserted well-formed but never fetched.
Fenced code blocks are stripped before extraction, so example links in code samples are
not treated as real links.

Two additional properties are enforced: every `docs/guides/*.md` file must be linked from
`docs/README.md` (the existing `test_docs_examples_index.py` only covers `docs/*.md`, so
the new subdirectory would otherwise be unguarded), and anti-false-green tests exercise
the actual walker against a missing target and an existing target reached by a repo-escape
path. Separate self-tests cover fence stripping, reference definitions, and GitHub slug
rules including duplicate-heading numbering.

```
$ uv run pytest tests/contract/test_release_sync.py \
    tests/contract/test_release_workflow.py tests/contract/test_docs_links.py -q
...............................................                          [100%]
47 passed in 1.80s
```

The walk found no pre-existing broken links: the suite was green on its first run against
the current tree.

## 6. Story evidence — US5 (declarative import-boundary gate)

Executed: T025–T028. US6a and US7 subsequently completed; see §§10–11. T032 remains deferred behind 078.

### T025–T027 — stdlib AST matrix: RED then GREEN

`tests/contract/test_import_matrix.py` is the single declarative source for all direct
`src/loopplane` child packages and every top-level `*.py` stem. It does not import
production packages. The validator auto-discovers those entries and fails closed for both
missing and orphan matrix declarations. Each entry
has explicit runtime, `TYPE_CHECKING`, and function-scoped prefix sets plus its owning-rule
note. Diagnostics contain the source-relative path, line, scope, import edge, and rule note.

The first focused RED run used an intentionally empty matrix and proved the required
default-deny behavior before the matrix was seeded:

```
$ uv run --active pytest tests/contract/test_import_matrix.py -q
1 failed in 0.76s
FAILED ... default-deny missing entries
```

The smallest GREEN change populated the matrix from the current AST import inventory and
existing boundary guards; no production source or existing guard was modified. The four
self-tests call `_validate` directly and prove a forbidden synthetic edge, an undeclared
synthetic package, a `TYPE_CHECKING`-only edge used at runtime, and an orphan matrix entry
all produce their expected failures.

```
$ uv run --active ruff format --check tests/contract/test_import_matrix.py
1 file already formatted

$ uv run --active ruff check tests/contract/test_import_matrix.py
All checks passed!

$ uv run --active pytest tests/contract/test_import_matrix.py -q
5 passed in 1.34s

$ uv run --active pytest tests/contract/test_*boundary.py -q
60 passed, 1 warning in 5.51s
```

The single warning is the pre-existing Starlette `TestClient`/`httpx` deprecation warning
from `test_webapi_boundary.py`; it is non-failing.

Seeding reconciliation found no current source edge that conflicts with an existing boundary
guard. The following architecture-document granularity differences were recorded rather than
silently normalized: (1) TARGET §1 names the `context` → `tools` typing exception but does
not enumerate the current `context` → `approval.interactions` typing edge, so the matrix
records that source edge as type-only; (2) TARGET §2 names the R4 tool seam at
`host/assembly.py`; separately, the existing runtime
`host/capability_manager.py` → `loopplane.adapters.mcp` dependency is a composition/dependency
discrepancy, not a package-wide sanctioned direction. The matrix permits it only through an
exact-file runtime exception, while an anti-false-green synthetic `host/other.py` edge is
rejected; (3) TARGET §10 describes the observability optional-dependency pattern but not its
current function-local self-overlay import, which is recorded in the function-scoped set.
TARGET §7's tools edges remain narrow: `events.envelope`, `gateway.spi`, `memory.store`, and
the sanctioned `orchestration` public surface. No architecture document or production source
was changed.

### T028 — landing-order decision

On 2026-08-09, after reviewing the remaining queue, the user gave the user-role instruction
`好 請繼續` to continue in the already established order. This is the requested record for
handoff.md §8 decision 5: land US5 now, rather than wait for 078's Stage-C delivery review;
US6a/US7 remain separately queued. No system or tool notification was treated as approval.

## 7. Polish

### T036 — `CHANGELOG.md`

Additive only: new bullets appended to the existing `[Unreleased]` `### Added` list, in
the style of the surrounding entries. No existing line was reordered, reworded, or
removed, and no version section was promoted (promotion is the maintainer's §E release
action).

### T037 — public-safety scan (SC-007, scoped to this pass's files)

The permanent repository-wide test (`tests/contract/test_public_safety.py`) scans
`git ls-files`, i.e. **tracked** files only; this pass committed nothing, so most of its
files would not have been scanned by it. An explicit scan was therefore run over all 21
files this pass created or modified, using the same pattern families as the permanent
test — private-key blocks, cloud access-key ids, provider tokens, assigned secret values,
private IPv4 ranges, absolute Windows user paths, absolute POSIX home paths — plus three
added patterns for this workstation: the local checkout drive path, the internal
directory names in that path, and the temporary scratch path.

The scanner script lives outside the repository (in a scratch directory) precisely so its
own patterns are never committed.

```
$ uv run python <scratch>/scan082.py <repo>
public-safety scan: 21 files scanned, 0 findings
scan exit=0
```

The scan earned its keep on the way there: an earlier draft of this very evidence file
quoted the offending marker strings from 078's fixture while reporting the finding in §8,
and the scan flagged both lines (`implementation-evidence.md:423` and `:424`). The
descriptions were rewritten to name the shape of the values instead of reproducing them,
after which the scan returned zero.

**Anti-false-green check** — the pattern set was proven able to fire, on a known-bad
tracked file and on a synthetic string containing this checkout's path:

```
tests/helpers/public_safety.py -> ['absolute Windows user path']
<synthetic checkout path>      -> ['local checkout drive path', 'internal directory name']
```

So the zero-finding result over the 082 file set is a real negative, not a dead scanner.

### T038 / T039 — final tasks remain open

The earlier A-stage gate and no-touch results are historical snapshots only. US5–US7 and the
review remediations below supersede them; they cannot serve as T039 final evidence.

- **T038** remains unchecked. The main session will run the sole fresh final verification;
  this pass does not claim any final scan or full-gate result.
- **T039** remains unchecked. Its final FR-016 inventory must be derived from this
  worktree's actual `git status` and diff against base at that time, not from this document's
  historical inventory or the initial 078 checkout status.

## 8. Historical A-stage file inventory and verification (not T039 evidence)

This 33-file inventory and its status results are retained as an A-stage snapshot. Later
US5–US7 work and the review remediations supersede it; it must not be used as T039 final
evidence. The final inventory must be produced from the actual worktree `git status` and
diff against base when T039 is run.

### Created by this pass

| Path | Purpose |
| --- | --- |
| `specs/082-open-source-release-readiness/implementation-evidence.md` | this file (T003) |
| `tests/contract/test_release_sync.py` | release-sync validator contract tests (T009) |
| `tests/contract/test_release_workflow.py` | release workflow security/graph contract tests (T011) |
| `scripts/release_sync_check.py` | stdlib-only release-sync validator (T010) |
| `.github/workflows/release.yml` | tag-triggered validate → build → publish → release (T011) |
| `docs/release-process.md` | human-gated release runbook (T012) |
| `GOVERNANCE.md` | roles, decision rights, §E gate map (T014) |
| `.github/CODEOWNERS` | load-bearing paths → maintainer review (T015) |
| `docs/guides/agent-tools-and-permissions.md` | thematic guide (T018) |
| `docs/guides/autonomy-and-multi-agent.md` | thematic guide (T019) |
| `docs/guides/cost-governance.md` | thematic guide (T020) |
| `docs/guides/platform-and-deployment.md` | thematic guide (T021) |
| `docs/guides/web-ui-product.md` | thematic guide (T022) |
| `tests/contract/test_docs_links.py` | offline docs link/anchor walker (T024) |
| `tests/contract/test_import_matrix.py` | stdlib-only default-deny AST import matrix (T025–T027) |

### Modified by this pass

| Path | Change |
| --- | --- |
| `.github/workflows/ci.yml` | one added metadata-validation step (T004) |
| `README.md` | badges, install wording, extras matrix, governance links (T005) |
| `docs/getting-started.md` | install-status wording mirrored from README (sync rule) |
| `CONTRIBUTING.md` | appended hazard-map section (T016) |
| `docs/model-providers.md` | appended a "Later provider units (035, 037, 045, 070)" section and widened the title's unit list from `(unit 020)`; the unit-020 body is untouched (T023) |
| `docs/README.md` | new "Capability guides" section, `release-process.md` row, and a truthful unit list on the model-providers row (T023) |
| `docs/loopplane-agent-board.md` | one additive 082 `Implementation in progress` row; active 078 controls unchanged (T002) |
| `CHANGELOG.md` | additive `[Unreleased]` bullets (T036) |
| `specs/082-open-source-release-readiness/tasks.md` | checked the completed task boxes |

### First-pass verification in the dirty 078 checkout (historical; targeted only)

New tests, plus every existing contract test that this pass's files could plausibly break
(the docs index, the CI-gate contract, the changelog contract, packaging, public safety):

```
$ uv run pytest tests/contract/test_release_sync.py tests/contract/test_docs_links.py \
    tests/contract/test_docs_examples_index.py tests/contract/test_ci_gates.py \
    tests/contract/test_changelog.py tests/contract/test_public_safety.py \
    tests/contract/test_packaging.py -q
1 failed, 58 passed in 12.87s
```

**The one failure is pre-existing and belongs to 078, not to this unit:**

```
FAILED tests/contract/test_public_safety.py::test_committed_files_are_public_safe
  tests\helpers\public_safety.py:21: absolute Windows user path
  tests\helpers\public_safety.py:32: absolute POSIX home path
  tests\helpers\public_safety.py:35: absolute Windows user path
```

`tests/helpers/public_safety.py` is tracked, unmodified relative to `HEAD`
(`git diff HEAD -- tests/helpers/public_safety.py` is empty), and was introduced by 078's
own commit `49a2649` ("test(078): complete Phase 2 desktop harnesses and safety
fixtures"). Its synthetic marker constants are absolute user-home paths in the Windows and
POSIX forms the repository-wide scan rejects (the values are not reproduced here). It is a
**078 finding reported, not touched** — the file is 078's and outside this unit's allowed
set. No file created or modified by this pass appears in the violation list.

Final re-run after the last edit, with the 078-owned failure excluded from the selection:

```
$ uv run pytest tests/contract/test_release_sync.py tests/contract/test_docs_links.py -q
31 passed in 1.53s

$ uv run pytest tests/contract/test_docs_examples_index.py tests/contract/test_ci_gates.py \
    tests/contract/test_changelog.py tests/contract/test_packaging.py -q
14 passed in 2.07s
```

Both workflow files were re-parsed after the final `ci.yml` edit:

```
$ uvx --from pyyaml python -c "...safe_load both workflow files..."
.github/workflows/ci.yml OK ['test']
.github/workflows/release.yml OK ['validate', 'build', 'publish', 'release']
ci steps: ['actions/checkout@v4', 'astral-sh/setup-uv@v6', 'Install dependencies',
           'Lint', 'Format check', 'Type check', 'Tests', 'Build distribution',
           'Validate distribution metadata']
```

Linting of the new Python files (only the new files, not the whole tree):

```
$ uv run ruff check scripts/release_sync_check.py tests/contract/test_release_sync.py \
    tests/contract/test_docs_links.py
All checks passed!

$ uv run ruff format --check scripts/release_sync_check.py \
    tests/contract/test_release_sync.py tests/contract/test_docs_links.py
3 files already formatted
```

Workflow YAML was machine-parsed (no repository dependency added — a transient
`uvx --from pyyaml python` invocation) and its job graph asserted against the contract:

```
$ uvx --from pyyaml python -c "...safe_load both workflow files..."
.github/workflows/release.yml
.github/workflows/ci.yml
YAML OK

triggers: ['push', 'workflow_dispatch']
workflow permissions: {'contents': 'read'}
--- validate   needs: None                       perms: None
--- build      needs: validate                   perms: None
--- publish    needs: ['validate', 'build']      perms: {'contents': 'read', 'id-token': 'write'}
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') &&
        github.repository == '<owner>/loopplane' && needs.validate.outputs.dry-run == 'false'
--- release    needs: ['validate', 'build', 'publish']  perms: {'contents': 'write'}
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') &&
        github.repository == '<owner>/loopplane'
```

Not run in that first pass, with reasons: `uv run pytest -q` (whole suite) and
`uv run mypy` (configured over `src`, which carried 078's WIP), `uv run ruff check .` /
`ruff format --check .` (whole tree), the fresh-venv install validation (T006), and the
frontend suites. YAML parsing is not the same as GitHub Actions expression validation: the
first real machine validation of `release.yml` still happens only after push.

### Clean-branch A-stage verification (2026-08-09)

All commands below ran from branch `082-open-source-release-readiness` based exactly on
`origin/main` commit `e2214f517b38e8be89cd38cbe92a010df13785c5`.

```
$ uv run ruff format --check .
478 files already formatted

$ uv run ruff check .
All checks passed!

$ uv run mypy
Success: no issues found in 201 source files

$ uv build
Successfully built dist\loopplane-0.4.0.tar.gz
Successfully built dist\loopplane-0.4.0-py3-none-any.whl

$ uv run pytest tests/contract/test_release_sync.py \
    tests/contract/test_release_workflow.py tests/contract/test_docs_links.py -q
47 passed in 1.80s
```

The final comprehensive command's attempt to invoke `uvx twine` again was denied by the
session's external-code classifier before that command ran. The latest successful Twine
result remains the pass recorded under T006 (wheel + sdist both `PASSED`), executed after
the final README metadata wording. Subsequent changes were limited to workflow, validator,
tests, CHANGELOG, and Spec Kit evidence/contracts; neither `pyproject.toml` nor README
metadata changed. Twine was therefore not downloaded or re-executed in the final bundle.

Release-sync quickstart:

```
$ uv run python scripts/release_sync_check.py v0.4.0
PASS: release sync checks passed for v0.4.0
(exit 0; dated [0.4.0] notes emitted to stdout)

$ uv run python scripts/release_sync_check.py v9.9.9
[fail] __version__ is 0.4.0, expected 9.9.9
[fail] CHANGELOG.md has no released, dated section [9.9.9]
FAIL: 2 release-sync check(s) failed; nothing may be published.
(exit 1 as required)
```

Full-suite path handling and final result:

1. The literal `uv run pytest -q` first failed during fixture setup because the clean
   worktree did not contain the configured `tmp/` parent for `--basetemp=tmp/pytest`.
2. After creating that parent, the run reached the tests but path-heavy capability-store
   cases failed: their SHA-256 + UUID atomic filenames exceeded the legacy Windows path
   limit under the deep `.claude/worktrees/...` root and were normalized to the public-safe
   `capability settings are unavailable` result. A focused reproduction exposed the
   underlying `FileNotFoundError`; no 082 source file was involved.
3. The same suite was re-run in the same worktree with a Windows `\\?\` long-path
   basetemp, preserving all code and test semantics:

```
$ uv run python -c "... pytest.main(['-q', '--basetemp=<long-path>']) ..."
1543 passed, 8 skipped, 1 warning in 111.26s (0:01:51)
```

The warning is Starlette's dependency deprecation notice for `fastapi.testclient` using
`httpx`; it is pre-existing and non-failing. The frontend suites were not run because this
unit touched no `apps/**` or `packages/**` path and FR-016 expressly forbids doing so while
078 is unverified. Generated `.venv`, wheel/sdist, and fresh-install artifacts were removed.
A final focused contract rerun passed **47 tests** using the unique gitignored basetemp
`tmp/082-final-20260809-a1`; the session classifier declined recursive cleanup of `tmp`, so
that ignored local test directory remains but does not appear in git status or the 33-file
change inventory.

A fresh public-safety scan then covered all **33** final changed/untracked files using the
repository's built-in pattern families plus dynamically derived local-checkout/path-part
patterns. Result: **0 findings**. Its anti-false-green probe asserted that the exact local
checkout pattern matched a synthetic in-memory value. The temporary scanner was removed
before the final status review.

### Current `git status` review

Reviewed on the clean 082 worktree after generated validation artifacts were removed
(`git status --porcelain` and `git diff --check`).

**Tracked files modified — exactly eight, all 082-scoped:** `.github/workflows/ci.yml`,
`CHANGELOG.md`, `CONTRIBUTING.md`, `README.md`, `docs/README.md`,
`docs/getting-started.md`, `docs/loopplane-agent-board.md`, and
`docs/model-providers.md`.

**Untracked paths added — exactly ten, all 082-scoped:** `.github/CODEOWNERS`,
`.github/workflows/release.yml`, `GOVERNANCE.md`, `docs/guides/`,
`docs/release-process.md`, `scripts/release_sync_check.py`,
`specs/082-open-source-release-readiness/`, `tests/contract/test_docs_links.py`,
`tests/contract/test_release_sync.py`, and `tests/contract/test_release_workflow.py`.

There are no 078 WIP files, `.superpowers/**`, `openspec/**`, generated distributions,
virtual environments, or test-temp paths in the status list. `git diff --check` is clean.

**No FR-016 no-touch path changed.** Specifically unchanged: `pyproject.toml`, `uv.lock`,
root `package.json` / `package-lock.json`, everything under `apps/**`, `packages/**`,
`src/loopplane/host/**`, `src/loopplane/controller/**`, `scripts/verify-desktop-stage-b.ps1`,
`.github/workflows/desktop.yml`, `docs/adr/0015-desktop-cowork-boundary.md`,
`specs/078-desktop-cowork-parity/**`, `tests/**/test_desktop*`, and
`tests/helpers/desktop_*`. Also unchanged: `.superpowers/**`, `openspec/**`,
`.specify/feature.json`, and the SPECKIT-managed blocks in `AGENTS.md` / `CLAUDE.md`.
The board diff is exactly the one additive 082 row described under T002.

**Nothing was staged or committed.** The only git mutations were the worktree/branch
creation and branch rename performed under the maintainer's continuation-queue instruction;
no push, PR, tag, workflow dispatch, release, or publish occurred.

### Historical 078 finding from the source checkout (not present on this base)

In the original dirty 078 checkout,
`tests/contract/test_public_safety.py::test_committed_files_are_public_safe` failed because
078 commit `49a2649` added synthetic marker constants in
`tests/helpers/public_safety.py` whose values have absolute user-home path shapes rejected
by the repository-wide scanner. The exact strings are not reproduced here. The clean 082
branch is based on earlier `main` commit `e2214f5`, does not contain that 078 commit, and
its full suite — including public safety — passed. The 078 finding remains report-only and
was not imported or fixed by unit 082.

## 9. Historical §H completion report — continuation A stage (superseded)

This continuation-A report predates US5–US7 and the review remediations. It is historical
context only, not a completion report and not T039 final evidence.

1. **What changed.** Created the clean `082-open-source-release-readiness` branch/worktree
   from `origin/main`; transferred only the existing 082 release, governance, docs, tests,
   scripts, and Spec Kit artifacts; registered one 082 board row; and completed the
   fresh-wheel validation evidence. No runtime source, frontend, 078, dependency, default,
   schema, or outward API contract changed.
2. **Verification.** PASS: Ruff format (478 files), Ruff lint, mypy (201 source files),
   full pytest (1543 passed / 8 skipped / 1 pre-existing warning), `uv build`, the latest
   applicable Twine checks for wheel + sdist, fresh Python 3.12.9 wheel install with
   `[web,anthropic]`, credential-free host quickstart, installed `loopplane run`,
   release/workflow/docs contracts (47 passed), release-sync positive/negative paths, a
   focused code-review PASS, and `git diff --check`. The final Twine re-invocation was denied
   before execution by the external-code classifier; §8 records why the earlier successful
   metadata result remains applicable. Two preliminary pytest
   attempts failed for environment/path setup as documented in §8; the unchanged suite
   passed with a Windows long-path basetemp. Frontend suites were skipped because FR-016
   forbids touching their paths and this change-set contains no frontend changes.
3. **§E approvals.** The maintainer's genuine user-role instruction on 2026-08-09 was to
   read the continuation handoff and execute its §3 queue; that instruction covered the
   local T001/A-stage work described here. No separate user-role approval was received for
   commit, push, PR, workflow dispatch, dependency/extra changes, version/CHANGELOG
   promotion, tag, release, or publish, and none of those actions occurred.
4. **Limitations / deferred work.** The gitignored final focused-test basetemp remains at
   `tmp/082-final-20260809-a1` because the session classifier declined recursive cleanup of
   `tmp`; no tracked/untracked change is introduced. T013's GitHub `workflow_dispatch`
   dry-run requires a pushed branch and remains deferred. CODEOWNERS syntax receives GitHub's authoritative
   validation only after push. T025–T035 (US5/US6/US7) await the maintainer's landing-order
   decision relative to 078 Stage-C. T007/T008/T017/T032 remain blocked until 078 is
   `Verified`; T008 also requires explicit approval of any new extra. Consequently T038
   and T039 remain unchecked despite current A-stage PASS evidence.
5. **Rollback.** No commit exists. Removing this worktree discards the isolated 082 copy;
   if later committed, each documented story is designed to remain independently
   `git revert`-able.

## 10. Story evidence — US6a WebAPI route decomposition (T029–T031)

Executed: T029–T031. `src/loopplane/webapi/app.py` is now the composition root for
one lifespan, one shared state/helper ownership set, validation-error handling, and
ordered router mounting. Domain routers under `src/loopplane/webapi/routers/` receive
one immutable `RouterState` by reference; state and helpers were not copied.

### T029 — pre-split fixed baseline: RED then GREEN

The new contract test was written before any route was re-filed. Its initial focused
run intentionally failed because the checked-in static fixture did not yet exist; the
test never generates or accepts a new snapshot at runtime:

```
$ uv run pytest tests/contract/test_webapi_route_snapshot.py -q
5 failed in 7.48s
FAILED ... T029 pre-split route baseline is not checked in
```

One capture was then performed against the unchanged pre-split `app.py`; the temporary
capture helper was removed immediately. The committed literal fixture records **60 HTTP
routes** (sorted methods, path, endpoint name, response-model class name, and status
code), **1 WebSocket route** (path and endpoint name), the **67,326-byte** canonical
OpenAPI JSON, and the complete `inspect.signature(create_app)` string. The pre-split
baseline then passed:

```
$ uv run pytest tests/contract/test_webapi_route_snapshot.py -q
5 passed in 1.19s
```

### T030–T031 — invariant split and recursive boundary guard: GREEN

The post-split baseline was run without changing its fixture:

```
$ uv run pytest tests/contract/test_webapi_route_snapshot.py -q
5 passed in 5.62s

$ uv run pytest tests/contract/test_webapi_boundary.py -q
4 passed, 1 warning in 4.99s
```

`test_webapi_boundary.py` now recursively scans every Python module below
`src/loopplane/webapi/`, including all router modules. The one warning is the existing
Starlette TestClient/httpx deprecation warning and is non-failing.

The first complete WebAPI behavior selection run without a long-path basetemp reported
10 capability-management failures. Those tests returned the existing public-safe
capability-store unavailable result when the nested Windows worktree test path exceeded
the legacy path limit; a focused affected test passed with the repository-local Windows
long-path basetemp. The same long-path setting was therefore used for the final WebAPI
regression selection:

```
$ uv run python <temporary long-path runner>
123 passed, 1 warning in 21.08s
```

Final §G evidence after the split:

```
$ uv run ruff format --check .
489 files already formatted

$ uv run ruff check .
All checks passed!

$ uv run mypy
Success: no issues found in 210 source files

$ uv run python <temporary long-path runner>
1553 passed, 8 skipped, 1 warning in 160.64s
```

Both temporary runners were removed after use. **No §E outward-contract gate was
triggered:** the pre-split literal inventory, WebSocket route, canonical OpenAPI JSON,
and complete `create_app` signature all remained unchanged; recursive boundary and
behavior regressions are green.

## 11. Story evidence — US7 architecture audit and verified test-debt backfill (T033–T035)

Executed: T033, T034, and T035. Scope was limited to the confirmed architecture-audit
rows and their direct test seams. No production behavior, dependency, schema, default,
or public API changed.

### T033 — audit refresh

`docs/architecture/ARCHITECTURE_AUDIT.md` is refreshed as a 2026-08-09 snapshot against
base commit `e2214f5` plus the current 082 worktree. It now cites direct source/test/doc
evidence instead of retaining stale broad assertions.

- Removed/replaced the stale claims that controller lacked a dedicated test, errors had
  only indirect coverage, engineering had only one focused test, and memory/skills had
  only indirect coverage. The audit names the current direct test files and their actual
  coverage seams.
- Removed/replaced the stale README unit-013, capabilities/CHANGELOG unit-063/0.4.0, and
  API unit-072 snapshot claims. README now has install/extras/CLI coverage;
  capabilities reaches 077 plus 080–081; CHANGELOG has an Unreleased 064–082 section;
  API reference is guarded by `test_api_reference.py`.
- Retained one direct document finding: `docs/gap-analysis.md` self-identifies as through
  075 despite board-verified 076/077/080/081. The base worktree's 078 row and active-feature
  text both say Not started; no other-worktree WIP was used as audit evidence. No speculative
  test, example, live-model, or packaging debt was added.

### T034 — RED then GREEN focused tests

The controller behavior was already correct, so the required initial RED used a missing
**test-only** `_checkpoint_store` helper; it did not claim a production failure:

```
$ uv run pytest tests/unit/test_controller_core.py -q
1 failed, 6 passed in 3.38s
FAILED ... NameError: name '_checkpoint_store' is not defined
```

The smallest GREEN change added that test helper and one async test. It drives
`RuntimeController` with `FileCheckpointStore`, asserts exact persisted record order
`SessionMetaRecord → UserInputRecord → AssistantMessageRecord → TerminationRecord`,
asserts record sequences `1, 2, 3, 4`, and has the forwarded terminal-event sink read the
store and require the terminal record before accepting the event:

```
$ uv run pytest tests/unit/test_controller_core.py -q
7 passed in 1.16s
```

The memory behavior was also already correct. Its initial RED likewise came from the
intentionally missing **test-only** `_entry` fixture helper, not a production defect:

```
$ uv run pytest tests/unit/test_memory_core.py -q
1 failed in 0.73s
FAILED ... NameError: name '_entry' is not defined
```

The smallest GREEN change supplied the fixture and retained one direct CRUD test covering
`MemoryStore.get()` present/missing plus `delete()` successful/missing branches:

```
$ uv run pytest tests/unit/test_controller_core.py tests/unit/test_memory_core.py -q
8 passed in 1.34s
```

A separate skills descriptor SPI test was deliberately not added. Direct inspection found
`tests/unit/test_skills.py` already covers loading, descriptor-backed execution profiles,
malformed input, merge precedence, substitution, and advertisement. No minimal confirmed
SPI gap remained, so adding another test would expand scope.

### T035 — terminal-record mutation (RED) and restoration (GREEN)

After the normal focused suite was green, the terminal branch in
`src/loopplane/checkpoint/recorder.py::RecordingSink.__call__` was temporarily removed
(the `RunTerminatedEvent` / `record_termination` conditional only). The new controller
test failed while forwarding the terminal event because the latest durable record was an
`AssistantMessageRecord`, not a `TerminationRecord`:

```
$ uv run pytest tests/unit/test_controller_core.py -q
1 failed, 6 passed in 1.65s
FAILED ... assert isinstance(records[-1], TerminationRecord)
```

The exact production branch was restored immediately. Focused tests and an explicit
production-file diff check then passed:

```
$ uv run pytest tests/unit/test_controller_core.py tests/unit/test_memory_core.py -q \
    && git diff --exit-code -- src/loopplane/checkpoint/recorder.py
8 passed in 1.35s
(exit 0)
```

The mutation is absent from the final diff; `src/loopplane/checkpoint/recorder.py` is
byte-for-byte unchanged relative to the worktree baseline.

## 12. Final review-finding remediation (targeted; not final-gate evidence)

- **Release tag TOCTOU.** RED: the added workflow contract failed with **1 failed, 8
  passed** because `validate` exposed no checked-out SHA and `build` re-resolved the mutable
  tag/ref. GREEN: **9 passed** after `validate` records `git rev-parse HEAD`, exposes that
  SHA as a job output, and `build` checks out only `needs.validate.outputs.sha`.
- **Import-matrix fail-open.** The matrix now discovers every direct top-level `*.py` stem,
  resolves relative `ImportFrom` edges using the inspected file's package, and applies the
  `host/capability_manager.py` MCP exception by exact path only. The focused matrix suite is
  GREEN at **8 passed**, including new cross-package-relative, undeclared-top-level-module,
  and non-capability-manager host-MCP anti-false-green cases.
- **Audit/evidence status.** The unsupported board-conflict audit finding was removed; only
  the evidence-backed `gap-analysis.md` through-075 gap remains. The 33-file/A-stage and
  continuation-A sections above are explicitly historical and cannot establish T039.

No final full-suite scan, final no-touch inventory, or final gate PASS is claimed here; those
are reserved for T038/T039.

## 13. T038/T039 final local verification and §H completion report

Executed 2026-08-09 on branch `082-open-source-release-readiness` at base/HEAD
`e2214f517b38e8be89cd38cbe92a010df13785c5`. All 35 tasks currently executable before
078 reaches `Verified` are complete; T007/T008/T017/T032 remain explicitly deferred.

### Fresh §G gates

```
$ uv run ruff format --check .
490 files already formatted

$ uv run ruff check .
All checks passed!

$ uv run mypy
Success: no issues found in 210 source files

$ uv run pytest -q --basetemp=<repository-local Windows long path>
1559 passed, 8 skipped, 1 warning in 141.82s

$ uv build
Successfully built dist/loopplane-0.4.0.tar.gz
Successfully built dist/loopplane-0.4.0-py3-none-any.whl
```

The one warning is the pre-existing Starlette `TestClient` / `httpx` deprecation warning.
Neither named known flake failed in the full suite, so no isolation rerun was required. The
fresh `uvx twine check --strict dist/*` invocation was denied before execution by the
external-code classifier because it would download and execute Twine. The earlier successful
Twine wheel/sdist metadata result in the historical A-stage evidence remains applicable:
`pyproject.toml`, its metadata inputs, and the README metadata surface were not changed after
that check. This limitation is reported rather than treated as a fresh Twine execution.

### Fresh-wheel and quickstart proof

A new Python 3.12.9 environment was created under a gitignored repository-local temporary
path. The freshly built wheel installed with `[web,anthropic]` and resolved 25 packages. An
independent runner verified that `loopplane.__file__` came from that environment's
`site-packages` and that the repository root was absent from `sys.path`, then ran
`examples/host_quickstart.py` to natural completion. The installed `loopplane run "hello"`
console script also completed with the credential-free canned model. Generated wheel, sdist,
venv, runner, and long-path pytest artifacts were removed afterward.

The release validator's real CLI paths were also rerun: `v0.4.0` passed version, dated
CHANGELOG, and board-status synchronization; `v9.9.9` exited 1 with two fail-closed
diagnostics and empty stdout.

### Final public-safety and FR-016 inventory

The final explicit SC-007 scanner combined all 12 tracked modifications with all 38 untracked
files (**50 text files total**), applied the permanent built-in secret/private-network/user-path
patterns plus dynamically derived exact local-checkout, local-home, and user-component patterns, and ran
an anti-false-green assertion against the exact checkout pattern. Result: **0 findings**.

The final inventory compared tracked changes to `HEAD`, included every non-ignored untracked
file, and separately inspected the staged list:

```
tracked_modified=12
untracked_files=38
total_changed=50
staged=0
fr016_forbidden=0
```

No `pyproject.toml`, lockfile, root package manifest, `apps/**`, `packages/**`,
`src/loopplane/host/**`, `src/loopplane/controller/**`, desktop workflow/script/ADR/spec/test,
or other FR-016 path is modified. `git diff --check` passed. Nothing is staged, committed,
pushed, tagged, dispatched, released, or published.

### Assurance closure

The first focused code and architecture reviews found four code/completion issues and four
architecture/inventory issues. Repairs pinned the build to the validated checkout SHA, closed
relative-import and top-level-module matrix bypasses, narrowed the existing host MCP edge to
one exact file, removed a false audit debt, and refreshed CHANGELOG/board/evidence state.
Targeted re-review marked all prior code and architecture findings fixed; the code reviewer
left only the intentionally pending final public-safety scan, which the zero-finding result
above closes. The WebAPI route/OpenAPI/signature contract and behavior suites remained green.

### §H completion report

1. **What changed.** Added fail-closed release automation and validation, governance and
   ownership files, public capability guides and link contracts, a default-deny import matrix,
   an outward-contract-preserving WebAPI router decomposition, and a refreshed architecture
   audit with direct controller/checkpoint and memory CRUD tests. No outward contract, schema,
   dependency, default, or FR-016 path changed.
2. **Verification.** PASS: Ruff format/lint, mypy, full pytest (**1559 passed / 8 skipped /
   1 warning**), build, fresh-wheel `[web,anthropic]` install, host quickstart, installed CLI,
   release validator positive/negative paths, **50-file / 0-finding** public-safety scan,
   **0** staged paths, **0** FR-016 paths, `git diff --check`, and final code/architecture
   re-review. Fresh Twine execution was classifier-denied; the last applicable metadata PASS
   and its unchanged inputs are recorded above.
3. **§E / outward actions.** No approval exists for commit, push, PR, workflow dispatch,
   dependency/extra changes, version promotion, tag, GitHub Release, or PyPI publication;
   none occurred. The release workflow dispatch dry-run and authoritative GitHub CODEOWNERS
   validation remain post-push actions.
4. **Limitations and deferred work.** T007 (packaging URLs/classifiers), T008 (any approved
   convenience extra), T017 (ADR-0015 status convergence), and T032 (`capability_manager.py`
   decomposition) wait for 078 to become `Verified`; T008 additionally needs explicit
   maintainer approval. The board remains `Implementation in progress` until those deferrals
   are resolved or dispositioned and the maintainer signs off.
5. **Rollback.** No commit exists. The isolated 082 worktree can be discarded to remove all
   local work; after a future approved commit, the independent story layout supports bounded
   `git revert` rollback.
