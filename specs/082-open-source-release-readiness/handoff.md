# Unit 082 Handoff — Open-Source Readiness: Architecture Analysis and Execution Basis

> **Continuation status (2026-08-09)**: 23/39 tasks are complete on an uncommitted clean 082 worktree based on `origin/main`; current local gates are recorded, while US5/US6/US7 and the 078-sensitive tail remain blocked. Live status, the remaining-work queue, and re-entry instructions are in [handoff-continuation.md](handoff-continuation.md) — read that first when resuming; this file remains the stable analysis + constraints reference.

> Prepared 2026-08-08 by an analysis-only session for the implementing agent of unit 082 (planned: a fresh Claude Opus 5 session). Companion to [spec.md](spec.md). This document records the architecture analysis that motivates the unit, the repository state at handoff, and the constraints the implementer must honor. On conflict: constitution > `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` > this file.

## 1. Mission

The maintainer's goal is to **open-source LoopPlane**. The product today has three usage surfaces over one Python runtime: **CLI** (`loopplane` console script), **Web** (`apps/web` SPA over the `webapi` host), and **Cowork desktop** (`apps/desktop`, Electron + Python sidecar — unit 078, in flight). A three-track architecture review (Python core / frontends / docs+release state) was performed on 2026-08-08; its verdict and evidence are in §2–§4. Unit 082 executes the resulting adjustments **in phases** (maintainer's explicit direction: low-risk consolidation and release readiness first; larger refactors as later, independently verifiable stories).

Your job as implementer: run this unit through the Spec Kit flow (plan → tasks → analyze → implement) against [spec.md](spec.md), honoring the sequencing and no-touch constraints below.

## 2. Architecture analysis — verdict

**The runtime architecture is suitable for open-sourcing as-is. No architectural rework is required before going public.** The adjustments in this unit are distribution/governance/documentation mechanics plus contributor-scale internal debt — none change runtime behavior.

### 2.1 What is strong (do not disturb)

| Strength | Evidence |
| --- | --- |
| Layered core: Phase-1 runtime ← Phase-2 hosts ← Phase-3 engineering; ~31 subpackages, ~19.4k LOC | `src/loopplane/`; `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` (G1–G8) |
| Single tool chokepoint (Gateway, 6-stage pipeline), single outbound event seam (`EventSink`), versioned schemas | Constitution IV–VI; `src/loopplane/gateway/`, `src/loopplane/events/` |
| 17 AST-based boundary guard tests, incl. bidirectional guards and a meta-guard | `tests/contract/test_*_boundary.py`, `tests/integration/test_{cli,hooks,plugins}_boundary.py` |
| Minimal base deps (anyio/pydantic/jsonschema) + 9 optional extras behind 4 sanctioned patterns; strict mypy; default-off/byte-identical knob rule | `pyproject.toml`; `TARGET_ARCHITECTURE_BOUNDARIES.md` G4/G5 |
| Governance artifacts unusually mature: constitution (10 principles), 15 Accepted ADRs, risk register (R1–R13), release-sync rules, handoff template | `.specify/memory/constitution.md`; `docs/adr/`; `docs/architecture/` |
| Desktop sidecar **reuses** the core instead of reimplementing it: imports only `loopplane.host` / `.events` / `.model`; all session/agent/persistence logic delegates to `LoopPlaneHost`; webapi and sidecar are two thin adapters over the same host facade | `apps/desktop/sidecar/` import scan; ADR 0015; `tests/contract/test_desktop_boundary.py` |
| Web app mature (57 test files / ~192 cases) with REST + WebSocket transports behind one `SessionTransport` interface | `apps/web/src/api/` |
| Two deliberate TYPE_CHECKING-quarantined cycles (`context ⇄ tools`, `host ⇄ tools`) are documented load-bearing compromises, mechanically guarded | R1/R4 in `docs/architecture/RISK_REGISTER.md`; `src/loopplane/context.py`, `src/loopplane/host/assembly.py` |

### 2.2 Gaps found (what this unit fixes)

| # | Gap | Evidence | Addressed by |
| --- | --- | --- | --- |
| 1 | Not installable from a package index; README concedes clone-only install; name `loopplane` unclaimed on PyPI as of 2026-08-08 | `README.md` Install; PyPI JSON API 404 | US1 |
| 2 | 16 verified units (064–077, 080–081) unreleased; latest tag `v0.4.0` (units ≤063); no release automation (CI builds but nothing publishes on tag) | `CHANGELOG.md` `[Unreleased]`; `.github/workflows/ci.yml` | US2 |
| 3 | No `GOVERNANCE.md` / `CODEOWNERS` / public maintainer model; "maintainer-authorized" gates referenced everywhere but undocumented publicly | repo root; board Global Rules | US3 |
| 4 | Contributor hazard map missing: an outsider's most likely first PR is "fixing" a guarded compromise (lazy imports, boundary edges) | R1/R4; `AGENTS.md` forbidden actions | US3 |
| 5 | Docs index layer guides stop at unit 020; units 021–081 discoverable only via reference tables/CHANGELOG | `docs/README.md` | US4 |
| 6 | R10: no static default-deny import gate; each of the 17 guards is bespoke; a new package ships unguarded by default | `docs/architecture/RISK_REGISTER.md` R10 | US5 |
| 7 | Oversized modules: `src/loopplane/webapi/app.py` (~1.27k lines, ~60 routes; risk R11) and `src/loopplane/host/capability_manager.py` (~1.5k lines, largest file) | R11; file sizes | US6 |
| 8 | `ARCHITECTURE_AUDIT.md` snapshot (2026-07-06) is past its own ~10-unit refresh window and provably stale in places — its test-gap table claims `controller/` has no dedicated test file, but `tests/unit/test_controller_core.py`, `test_controller_capability_seams.py`, `test_errors_core.py`, `test_engineering_core.py` exist today; residual coverage depth unverified | audit file vs `tests/unit/` listing (verified 2026-08-08) | US7 (refresh first, then backfill confirmed gaps) |
| 9 | ADR 0015 status drift: ADR file says Accepted (2026-08-05); board §4/row text still says Proposed in places | `docs/adr/0015-desktop-cowork-boundary.md` vs `docs/loopplane-agent-board.md` | US3 (post-078 check) |
| 10 | Packaging metadata gaps: missing Changelog/Issues/Documentation URLs and OS classifier; no convenience extra (`all`/`server`) | `pyproject.toml` | US1 (extra needs §E approval) |

### 2.3 Findings that are explicitly NOT this unit's scope

- **UI sharing is incomplete by design-in-progress, not by architecture flaw.** `packages/cowork-presentation` has only 2 components and is Desktop-only; `apps/web` imports none of it; Desktop instead reaches into Web's `src/` via an undeclared `@web/*` tsconfig/vite alias, and real partial duplication exists (`focus.ts` vs `useFocusTrap.ts`, `models.ts` vs `api/types.ts`, desktop `SessionSidebar.tsx` vs web `Sidebar.tsx`). **This is exactly 078's remaining work (tasks T062/T063/T066)** — finishing 078 is the fix. Unit 082 must not touch it.
- CLI is a thin host (4 subcommands: `chat`, `run`, `sessions`, `resume`); remote/API parity for CLI is reserved unit **079**, blocked on 078.
- Runtime roadmap tails (distributed multi-worker, docker sandbox, MCP interactive OAuth, metering, IDE/voice): tracked in `docs/gap-analysis.md` §C4, untouched here.

## 3. Functional scope inventory (condensed)

Authorities (trust ladder): `src`+`tests`+`pyproject.toml` > `docs/loopplane-agent-board.md` (sole completion authority) > `docs/api-reference.md` > `specs/` > `docs/capabilities.md`/`docs/gap-analysis.md`. The full per-layer inventory lives in `docs/capabilities.md`; do not restate it — this is the one-screen orientation:

- **Runtime core** (001–002, 021, 060): agent loop, Tool Gateway (internal + MCP), Event Bus, durable checkpoint/resume (File/SQLite/Postgres), memory, skills, approvals, artifacts.
- **Loop engineering** (003–006): outer control loop `run_loop`, scheduler, validator/evaluator packs, human-review workflows.
- **Knowledge/governance/observability** (007–010): recall, gateway discovery, deny-wins policy deciders, metadata-only observability.
- **Autonomy** (013, 043, 048–051): host-driven orchestration, model-driven subagents, background tasks, agent scheduling, messaging/swarm, worktree isolation — all cap-gated, default-off.
- **Providers** (020, 035, 037, 045, 070): Anthropic, OpenAI, OpenRouter, Ollama, native Gemini; structured output.
- **Agent tools** (033–034, 036, 044, 046–047, 054, 069): file tools, web fetch/search (default-deny egress), images + PDF, todo, notebook, undo. 17 gateway-reachable tools total.
- **Workflow governance** (038–039, 066): plan mode, permission rule DSL, permission modes.
- **Cost** (040–042, 053, 055, 062–064, 068): prompt caching, compaction, pricing, USD caps, durable per-principal monthly ledger, pre-turn guard.
- **Hosts** (011–012, 017–019, 022–023, 056, 065): webapi (REST/SSE/WS, ~60 routes, default-deny auth, JWT/JWKS), studio, CLI, web SPA + login, desktop GUI, slash commands.
- **Platform** (057–061, 067, 071–072): MCP transports/resources, resumable SSE + durable replay store, Postgres backends, per-principal host pool, fairness/quota.
- **Web UX** (025–032, 074–077, 080–081): full chat product surface, inspection, capability management, session management, a11y/visual refactor, agent controls.
- **Board state (2026-08-08)**: units 001–077 and 080–081 **Verified**; **078 active** (Stage-B T005 accepted, T006+ authorized, Stage-C T090 pending; 66/101 tasks done); **079 reserved, not started**. Next free unit number: **082** (this unit).

## 4. Repository state at handoff (read before planning)

- **Active branch belongs to 078** and carries heavy uncommitted WIP (~16 modified + ~40 untracked files across `apps/desktop`, `apps/web`, `packages/cowork-presentation`, `src/loopplane/{host,controller}`, tests). Unit 082 work MUST NOT be mixed into 078's branch/commits. Start 082 from `main` on its own `082-open-source-release-readiness` branch (branch creation is a maintainer-confirmed action).
- **Known WIP defect (078's, not yours)**: `apps/desktop/electron/main.ts` currently contains invalid TypeScript (`*,` Python-style keyword-only marker in a parameter list, circa line 29) plus a call site passing an object literal to a positional parameter — desktop typecheck/build fails in that worktree. Do not fix it under 082; it belongs to 078.
- **Stage-B binding (the reason for FR-016)**: 078's accepted reviews bind exact bytes of `pyproject.toml`, `uv.lock`, and the root npm manifests/lock; byte-changes to those before 078 is Verified force 078 back through its review gates. Hence US1's `pyproject.toml` edits are deferred until 078 is Verified.
- **Recorded baselines** (from `specs/078-desktop-cowork-parity/plan.md`): Python `1496 passed, 8 skipped`; Web 57 files / 192 Vitest; Desktop 3 files / 12 Vitest (pre-078-WIP). These are reference points only — capture **fresh** counts on your clean 082 branch before claiming anything.
- Known flaky tests: `tests/integration/test_examples_smoke.py` and `test_us2_mcp` under load — re-run in isolation before drawing conclusions; do not run the full pytest suite concurrently with multi-agent workflows.

## 5. Required reading order

Per `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` §A, then unit-specific:

1. `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` (§E gates and §F forbidden actions are binding)
2. `.specify/memory/constitution.md`
3. `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`
4. `docs/loopplane-agent-board.md`
5. This unit: `specs/082-open-source-release-readiness/{spec.md, handoff.md}` (+ your generated plan/tasks)
6. `docs/architecture/{ARCHITECTURE_AUDIT.md, RISK_REGISTER.md}` (US5/US6/US7 touch load-bearing areas)
7. `AGENTS.md`; for US2: `docs/architecture/RELEASE_SYNC_RULES.md` and `docs/release-readiness.md`; for US4: `docs/README.md`, `docs/capabilities.md`, `docs/api-reference.md`

## 6. Hard constraints

1. **078 no-touch set while 078 is not Verified** (FR-016): `pyproject.toml`, `uv.lock`, root `package.json`/`package-lock.json`, `apps/**`, `packages/**`, `src/loopplane/host/**`, `src/loopplane/controller/**`, `scripts/*desktop*.ps1`, `.github/workflows/desktop.yml`, `docs/adr/0015-*`, `specs/078-*/**`, desktop-related tests (`tests/**/test_desktop*`, `tests/helpers/desktop_*`).
2. **§E human gates in play for this unit**: releases (version/CHANGELOG/tag — maintainer performs), new dependencies or extras (incl. `import-linter` and any `all`/`server` extra — ask first), any outward web/API contract change (US6a must prove it made none).
3. **Sequencing** (from spec Assumptions): start now → US2/US3/US4 (new standalone files + README/CHANGELOG-additive), US5/US6a/US7 (src/tests outside 078's files; coordinate landing order with the maintainer relative to 078's Stage-C). Blocked until 078 Verified → US1's `pyproject.toml` edits, US6b (`capability_manager`), FR-009 board-text check.
4. **Public-safety (Constitution VII)**: no internal/company paths, private names, or secrets in any committed file; scan every changed file (SC-007). Docs in English.
5. **Byte-identity**: no default-value change, no `SCHEMA_VERSION`/`RECORD_SCHEMA_VERSION` change, no runtime-dependency change, no re-exports added to `src/loopplane/__init__.py`, never convert lazy/TYPE_CHECKING imports to top-level.
6. **Git discipline**: never blind bulk `git add` (reset → add explicit files → review staged list as a separate step → commit); one revertable commit per story where practical; never stage `.superpowers/**`, `openspec/**`, or unrelated WIP; commits/branches/PRs only per `AGENTS.md` rules or explicit maintainer instruction.

## 7. Execution protocol

1. Register the unit: add an 082 row to `docs/loopplane-agent-board.md` following the format of rows 079–081 (status "Not started" → progress per board rules). Confirm with the maintainer if autopilot is active, since the board is its control document.
2. Run the Spec Kit flow for 082: `plan` → `tasks` → `analyze` → `implement`, keeping stories independently deliverable (Constitution X).
3. Verification gates (per template §G): `uv run ruff format --check .` / `uv run ruff check .` / `uv run mypy` / `uv run pytest -q` plus targeted suites; frontend suites only to prove you did not regress them.
4. Completion report per template §H: what changed, literal fresh gate results (including failures/skips), which §E gates were touched and their approval records, limitations. Never claim what was not verified.
5. Rollback per template §I: each story independently revertable; docs-only stories are fully rolled back by revert.

## 8. Maintainer decision queue (blockers only the maintainer can clear)

| # | Decision | Needed for | Default recommendation |
| --- | --- | --- | --- |
| 1 | Reserve the `loopplane` name / configure PyPI trusted publisher | US1/US2 publish path | Do early; name was unclaimed 2026-08-08 |
| 2 | Approve (or reject) a convenience extra `all`/`server` | US1 (FR-002) | Approve `all` = union of extras; else document matrix |
| 3 | Approve `import-linter` as dev dependency, or choose the no-new-dep AST gate | US5 (FR-011) | No-new-dep gate first; revisit later |
| 4 | Timing of `v0.5.0` cut (recommended scope: 064–081, + 078 if Verified) | US2 runbook execution | After 078 Verified |
| 5 | Landing order of US5/US6a/US7 relative to 078 Stage-C | §6.3 | Land after 078's T090 review if imminent; else proceed |
| 6 | Repo public flip + first publish | Mission completion | After US1–US3 land and v0.5.0 is cut |

## 9. Evidence appendix (analysis key numbers, 2026-08-08)

- Python core: ~31 subpackages, ~19.4k LOC; base deps 3; extras 9; strict mypy; 1 console script (`loopplane = loopplane.cli:main`).
- Boundary guards: 17 AST test files; global invariants G1–G8; risks R1–R13; ADRs 0001–0015 all Accepted.
- webapi: ~60 routes under `/v1` (largest cluster: ~24 capability routes); default-deny auth; File/SQLite/Postgres triads for checkpoint, ledger, and event-replay stores; uploads are filesystem-only (known asymmetry, out of scope).
- Hotspots: `webapi/app.py` ~1265 lines; `host/capability_manager.py` ~1546 lines; `controller/controller.py` ~1253 lines (dedicated core tests exist since 2026-07-07; depth to re-verify during the US7 audit refresh).
- Frontends: web 57 test files / ~192 cases; desktop 13 files / ~60 cases; `packages/cowork-presentation` 4 files / 14 cases, 2 components, consumed by desktop only.
- Desktop sidecar imports from the core: exactly `loopplane.host`, `loopplane.events`, `loopplane.model` — no controller/gateway/checkpoint/webapi/loop/tools imports.
- Release state: tags `v0.1.0`–`v0.4.0`; `__version__` 0.4.0; `[Unreleased]` = units 064–077 + 080–081; CI = 3 workflows (ci/web/desktop), none publish.
- 078 progress: 66/101 tasks done; remaining phases: a11y matrix, Web→package extraction, backup/restore durability tail, packaging + Stage-C delivery review.
