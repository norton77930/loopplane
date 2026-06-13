# LoopPlane Agent Board

> **🛰 Roadmap Autopilot control document for `/loop` and `/loop 1m`.**
> Read this file **first** at the start of every `/loop` run. It is the single source of truth that
> lets `/loop` advance the **entire LoopPlane roadmap (units 000–014) autonomously** — choosing the
> active unit, the current Spec Kit step, and the next command from repository state, **without the
> user manually prompting each step**. It governs *how the loop chooses and sequences work*; it
> contains no product code.

---

## 1. Purpose

This file is the **Roadmap Autopilot control document** for Claude Code / Fable 5 when running
`/loop` or `/loop 1m` against the LoopPlane repository.

Its goal is to let `/loop` **continue the entire LoopPlane roadmap automatically** — driving each
Spec Kit step and advancing from one unit to the next — **without the user manually prompting every
step**. The board is not merely a progress record; it is the operating contract the autopilot reads
to decide what to do next. The per-run operating instruction lives in [`.claude/loop.md`](../.claude/loop.md);
a human-readable descriptor of the same roadmap lives in
[`.specify/workflows/loopplane-roadmap-autopilot/workflow.yml`](../.specify/workflows/loopplane-roadmap-autopilot/workflow.yml).

By reading this board, the autopilot determines — from repository state, without re-deriving from
scratch — every decision dimension it needs:

| Decision | Where it is defined |
| -------- | ------------------- |
| **active unit** | §3 Roadmap (status) + §4 Active Feature |
| **current feature directory** | §4 Active Feature (`.specify/feature.json`) |
| **current Spec Kit step** | §4 Active Feature + §6 Decision Algorithm (step 6) |
| **next command** | §4 Active Feature + §3 Roadmap (Next Action) |
| **allowed changes** | §5 Spec Kit Execution Flow |
| **validation commands** | §10 Validation Commands |
| **commit policy** | §11 Commit Policy |
| **push policy** | §2 Global Rules (#10) + §6 (step 10) + §12 |
| **stop conditions** | §9 Required Stop Conditions |
| **when to continue to next unit** | §7 Autopilot Mode (step 7) + §3 Roadmap (Next Action) |

The board is a control document, not implementation. It governs *how the loop chooses and
sequences work*; it does not contain product code.

> **Command-name note.** This board uses the canonical Spec Kit command labels
> `/speckit.specify`, `/speckit.clarify`, `/speckit.checklist`, `/speckit.plan`,
> `/speckit.tasks`, `/speckit.analyze`, `/speckit.implement`. In this environment the
> locally-installed skills are hyphenated equivalents:
> `speckit-specify`, `speckit-clarify`, `speckit-checklist`, `speckit-plan`,
> `speckit-tasks`, `speckit-analyze`, `speckit-implement`.

---

## 2. Global Rules

1. Do **not** modify raw `openspec/`.
2. Do **not** commit raw `openspec/`.
3. Do **not** copy old implementation code. Treat any legacy/private reference as inspiration
   only; re-derive through public-safe specs.
4. Do **not** include private paths, private repo names, internal project names, internal IPs,
   API keys, tokens, or secrets in any committed file.
5. Follow the Spec Kit flow: **specify → clarify/checklist (if needed) → plan → tasks → analyze
   → implement → final review.**
6. Do **not** implement during specify, clarify, checklist, plan, tasks, or analyze.
7. Do **not** skip tests.
8. Do **not** bypass the public contracts established by earlier phases (001, 002).
9. Prefer **small commits** after stable milestones.
10. **Push** after each safe commit.
11. When running autopilot, **stop only on hard stop conditions** (see Section 9).

---

## 3. Product Unit Roadmap

Allowed status values: `Not started`, `Spec in progress`, `Spec complete`, `Plan complete`,
`Tasks complete`, `Analyze complete`, `Implementation in progress`, `Implemented`, `Verified`,
`Deferred`, `Blocked`.

Status is **inferred from repository state** (specs, plans, tasks, implementation files, tests,
git history) — not invented.

| Unit | Feature Directory | Status | Purpose | Depends On | Next Action |
| ---- | ----------------- | ------ | ------- | ---------- | ----------- |
| **000-project-bootstrap** | _(no `specs/` dir — bootstrap)_ | **Implemented** | Repository setup, Spec Kit initialization, constitution, README, `.gitignore`, and this agent board. | — | Maintain board as units progress. |
| **001-loopplane-runtime-foundation** | `specs/001-loopplane-runtime-foundation` | **Verified** | Agent Harness Runtime foundation: Agent Loop, Runtime Controller, Dispatcher, Tool Gateway, Internal Tool Adapter, MCP Tool Adapter boundary, Skill Execution Profile boundary, Runtime Event Bus, Memory, Checkpoint, Artifact Storage, Observability, Human Approval boundary. | 000 | None — shipped (PR #1). See caveat: T054 manual real-model validation documented, not run in CI. |
| **002-loopplane-host-interface** | `specs/002-loopplane-host-interface` | **Verified** | Expose the runtime foundation to host applications: Host Application Interface, Reference Runner, programmatic runtime configuration object, host-to-runtime wiring, event consumption, end-to-end smoke path, public-safe examples. | 001 | None — shipped (PR #2). |
| **003-loopplane-loop-engineering-layer** | `specs/003-loopplane-loop-engineering-layer` | **Spec complete** | Outer loop-engineering layer on top of runtime + host: Loop Definition, Loop Controller, Manual trigger, Interval trigger contract, Condition trigger contract, Validator interface, Evaluator interface, Retry policy, Repair policy, in-memory reconstructable Loop State, Loop Events, Host Interface integration. | 001, 002 | **`/speckit.plan`** (spec.md + checklist exist; plan.md missing). |
| **004-loopplane-scheduler-trigger-engine** | _(not created)_ | **Not started** | Turn trigger contracts into usable local scheduling and condition-watch behavior: local scheduler, interval trigger, condition trigger, manual trigger registry, trigger state, missed-run policy. No distributed queue yet unless explicitly approved. | 003 | `/speckit.specify`. |
| **005-loopplane-validator-evaluator-packs** | _(not created)_ | **Not started** | Reusable validators and evaluators: rule-based validators, schema validators, artifact validators, scoring evaluators, threshold gates, quality labels, validator/evaluator examples. | 003 | `/speckit.specify`. |
| **006-loopplane-human-review-workflows** | _(not created)_ | **Not started** | Extend approval boundaries into human review workflows: review request, user question event, approval memory, review decision, pause/resume, human gate loop. No UI unless separately specified. | 003 | `/speckit.specify`. |
| **007-loopplane-memory-recall-knowledge** | _(not created)_ | **Not started** | Recall and knowledge indexing as loop-aware context sources: conversation recall, artifact recall, knowledge index contract, memory injection policy, retrieval budget, loop-aware memory usage. | 001, 003 | `/speckit.specify`. |
| **008-loopplane-tool-gateway-advanced** | _(not created)_ | **Not started** | Expand the tool ecosystem beyond the foundation: MCP tool discovery, remote tool registry, plugin bundle, tool package metadata, tool capability manifest, tool versioning, tool diagnostics. | 001 | `/speckit.specify`. |
| **009-loopplane-sandbox-policy-governance** | _(not created)_ | **Not started** | Stronger execution safety and governance: sandbox execution, path policy, permission policy, budget policy, quota policy, cost governance, safe failure behavior. | 001 | `/speckit.specify`. |
| **010-loopplane-observability-debug-console** | _(not created)_ | **Not started** | Make runs and loops inspectable: trace viewer data contract, event replay, debug timeline, run diagnostics, loop diagnostics, metadata-only observability. No full frontend unless separately specified. | 001, 003 | `/speckit.specify`. |
| **011-loopplane-web-api-host** | _(not created)_ | **Not started** | Expose LoopPlane through a web/API host: FastAPI or equivalent host, REST endpoints, SSE or WebSocket streaming, auth boundary, session APIs, host-level integration tests. | 002 | `/speckit.specify`. |
| **012-loopplane-desktop-or-studio-host** | _(not created)_ | **Not started** | Local desktop or studio host: local app host, sidecar process, local session manager, developer console, optional UI shell. No private legacy UI copy. | 002 | `/speckit.specify`. |
| **013-loopplane-multi-agent-orchestration** | _(not created)_ | **Not started** | Subagents, coordinator, and delegation: agent registry, subagent execution, coordinator, delegation policy, child run references, aggregated events, aggregated artifacts. | 003 | `/speckit.specify`. |
| **014-loopplane-release-packaging-docs** | _(not created)_ | **Not started** | Public release quality: packaging, examples, docs, quickstart, API reference, changelog, public-safe cleanup, CI readiness. | all prior | `/speckit.specify`. |

**Status evidence (for audit):**

- **000** — `git log` shows `chore: initialize LoopPlane project`, `chore: initialize Spec Kit`,
  `docs: establish LoopPlane constitution`, `chore: ignore local legacy OpenSpec reference`;
  constitution v1.0.0 ratified; README and `.gitignore` present. This board is its final artifact.
- **001** — Merged via PR #1. Full `spec.md` / `plan.md` / `tasks.md` / `research.md` /
  `data-model.md` / `reference-analysis.md` / `contracts/` (8 files) / `checklists/`.
  Tasks: **53/54 complete**; the single open task **T054** is a *documented manual* real-model
  validation procedure (`docs/real-model-validation.md`), not executed in CI. All automated
  tests pass → **Verified** (with T054 caveat).
- **002** — Merged via PR #2. `spec.md` / `plan.md` / `tasks.md` / `checklists/`. Tasks:
  **28/28 complete**. `research.md` / `data-model.md` / `contracts/` intentionally folded into
  `plan.md`. Host smoke + session + durability + gating integration tests pass → **Verified**.
- **003** — `spec.md` (Draft) + `checklists/requirements.md` present; **no** `plan.md`,
  `tasks.md`, or source. Directory currently **untracked** in git → **Spec complete**.
- **004–014** — No `specs/` directory and no source → **Not started**.

---

## 4. Active Feature

| Field | Value |
| ----- | ----- |
| Active unit | **003-loopplane-loop-engineering-layer** |
| Active feature directory | `specs/003-loopplane-loop-engineering-layer` |
| Current branch | `main` — **main-only autopilot**; all units progress on `main`, no dedicated feature branch required (see §7 Branch Strategy) |
| Current Spec Kit step | **Plan** (`spec.md` + `checklists/requirements.md` exist; `plan.md` missing) |
| Depends on | 001, 002 |
| Next command | **`/speckit.plan`** |
| Stop condition status | None active. Branch strategy is **main-only** — a missing feature branch is *not* a stop condition (see §7 / §9). |

---

## 5. Spec Kit Execution Flow

| Step | Command | Expected Output | Allowed Changes | Validation | Human Gate |
| ---- | ------- | --------------- | --------------- | ---------- | ---------- |
| 1. Specify | `/speckit.specify` | `spec.md` for the active feature (and `checklists/` if generated) | Active feature **spec/checklist only**. No implementation code. | `git diff --check`; confirm only `specs/<feature>/` changed; public-safety scan | After spec drafted — review before plan |
| 2. Clarify / Checklist | `/speckit.clarify` or `/speckit.checklist` | Clarified `spec.md` and/or `checklists/*.md` | Active feature **spec/checklist only**. No implementation code. | Confirm only `specs/<feature>/` changed; public-safety scan | After clarifications encoded |
| 3. Plan | `/speckit.plan` | `plan.md` (+ `research.md`, `data-model.md`, `contracts/` if produced) | Active feature **plan/research/data-model/contracts only**. No implementation code. | Constitution Check gate; only `specs/<feature>/` changed; public-safety scan | After plan complete — review before tasks |
| 4. Tasks | `/speckit.tasks` | `tasks.md` (dependency-ordered) | Active feature **tasks only**. No implementation code. | Only `specs/<feature>/tasks.md` changed; public-safety scan | After tasks generated |
| 5. Analyze | `/speckit.analyze` | Cross-artifact consistency report; minimal fixes | **Minimal consistency fixes to Spec Kit artifacts only**. No implementation code. | Analyze passes with no blocking inconsistencies; public-safety scan | After analyze passes — gate before implement |
| 6. Implement | `/speckit.implement` | Source, tests, and docs/examples as allowed by `tasks.md` | **Source, tests, docs/examples allowed by `tasks.md`.** Must run tests. | `pytest` green; `git diff --check`; public-safety scan. Stop after a major milestone if a hard stop occurs. | At each major milestone / hard stop |
| 7. Final Review | _(manual)_ | Verified feature, updated board | Validate tests, public-safety, `git diff`, scope. Update board status. | Full validation suite (Section 10) | Before declaring the unit Verified |

---

## 6. `/loop` Decision Algorithm

When `/loop` runs, operate exactly as follows:

1. Read `docs/loopplane-agent-board.md`.
2. Inspect the current branch.
3. Inspect `.specify/feature.json` (its `feature_directory` names the active feature).
4. Inspect the `specs/` feature directories.
5. Determine the **active feature**.
6. Determine the **current incomplete step**:
   - if no `spec.md` exists for the active feature → run **specify**;
   - if `spec.md` exists but the checklist is missing or unclear → run **clarify/checklist**;
   - if `spec.md` exists and no `plan.md` → run **plan**;
   - if `plan.md` exists and no `tasks.md` → run **tasks**;
   - if `tasks.md` exists and analyze has not passed → run **analyze**;
   - if analyze passed and implementation tasks are incomplete → run **implement**;
   - if all tasks complete and tests pass → **final review** and update the board.
7. Execute **only the next incomplete step** unless `/loop auto` or `/loop 1m` is explicitly used.
8. Validate (Section 10).
9. Commit safe, scoped changes (Section 11).
10. Push.
11. Stop at the next human gate unless autopilot mode is enabled.

---

## 7. Autopilot Mode

When the user runs `/loop auto` or `/loop 1m`, the agent **may continue automatically across
roadmap units**.

Autopilot may:

1. Determine the active unit.
2. Complete missing Spec Kit steps for that unit.
3. Run implementation tasks in order.
4. Run tests.
5. Commit and push safe, scoped changes.
6. Update board status.
7. Move to the next roadmap unit when the current unit is **Verified**.
8. Stop only on hard stop conditions (Section 9).

**Branch strategy — main-only.** Autopilot runs directly on `main`. All roadmap units (000–014)
progress on `main`; no dedicated feature branch is created or required, and autopilot must **not**
stop merely because a unit lacks a feature branch. After each safe stage it makes a small scoped
commit and pushes (Sections 10–11). A human may introduce branches manually; autopilot itself does
not create, switch, or merge branches.

Autopilot constraints:

- Branch strategy is **main-only**: do **not** create, switch, or merge branches; a missing feature
  branch is **not** a stop condition.
- Must **not** perform destructive git operations.
- Must **not** modify raw `openspec/`.
- Must **not** rewrite previously completed public contracts (001, 002) without explicit approval.

---

## 8. Dynamic Workflow Policy

`/loop 1m` is the **roadmap autopilot driver**. Dynamic Workflow is an **accelerator, not the
roadmap controller**.

Use Dynamic Workflow **only** for:

- `/speckit.analyze`
- `/speckit.implement`
- repo-wide audits
- cross-artifact consistency checks
- test coverage sweeps
- public-safety scans
- large independent implementation task groups

Do **not** use Dynamic Workflow for:

- branch creation
- git merge
- feature transition
- destructive operations
- specify / plan / tasks (unless explicitly requested)

During implement, Dynamic Workflow may split independent task groups, but **final integration
must run in the main session**. If workflow outputs conflict, the main session must reconcile and
run tests before any commit.

---

## 9. Required Stop Conditions

Stop and ask the user if:

1. Any change touches `openspec/`.
2. Any task wants to bypass previous-phase public contracts.
3. Any task introduces out-of-scope product layers.
4. Tests fail and the fix is not obvious after one focused repair attempt.
5. Implementation requires changing 001 or 002 public contracts.
6. A public-safety scan finds private paths, internal names, IPs, keys, tokens, or secrets.
7. A destructive git operation is needed.
8. The active feature cannot be determined.
9. The next step would combine specify, plan, tasks, and implementation without approval — unless
   autopilot mode is explicitly enabled.
10. The agent would need to rewrite the roadmap itself.
11. Push fails due to authentication or remote conflict.
12. Merge conflicts occur.

> **Not a stop condition:** the absence of a dedicated feature branch. Autopilot is **main-only**
> (see §7) — continue directly on `main`. Branch creation/merge is simply *not performed*; it is
> never a reason to pause.

---

## 10. Validation Commands

Run these (PowerShell) before any commit:

```powershell
git status
git diff --stat
git diff --check
git diff --name-only | Select-String "^openspec/"
git diff --name-only | Select-String "^[A-Za-z]:\\|sk-|ghp_|api_key|secret|password|token"
pytest
```

**Public-safety scan — local literal patterns.** This board is a committed, public-safe document
(Constitution Principle VII), so it does **not** embed the literal private path or internal
company/host names. The committed scan above catches generic leak signatures (drive-letter
absolute paths, common secret prefixes). The **literal** internal patterns are kept in a
**local, gitignored** `sensitive-scan.txt` (already excluded by `.gitignore`) and run as a
supplementary local-only check:

```powershell
# sensitive-scan.txt is local-only and MUST NOT be committed.
if (Test-Path sensitive-scan.txt) {
    git diff | Select-String -Pattern (Get-Content sensitive-scan.txt)
}
```

Any non-empty match from either scan is a hard stop condition (Section 9, item 6).

**Source-change rules:**

- During **specify, clarify, checklist, plan, tasks, and analyze**, Python source changes are
  **not** allowed.
- During **implement**, Python source changes are allowed **only if required by `tasks.md`**.

---

## 11. Commit Policy

One commit per stable step. Push after each safe commit. Suggested messages:

- `docs: define LoopPlane <feature> spec`
- `docs: validate LoopPlane <feature> requirements`
- `docs: plan LoopPlane <feature>`
- `docs: define LoopPlane <feature> tasks`
- `docs: align LoopPlane <feature> artifacts`
- `feat: implement LoopPlane <feature>`
- `test: cover LoopPlane <feature> flows`
- `docs: update LoopPlane agent board`

---

## 12. `/loop` Operating Instruction

When `/loop` is used, read `docs/loopplane-agent-board.md` first.

Determine the current incomplete step from repository state.

Execute only that step unless autopilot mode is explicitly enabled.

Run validation before committing.

Commit only safe, scoped changes.

Push after safe commits.

Stop at the next human gate unless autopilot mode is enabled.

Report:

1. completed step
2. files changed
3. tests run
4. validation result
5. commits created
6. next recommended step

---

## 13. Maintenance Rules

Update this board:

- after each feature is implemented
- after a phase status changes
- before starting a new feature branch
- when roadmap scope changes
- when a new stop condition is discovered
