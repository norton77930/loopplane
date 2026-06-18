# LoopPlane Agent Board

> **🛰 Roadmap Autopilot control document for `/loop` and `/loop 1m`.**
> Read this file **first** at the start of every `/loop` run. It is the single source of truth that
> lets `/loop` advance the **entire LoopPlane roadmap (units 000–024) autonomously** — choosing the
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
| **003-loopplane-loop-engineering-layer** | `specs/003-loopplane-loop-engineering-layer` | **Verified** | Outer loop-engineering layer on top of runtime + host: Loop Definition, Loop Controller, Manual trigger, Interval trigger contract, Condition trigger contract, Validator interface, Evaluator interface, Retry policy, Repair policy, in-memory reconstructable Loop State, Loop Events, Host Interface integration. | 001, 002 | None — implemented & verified on `main` (full Spec Kit flow; `loopplane.engineering`). |
| **004-loopplane-scheduler-trigger-engine** | `specs/004-loopplane-scheduler-trigger-engine` | **Verified** | Turn trigger contracts into usable local scheduling and condition-watch behavior: local scheduler, interval trigger, condition trigger, manual trigger registry, trigger state, missed-run policy. No distributed queue yet unless explicitly approved. | 003 | None — implemented & verified on `main` (`loopplane.scheduling`). |
| **005-loopplane-validator-evaluator-packs** | `specs/005-loopplane-validator-evaluator-packs` | **Verified** | Reusable validators and evaluators: rule-based validators, schema validators, artifact validators, scoring evaluators, threshold gates, quality labels, validator/evaluator examples. | 003 | None — implemented & verified on `main` (`loopplane.packs`). |
| **006-loopplane-human-review-workflows** | `specs/006-loopplane-human-review-workflows` | **Verified** | Extend approval boundaries into human review workflows: review request, user question event, approval memory, review decision, pause/resume, human gate loop. No UI unless separately specified. | 003 | None — implemented & verified on `main` (`loopplane.review`). |
| **007-loopplane-memory-recall-knowledge** | `specs/007-loopplane-memory-recall-knowledge` | **Verified** | Recall and knowledge indexing as loop-aware context sources: conversation recall, artifact recall, knowledge index contract, memory injection policy, retrieval budget, loop-aware memory usage. | 001, 003 | None — implemented & verified on `main` (`loopplane.recall`). |
| **008-loopplane-tool-gateway-advanced** | `specs/008-loopplane-tool-gateway-advanced` | **Verified** | Expand the tool ecosystem beyond the foundation: MCP tool discovery, remote tool registry, plugin bundle, tool package metadata, tool capability manifest, tool versioning, tool diagnostics. | 001 | None — implemented & verified on `main` (`loopplane.toolkit`). |
| **009-loopplane-sandbox-policy-governance** | `specs/009-loopplane-sandbox-policy-governance` | **Verified** | Stronger execution safety and governance: sandbox execution, path policy, permission policy, budget policy, quota policy, cost governance, safe failure behavior. | 001 | None — implemented & verified on `main` (`loopplane.governance`). |
| **010-loopplane-observability-debug-console** | `specs/010-loopplane-observability-debug-console` | **Verified** | Make runs and loops inspectable: trace viewer data contract, event replay, debug timeline, run diagnostics, loop diagnostics, metadata-only observability. No full frontend unless separately specified. | 001, 003 | None — implemented & verified on `main` (`loopplane.inspect`). |
| **011-loopplane-web-api-host** | `specs/011-loopplane-web-api-host` | **Verified** | Expose LoopPlane through a web/API host: FastAPI or equivalent host, REST endpoints, SSE or WebSocket streaming, auth boundary, session APIs, host-level integration tests. | 002 | None — implemented & verified on `main` (`loopplane.webapi`). |
| **012-loopplane-desktop-or-studio-host** | `specs/012-loopplane-desktop-or-studio-host` | **Verified** | Local desktop or studio host: local app host, sidecar process, local session manager, developer console, optional UI shell. No private legacy UI copy. | 002 | None — implemented & verified on `main` (`loopplane.studio`). |
| **013-loopplane-multi-agent-orchestration** | `specs/013-loopplane-multi-agent-orchestration` | **Verified** | Subagents, coordinator, and delegation: agent registry, subagent execution, coordinator, delegation policy, child run references, aggregated events, aggregated artifacts. | 003 | None — implemented & verified on `main` (`loopplane.orchestration`). |
| **014-loopplane-release-packaging-docs** | `specs/014-loopplane-release-packaging-docs` | **Verified** | Public release quality: packaging, examples, docs, quickstart, API reference, changelog, public-safe cleanup, CI readiness. | all prior | None — implemented & verified on `main` (packaging + docs + CI; **v0.1.0 release shipped**). |
| **015-loopplane-hook-system** | `specs/015-loopplane-hook-system` | **Verified** | Lifecycle hook system: a hook registry plus eleven lifecycle points (pre/post tool use, prompt submit, session start/end, subagent start/stop, file changed, model stop) that let host and plugin code observe — and, at the two gating points, gate or modify — agent behavior without forking the runtime. In-process; honors the single Tool Gateway (V) and Runtime Event Bus (VI) boundaries; hooks are a distinct concept from normalized events (synchronous, may gate/modify vs. fire-and-forget stream). | 001, 003 | None — implemented & verified on `main` (`loopplane.hooks`). |
| **016-loopplane-plugin-system** | `specs/016-loopplane-plugin-system` | **Verified** | Plugin manifest bundles: a public-safe `plugin.json` that packages skills + namespaced MCP servers + hooks into a discoverable, host-loadable unit; enable-list gating with zero default behavior change; loads through the existing skills/MCP/hook seams with no new runtime coupling. Reuses 001 skills, 008 toolkit, and 015 hooks. | 001, 008, 015 | None — implemented & verified on `main` (`loopplane.plugins`). |
| **017-loopplane-cli-host** | `specs/017-loopplane-cli-host` | **Verified** | Interactive CLI host: a thin terminal host over the Host Application Interface (`loopplane.host`) — REPL/chat loop, run/session commands, normalized-event rendering, and an optional credential-gated real model provider behind a seam. Executes **no tool** itself (V) and consumes the normalized event stream (VI). Adds a console entry point; the runtime core is unchanged. | 002 | None — implemented & verified on `main` (`loopplane.cli`; `loopplane` console entry point). |
| **018-loopplane-web-frontend** | `specs/018-loopplane-web-frontend` | **Verified** | Web frontend: a from-scratch single-page UI over the 011 web/API host (REST + SSE) — chat/run view, event timeline, approvals/questions, session list. **No private legacy UI copy** (VII); written fresh; the JS toolchain is isolated under `apps/` with its own CI gate. | 011 | None — implemented & verified on `main` (`apps/web`; React + Vite + Vitest). |
| **019-loopplane-desktop-gui** | `specs/019-loopplane-desktop-gui` | **Verified** | Desktop GUI shell: a local desktop application over the 012 studio sidecar contract — an Electron shell embedding the 018 frontend, driving a local sidecar host with no server. **No private legacy UI copy** (VII); reuses 018; launch + shell only, runtime unchanged. | 012, 018 | None — implemented & verified on `main` (`apps/desktop`; Python sidecar bridge + TS transport + reused 018 UI + Electron shell). |
| **020-model-provider-adapters** | `specs/020-model-provider-adapters` | **Verified** | Real model-provider adapters: Anthropic (`loopplane.adapters.anthropic`) and OpenAI (`loopplane.adapters.openai`) implementing the existing model boundary, each behind its own optional extra (`anthropic`/`openai`), with duck-typed stream mapping, offline stub-based tests, and an opt-in live check. Runtime core unchanged (VIII); tool calls surface as raw `ToolCallRequest` for the gateway (V); only normalized increments reach the loop (VI). First unit of the post-roadmap gap-closure plan (Phase A: real model). | 001, 002 | None — implemented & verified on `main` (`loopplane.adapters.{anthropic,openai}`; five gates green). |
| **021-checkpoint-store-backends** | `specs/021-checkpoint-store-backends` | **Verified** | Checkpoint store backends: the checkpoint store is now a `CheckpointStore` interface (Protocol) with two interchangeable implementations — `FileCheckpointStore` (the unchanged default) and an optional standard-library `SqliteCheckpointStore`, selected via `StorageConfig(checkpoint_backend=...)`. No new dependency; runtime core/contracts unchanged; `principal_id`/multi-user and a networked database deferred. Second unit of the gap-closure plan (Phase B: persistence abstraction). | 001, 002 | None — implemented & verified on `main` (`loopplane.checkpoint.{base,file,sqlite}`; one shared parametrized contract suite over both backends; all gates green). |
| **022-web-principal-auth** | `specs/022-web-principal-auth` | **Verified** | Web principal authentication & per-principal session scoping (gap-closure Phase C, backend): the web/API auth boundary now returns a `Principal` (was a bool) and every session is scoped to its owner — the listing is filtered and a non-owner gets a `404` (no existence leak). The owner rides the unit-021 checkpoint metadata (`principal_id`) so scoping survives restarts; a reference `token_authenticator` ships. **Breaking** change to the 011 webapi auth return type. Concurrency / login UI deferred (login UI = unit 023). Runtime core unchanged; no new dependency. | 011, 021 | None — implemented & verified on `main` (`loopplane.webapi`; a six-scenario two-principal scoping suite; all gates green). |
| **023-web-login-ui** | `specs/023-web-login-ui` | **Verified** | Web frontend login UI (gap-closure Phase C, frontend): a login screen captures an access token and gates the unit-018 SPA over the 022 secured backend — `AppRoot` renders `Login` (a masked token field) when there is no token, else the existing `App` wired with a `Bearer <token>` client. The token persists in `sessionStorage` (cleared on tab close); logout and a `401` clear it and return to login. Frontend only; the existing 018 app/components/tests are reused unchanged (`App` gains only an optional `onUnauthorized`). | 018, 022 | None — implemented & verified on `main` (`apps/web`; 27 Vitest incl. login/logout/401-to-login; tsc-strict + vite build green; Python suite unchanged). |
| **024-desktop-packaging** | `specs/024-desktop-packaging` | **Verified** | Desktop packaging (gap-closure Phase D, the final unit): the unit-019 Electron app can be packaged into a distributable installer that bundles a **PyInstaller-frozen** sidecar, so an end-user needs no system Python. A freeze spec (`sidecar/loopplane-sidecar.spec`), an `electron-builder.yml`, and a pure, unit-tested **spawn resolver** (`electron/sidecar-spawn.ts`) — packaged → the bundled frozen exe, dev → `python bridge.py`, missing → fail clearly. Desktop-only; runtime unchanged; the actual signed per-OS installer build is a reserved manual/CI step. | 019 | None — implemented & verified on `main` (`apps/desktop`; 8 Vitest incl. resolver + config↔spec consistency; tsc-strict green; Python suite unchanged). |
| **025-web-agent-ui** | `specs/025-web-agent-ui` | **Verified** | Web Agent UI (maintainer-authorized post-gap-closure extension): a **frontend-only** visual + UX overhaul of the unit-018 SPA into a professional agent UI — a two-pane app shell (sessions sidebar + chat column with sticky header/composer), assistant **markdown** rendering, **inline collapsible tool cards** (running/success/failure), styled approval/question dialogs, connection/run status + error banner, a **Stop** control, auto-scroll + jump-to-latest, a styled login, and a **light/dark theme** — all mapped onto the **existing** events/endpoints. **No backend change.** Follow-up units take the rest: **026** (reasoning/thinking display, multi-option questions, token usage — all frontend-only; the backend already emits them) and **027+** (skills/MCP/memory panels; model switching and file upload behind a constitution ADR). | 011, 018 | None — implemented & verified on `main` (`apps/web`; ordered-entries reducer + 11 new components + theme/styles; **49 Vitest**, tsc-strict + vite build green; Python suite unchanged). |
| **026-web-agent-signals** | `specs/026-web-agent-signals` | **Verified** | Web Agent Signals (maintainer-authorized extension): a **frontend-only** unit surfacing three agent signals the backend **already emits** but the unit-018/025 UI ignores — a streamed, de-emphasized, collapsible **reasoning/thinking block**; **selectable option choices** in the question dialog (free-text fallback); and a **token-usage** indicator (per-turn + session total). Consumes existing events/fields; **no backend change**, no ADR. Builds on 025. Cost/pricing, non-emitting-provider reasoning, model switching, file upload, and skills/MCP/memory panels are **out of scope** → later units (panels = 027). | 011, 018, 025 | None — implemented & verified on `main` (`apps/web`; reasoning block + question options + usage indicator; **60 Vitest**, tsc-strict + vite build green; Python suite unchanged). |
| **027-web-agent-inspection** | `specs/027-web-agent-inspection` | **Spec complete** | Web Agent Inspection Panels (maintainer-authorized extension): **read-only** inspection of the agent's capabilities/context in the web UI — loaded **skills** (+ load problems), registered **tools**, connected **MCP servers** (+ their tools), and **memory/knowledge** entries. Adds **additive, metadata-only** web/API read endpoints + host query methods composing existing internal layers, rendered as tabbed panels in the 025 shell. **No ADR** (touches neither Tool Gateway execution (V) nor Event Bus (VI); strictly additive — runtime/gateway/bus/existing endpoints unchanged). Read-only (no execute/edit). Model switching + file upload (need an ADR) → unit 028. | 011, 018, 025 | Run **plan** (`/speckit-plan`) after 025/026. Spec + checklist drafted. |
| **028-web-agent-model-files** | `specs/028-web-agent-model-files` | **Spec complete** | Web Agent Model Selection & File Attachments (maintainer-authorized extension): per-session **model selection** (web/API-layer registry of pre-configured single-model hosts; routes the session's next turn, resuming from the shared checkpoint — runtime keeps **one model per run**) + **file attachments** (upload endpoint, per-principal; agent reads on demand via a **read-upload tool in the Tool Gateway** — files = transient input by id, **not** embedded/artifact/memory). **Additive — NO ADR** (a reference review confirmed neither blurs a runtime boundary; like 027). Tool Gateway (V) / Event Bus (VI) / content model preserved. Multimodal embedded content + cost/pricing out of scope (the former would need an ADR → later unit). | 011, 018, 020, 021, 022, 025 | Run **plan** (`/speckit-plan`) after 027. Spec + checklist drafted. |
| **029-web-agent-extras** | `specs/029-web-agent-extras` | **Spec complete** | Web Agent Parity Extras (maintainer-authorized extension): **frontend-only** parity polish, **no backend, no ADR** — **i18n** (en + zh-TW + switcher), **code syntax highlighting** (in 025 markdown), a **command palette** (frontend-doable slash + `@file`/`@skill` from the 027 inspection data; backend-semantic commands out of scope), and a **client-side cost estimate** (026 token usage × a bundled price table; server-side pricing deferred). Builds on 025–027. | 011, 018, 025, 026, 027 | Run **plan** (`/speckit-plan`) after 025–028. Spec + checklist drafted. |

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
- **003** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (5) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/engineering/` (10 modules) + `examples/loop_quickstart.py` +
  `docs/loop-engineering.md`. Tasks **45/45 complete**; 49 engineering tests pass
  (foundational unit + US1–US5 integration + import-boundary + public-safety); the
  loop composes the runtime only through `loopplane.host`. ruff format/lint +
  mypy(strict) clean; full suite **242 passed** → **Verified**.
- **004** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (3) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/scheduling/` (7 modules) + `examples/scheduler_quickstart.py` +
  `docs/scheduling.md`. Tasks **34/34 complete**; 38 scheduler tests pass
  (foundational unit + US1–US5 integration + import-boundary + public-safety);
  the scheduler fires Loop Runs only through the Phase-3 `run_loop`, driven by an
  injectable virtual clock with no real sleeping. ruff + mypy(strict) clean; full
  suite **280 passed** → **Verified**.
- **005** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/packs/` (5 modules) + `examples/packs_quickstart.py` +
  `docs/packs.md`. Tasks **31/31 complete**; 34 pack tests pass (reader unit +
  US1–US5 integration + import-boundary + public-safety); packs are pure
  callables that read only the public `RunOutcome`/`LoopState` surface and never
  start runs. ruff + mypy(strict) clean; full suite **314 passed** → **Verified**.
- **006** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/review/` (7 modules) + `examples/review_quickstart.py` +
  `docs/human-review.md`. Tasks **31/31 complete**; 42 review tests pass (RA unit
  + gate-hardening unit + US1–US5 integration + import-boundary + public-safety);
  the layer composes only the Phase-3 review hook and never the Phase-1 approval
  machinery. The 006 spec was grounded in a multi-agent read-only survey of the
  existing approval/question/review surface; a post-implement multi-agent
  adversarial verification then hardened the gate fail-safe edges (a raising
  event sink or review-key never crashes the review — FR-052/NFR-005) and carried
  the decision `metadata` into the `review_decided` event (FR-002/SC-007), and
  corrected the `resume_review` contract (no `on_approval`: `OnApproval` is not on
  the Phase-3 public surface this layer may name). ruff + mypy(strict) clean; full
  suite **356 passed** → **Verified**.
- **007** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/recall/` (8 modules) + `examples/recall_quickstart.py` +
  `docs/memory-recall.md`. Tasks **29/29 complete**; 44 recall tests pass (core unit
  + US1–US5 integration + import-boundary + non-mutation + determinism + public-safety);
  the layer composes only the public Phase-1 (`memory`, `artifacts`) and Phase-3
  (`engineering`) surfaces, injects through the Phase-3 `InputSource`, drives no run, and
  mutates nothing. A `/speckit.analyze` pass (0 critical/high) realigned the plan phase
  table with tasks. ruff + mypy(strict) clean; full suite **400 passed** → **Verified**.
- **008** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/toolkit/` (6 modules) + `examples/toolkit_quickstart.py` +
  `docs/tool-gateway-advanced.md`. Tasks **28/28 complete**; 30 toolkit tests pass (core unit
  + US1–US5 integration + import/no-invoke boundary + public-safety); the layer composes only the
  public Phase-1 `ToolAdapter` SPI (`describe()` only) and `ToolDescriptor` identity, **never
  invokes a tool**, and registers only through the gateway's `register_adapter` (Constitution V).
  A `/speckit.analyze` pass (0 critical/high) aligned a plan test-note with tasks. ruff +
  mypy(strict) clean; full suite **430 passed** → **Verified**.
- **009** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/governance/` (8 modules) + `examples/governance_quickstart.py` +
  `docs/sandbox-policy-governance.md`. Tasks **29/29 complete**; 36 governance tests pass (core unit
  + US1–US5 integration + import/no-invoke boundary + public-safety); every policy returns a Phase-1
  allow/deny verdict and **never executes or OS-sandboxes a tool** (Constitution V), composing only the
  public Phase-1 policy contracts (reusing `resolve_rules`) and distinct from the Human Approval boundary.
  A `/speckit.analyze` pass (0 critical/high) aligned a plan test-note with tasks. ruff + mypy(strict)
  clean; full suite **466 passed** → **Verified**.
- **010** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/inspect/` (6 modules) + `examples/inspect_quickstart.py` +
  `docs/observability-debug.md`. Tasks **27/27 complete**; ~31 inspect tests pass (core unit
  + US1–US5 integration + import/no-run boundary + metadata-only + public-safety); the layer is a
  read-only DATA layer that composes only the public Phase-3 Loop Event/State (reusing
  `reconstruct_state`) and Phase-1 Runtime Event surfaces, **drives no run and re-emits no live bus**
  (Constitution VI), and surfaces only metadata (ids / types / sequences / counts / public-safe
  reasons). A `/speckit.analyze` pass (0 critical/high) added `base.py` to the plan source tree.
  ruff + mypy(strict) clean; full suite **497 passed** → **Verified**.
- **011** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/webapi/` (6 modules) + `examples/webapi_quickstart.py` +
  `docs/web-api-host.md`. Tasks **29/29 complete**; 33 webapi tests pass (core unit + US1–US5
  integration + import/no-tool/no-reemit boundary + metadata-only + default-deny + public-safety);
  the layer is an additive transport over the public Host Application Interface (`loopplane.host`) —
  it executes **no tool** (Constitution V) and consumes the normalized event stream as a host
  consumer, **never re-emitting the live bus** (Constitution VI). Response bodies are metadata-only;
  the SSE stream forwards `serialize_event` verbatim; auth is a pluggable default-deny boundary. A
  new optional `web` extra introduces FastAPI (a transport, not the runtime core — Principle VIII not
  engaged); `pytest-timeout` was added as a hang safety net after diagnosing that the buffering
  in-process `TestClient` cannot read an infinite SSE stream (so the interactive-approval round-trip
  is covered at the Session level by the Phase-2 host suite + US2 framing). ruff + mypy(strict)
  clean; full suite **530 passed** → **Verified**.
- **012** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/studio/` (5 modules) + `examples/studio_quickstart.py` +
  `docs/desktop-studio-host.md`. Tasks **28/28 complete**; 18 studio tests pass (core unit + US1–US5
  integration + import/no-tool/no-process boundary + metadata-only + public-safety); the layer is an
  additive **local** presentation over the public Host Application Interface (`loopplane.host`) —
  a developer-console core, a held-open session manager, and an in-process sidecar contract. It adds
  **no third-party dependency** (boundary is `loopplane.host` + `anyio` only), executes **no tool**
  (Constitution V), and re-emits **no live bus** (Constitution VI; its only event path is a discard
  sink). Views are metadata-only; the interactive approval round-trip runs **in-process** (no
  transport, so unit 011's buffering-client limitation does not apply); GUI / process spawn / network
  are reserved. ruff + mypy(strict) clean; full suite **548 passed** → **Verified**.
- **013** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/orchestration/` (4 modules) + `examples/orchestration_quickstart.py` +
  `docs/multi-agent-orchestration.md`. Tasks **28/28 complete**; 22 orchestration tests pass
  (core unit + US1–US5 integration + import/no-tool/no-reemit boundary + metadata-only +
  determinism + public-safety); the layer is an additive coordination sibling over the public
  Phase-3 loop surface (`loopplane.engineering`) — it runs each subagent through `run_loop`,
  **executes no tool** (Constitution V) and **re-emits no live bus** (Constitution VI; it reads
  each captured `LoopOutcome`, passing no live sink). The registry, the coordinator, and the
  aggregated event / artifact views are deterministic by registration order then event sequence,
  and metadata-only (subagent / type / sequence / reference); a failing subagent, a raising
  delegation policy, and an empty selection are each contained (a fixed public-safe `"failed"` /
  `"not found"` marker, never raw exception detail). ruff + mypy(strict) clean; full suite
  **571 passed** → **Verified**.
- **014** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`. A packaging +
  documentation + verification overlay over the existing tree — **no new package**:
  `pyproject.toml` (complete metadata + a single-source `dynamic` version from
  `src/loopplane/__init__.py` + wheel `packages` shipping `py.typed`), a PEP 561
  `src/loopplane/py.typed` marker, `docs/api-reference.md`, `README.md` /
  `docs/getting-started.md` / `docs/README.md` / `examples/README.md`, `CHANGELOG.md`,
  `docs/release-readiness.md`, and a CI `uv build` step. Tasks **27/27 complete**;
  17 release contract tests pass (single-source version + shipped `py.typed`; a
  per-package `__all__` bijection that keeps the API reference drift-proof across all
  **25 public packages**; docs/examples index ↔ file-tree consistency; CI gate +
  no-secret; changelog structure + coverage; the PHASE14 public-safety scan).
  **Strictly additive / non-breaking** — no layer public API (`__all__`) or runtime
  behavior changed, and **no new runtime dependency** (the only code additions are the
  version single-sourcing and the `py.typed` marker). `uv build` produces an sdist +
  wheel offline (version **0.1.0** from the single source; `py.typed` + every
  subpackage shipped). The project is licensed under **MIT** (a `LICENSE` file +
  `license = "MIT"` in `pyproject.toml`; the wheel carries `License-Expression: MIT`).
  ruff + mypy(strict) clean; full suite **589 passed** → **Verified**.
- **015** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/hooks/` (5 modules: points / decisions / registry / dispatcher /
  `__init__`) + additive `hooks` seams on the gateway, loop, controller, and
  orchestration coordinator + `examples/hooks_quickstart.py` + `docs/hooks.md`.
  Tasks **32/32 complete**; **39 hook tests pass** (4 unit suites: points /
  decisions / registry / dispatcher; US1–US5 integration; import-boundary +
  no-runtime-internal + public-safety + zero-behavior-change). Every seam is an
  optional `hooks` parameter defaulting to absent, so the un-hooked path is
  byte-identical (FR-011/SC-003, verified by the empty-registry-equals-no-hooks
  test and zero regressions). Tool hooks fire **inside** the Gateway and a hook
  deny reuses the existing `POLICY_DENIAL` path (V); hooks stay distinct from the
  Event Bus and a hook failure surfaces only via the existing `diagnostic` event
  (VI); payloads and reasons are metadata-only and public-safe (VII). The unit-013
  orchestration import allow-list was extended to admit the foundational,
  dependency-free `loopplane.hooks` layer (documented boundary change, Principle
  IV; the `PROHIBITED_TOKENS` guard is unchanged). ruff + mypy(strict) clean; full
  suite **628 passed** → **Verified**.
- **016** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/plugins/` (3 modules: manifest / discovery / loader + `__init__`)
  + `examples/plugins_quickstart.py` + `docs/plugins.md`. Tasks **20/20 complete**;
  **26 plugin tests pass** (manifest + discovery unit; US1–US5 integration;
  import-boundary + no-runtime-internal + public-safety). The layer **consumes**
  the existing public seams and changes no contract: it collects skill dirs for
  `skills.load_skills` (001), a namespaced `<plugin>__<server>` MCP layer for
  `adapters.mcp.merge_layers` (001/008), and registers hooks on a supplied
  `hooks.HookRegistry` (015) via a bounded, **enabled-only** `module:attr` import
  (research R5). A malformed / unparseable / credential-bearing manifest skips the
  whole plugin with a public-safe diagnostic and discovery never raises (FR-008/009);
  manifests and the listing are metadata-only and public-safe (VII). Its only
  `loopplane` import is `loopplane.hooks` (boundary test); inert with an empty
  enable-list (zero regressions). ruff + mypy(strict) clean; full suite
  **654 passed** → **Verified**.
- **017** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; source
  `src/loopplane/cli/` (4 modules: render / providers / session / app + `__init__`)
  + a `[project.scripts] loopplane = "loopplane.cli:main"` console entry point +
  `examples/cli_quickstart.py` + `docs/cli.md`. Tasks **21/21 complete**; **18 CLI
  tests pass** (render + providers unit; US1–US5 integration; import-boundary +
  no-runtime-internal). A thin host over `loopplane.host` — `chat` / `run` /
  `sessions` / `resume`, an `EventRenderer` over the normalized event stream
  (metadata-only — tool name + outcome, never raw I/O), and credential-free by
  default (a built-in stateless demo `ModelBoundary`); a real model is the opt-in
  `LOOPPLANE_MODEL="module:function"` builder seam (concrete network provider out of
  scope, manually validated like 001). Executes **no tool** (V) and consumes the
  normalized stream (VI); imports only `loopplane.host`/`model`/`events`
  (boundary test). The only packaging change is the entry point; `py.typed` + every
  subpackage still ship. The `loopplane run` command was smoke-run. ruff +
  mypy(strict) clean; full suite **672 passed** → **Verified**.
- **018** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; a **from-scratch**
  React + TypeScript + Vite single-page app under `apps/web/` (no legacy UI copied —
  VII) over the unit-011 `/v1` web API + SSE stream, with its own isolated toolchain
  and CI gate (`.github/workflows/web.yml`) + `docs/web-frontend.md`. Tasks
  **22/22 complete**; **20 Vitest tests pass** (the pure core — SSE parser / chat
  reducer / fetch-injectable API client — in node env; jsdom component smoke tests for
  Conversation / Timeline / Prompts / SessionList / App). `tsc --noEmit` (strict) clean
  and `vite build` produces static assets (149 kB / 48 kB gzip). The UI **consumes
  only** the public web API (runs no tool — V; a consumer of the normalized event
  stream — VI), renders metadata-only content, and embeds no secret (auth at runtime —
  VII). The Python package is **untouched**: `apps/` is excluded from the wheel, and the
  full Python suite is unchanged at **672 passed**. → **Verified**.
- **019** — Full Spec Kit flow on `main`: `spec.md` / `plan.md` / `research.md` /
  `data-model.md` / `contracts/` (2) / `quickstart.md` / `tasks.md`; an Electron
  desktop app under `apps/desktop/` (no server) that spawns a **Python sidecar**
  (`sidecar/bridge.py` — a stdio NDJSON bridge over `loopplane.host`, reusing
  `serialize_event`) and **reuses the unit-018 UI** as its renderer over a sidecar
  transport (`window.api` IPC) via a `@web` alias (no UI copied — VII), plus
  `.github/workflows/desktop.yml` (the isolated desktop gate) + `docs/desktop-gui.md`.
  Tasks **12/12 complete**; **3 Python sidecar tests** (`tests/integration/
  test_desktop_sidecar.py`, loaded by file path) + **3 Vitest tests** (the
  `SidecarTransport` over a stubbed bridge; the desktop App rendering a streamed run via
  the reused 018 components) pass; `tsc --noEmit` (strict) is clean over the renderer +
  the Electron main/preload (the GUI launch is a manual smoke; the Electron binary is
  skipped in CI). The renderer runs **no tool** (V) and consumes the normalized stream
  (VI); no secret is embedded (VII). The Python package and units 011/012/018 are
  **unchanged** (the sidecar is loaded by path, not in the wheel); the full Python suite
  is **675 passed**. Packaging a signed installer is reserved. → **Verified**.
- **020 / 021 — gap-closure Phase A & B** (post-roadmap). **020** shipped the real
  Anthropic/OpenAI model adapters (Phase A). **021** extracted the checkpoint store into
  an interface and added an optional SQLite backend (Phase B): `src/loopplane/checkpoint/`
  is split into `base.py` (the `CheckpointStore` Protocol + `SessionSummary`), `file.py`
  (`FileCheckpointStore`, the unchanged default), and `sqlite.py` (`SqliteCheckpointStore`,
  stdlib `sqlite3`); the host selects via `StorageConfig(checkpoint_backend=...)` (default
  `file`). One shared parametrized contract suite covers both backends (append/load order,
  corrupt-skip parity, missing→empty, recency); the default path is byte-identical and adds
  **no new dependency**. Runtime core/contracts unchanged; `principal_id`/multi-user and a
  networked database (Postgres) are deferred to Phase C. ruff + mypy(strict) clean; full
  suite green → **Verified**.
- **022 — gap-closure Phase C (backend)**. The web/API auth boundary
  (`loopplane.webapi`) became identity-bearing: `Authenticator` returns a `Principal`
  (was a bool — a **breaking** change to the 011 surface), `make_auth_dependency` resolves
  it per route, and a reference `token_authenticator` maps `Bearer <token>` →
  `Principal`. Every session is scoped to its owner — `GET /sessions` is filtered and the
  per-session routes `404` a non-owner (no existence leak). The owner threads additively
  (default `None`) through `SessionMetaPayload.principal_id` → `SessionSummary` → both
  checkpoint backends and `host.run`/`host.session`, so scoping survives a restart
  (the unit-021 seam). A six-scenario two-principal suite covers list/access scoping, the
  live-session guard, default-deny, no-leak, and durable restart; the existing webapi
  suites pass unchanged (single principal). Concurrency (host-per-principal) and the login
  UI (unit 023) are deferred. Runtime loop/gateway/event-bus unchanged; no new dependency.
  ruff + mypy(strict) clean; full suite green → **Verified**.
- **023 — gap-closure Phase C (frontend), COMPLETE.** The unit-018 SPA gained a login
  gate (`apps/web`): `AppRoot` (`src/AppRoot.tsx`) holds the access token in
  `sessionStorage` and renders `Login` (`src/components/Login.tsx`, a masked field) when
  there is no token, else the existing `App` wired with a `Bearer <token>` `ApiClient`. A
  logout control and an API `401` (via `onUnauthorized`, the only change to `App`) clear
  the token and return to login; the token is masked and never logged / URL-encoded /
  committed (VII). Tests are Vitest + jsdom (no Playwright): a login / logout /
  401-to-login suite; the existing 018 `App`/component tests pass unchanged (**27 Vitest**
  total). tsc-strict + vite build green; the Python suite is unchanged (frontend-only).
  With 023, **gap-closure Phase C is complete**; only **Phase D (desktop packaging)**
  remains. → **Verified**.
- **024 — gap-closure Phase D (desktop packaging), COMPLETE.** The unit-019 Electron app
  gained a packaging pipeline (`apps/desktop`): a **PyInstaller** spec
  (`sidecar/loopplane-sidecar.spec`) freezes `bridge.py` + `loopplane` into a standalone
  `loopplane-sidecar` executable; `electron-builder.yml` bundles the app + renderer +
  frozen sidecar (`extraResources` → `resources/sidecar/`) into an installer; and a pure,
  no-`electron` **resolver** (`electron/sidecar-spawn.ts`) chooses what `main.ts` spawns —
  the bundled frozen exe when packaged, `python bridge.py` in development, and a clear
  error (not a silent hang) when the frozen exe is missing. A Vitest suite covers the
  resolver (packaged / dev / missing / per-platform) and asserts the spec↔config name
  consistency; the existing 019 tests pass unchanged (**8 Vitest**). The default gate
  proves the resolver + consistency offline; the actual per-OS freeze, installer, and
  signing are a **reserved manual / CI step** (the 019 precedent). Built artifacts are
  gitignored. tsc-strict green; the Python suite is unchanged (desktop-only). **With 024,
  the four-phase gap-closure plan (A–D) is COMPLETE.** → **Verified**.
- **025 — Web Agent UI (maintainer-authorized extension, 2026-06-19), COMPLETE.** A
  frontend-only visual + UX overhaul of the unit-018 SPA (`apps/web`) into a modern agent UI,
  mapped onto the existing events/endpoints — **no backend change**. The reducer
  (`state/chat.ts`) now folds the normalized events into one **ordered `entries` list** (user /
  assistant / tool / terminated, in stream order) so tool cards interleave with messages
  (consumer-side shaping, Constitution VI). On top: a two-pane **AppShell** (sessions sidebar +
  a sticky-header / sticky-composer chat column), assistant **markdown** (`react-markdown` +
  `remark-gfm`, raw HTML disabled — no injection), inline **collapsible tool cards**
  (running → success/failure), styled **approval** (allow / deny / always-allow-session) and
  **question** dialogs, a status indicator + a **Stop** control (existing cancel endpoint), a
  non-blocking **error banner**, **auto-scroll + jump-to-latest**, a **light/dark theme**
  (`localStorage` + `prefers-color-scheme`, applied via `data-theme`), and a restyled login.
  The **api layer** (`api/*`) and the **023 auth gate** (`AppRoot`) are reused **unchanged**;
  the four old display components were replaced. **49 Vitest** pass (16 files: the rewritten
  ordered-entries reducer; Markdown / ToolCard / MessageList / dialogs / Sidebar / ChatHeader /
  Composer / theme; the updated `App` integration; api + `AppRoot` unchanged); tsc-strict +
  `vite build` green (CSS 7.4 kB, JS ~97 kB gz). New deps `react-markdown` + `remark-gfm` (the
  runtime tree is clean on `npm audit --omit=dev`); the Python suite is **unchanged**
  (frontend-only — zero Python diff). Rollback = revert the `apps/web` presentation diff.
  → **Verified**.
- **026 — Web Agent Signals (maintainer-authorized extension, 2026-06-19), COMPLETE.** A
  frontend-only unit that renders three signals the backend **already emits** (grounded in
  `src/loopplane/events/envelope.py`) but the unit-018/025 UI ignored — **no backend change**:
  a `reasoning` conversation entry (merged from `assistant-reasoning-increment`, interleaved
  before the answer) rendered by `ReasoningBlock` (de-emphasized, **collapsible**, streamed);
  **question options** (the real `question-asked` `questions[].{ text, options }` — correcting
  the unit-018 `prompt` mis-mapping) rendered by `QuestionDialog` as a select-one-or-many group
  with a free-text fallback; and a **token-usage** accumulator (`{ last, total }` over
  `turn-completed`) shown by `UsageIndicator` in the header (per-turn + session total, hidden
  when all-zero). Each signal **degrades gracefully** when absent (FR-008). The reducer stays a
  pure consumer (VI); no new dependency. **60 Vitest** pass (18 files: reasoning/usage/question
  reducer + `ReasoningBlock` / `UsageIndicator` / `QuestionDialog` + the extended `App`
  integration); tsc-strict + `vite build` green; the Python suite is **unchanged** (zero Python
  diff). Rollback = revert the `apps/web` diff → unit 025. → **Verified**.
- **027 — Web Agent Inspection Panels (maintainer-authorized extension, 2026-06-19), SPEC
  stage.** Read-only inspection of the agent's capabilities/context — skills (+ load problems),
  tools, MCP servers, memory — via **additive, metadata-only** web/API read endpoints + host
  query methods over existing internal layers, rendered as tabbed panels in the 025 shell.
  Full-stack but strictly additive; **no ADR** (no Tool Gateway (V) / Event Bus (VI) change).
  `specify` complete: `specs/027-web-agent-inspection/spec.md` (3 user stories P1–P3;
  FR-001..FR-011; SC-001..SC-006) + `checklists/requirements.md` (all pass; no
  `[NEEDS CLARIFICATION]`). Next step: `plan` (after 025/026).
- **028 — Web Agent Model Selection & File Attachments (maintainer-authorized extension,
  2026-06-19), SPEC stage.** Per-session model selection (web/API-layer registry of pre-configured
  single-model hosts + per-session routing, resuming from the shared checkpoint — runtime keeps
  one model per run) + file attachments (upload endpoint, per-principal; agent reads on demand via
  a **read-upload tool in the Tool Gateway**, Principle V — files = transient input by id, not
  embedded/artifact/memory). **Re-scoped to ADDITIVE — NO ADR** after a reference review (neither
  blurs a runtime boundary; like 027). Multimodal embedded content (a content block) is the one
  thing that would need an ADR → deferred. `specify` complete:
  `specs/028-web-agent-model-files/spec.md` (2 user stories P1–P2; FR-001..FR-010; SC-001..SC-006)
  + checklist. Next step: `plan`.
- **029 — Web Agent Parity Extras (maintainer-authorized extension, 2026-06-19), SPEC stage.**
  **Frontend-only**, no backend, no ADR: i18n (en + zh-TW + switcher), code syntax highlighting,
  a command palette (frontend slash + `@file`/`@skill` from 027 data), and a client-side cost
  estimate (026 usage × a bundled price table). Builds on 025–027. `specify` complete:
  `specs/029-web-agent-extras/spec.md` (4 user stories P1–P4; FR-001..FR-010; SC-001..SC-006) +
  checklist. Next step: `plan`.

> **🚧 NEW UNITS IN PROGRESS — `025-web-agent-ui` → `026-web-agent-signals` → `027-web-agent-inspection` → `028-web-agent-model-files` → `029-web-agent-extras` (maintainer-authorized web-UI extension, 2026-06-19).** The original roadmap (000–019, v0.1.0; MIT) and the four-phase gap-closure (020–024) remain COMPLETE and `Verified`. Beyond them, the maintainer authorized a **web-UI extension** to bring the unit-018 SPA to parity with a modern agent app. Five units, all `specify`-complete on `main`:
> - **025-web-agent-ui** (frontend-only) — **Verified** (shipped): two-pane shell, markdown, inline tool cards, styled dialogs, status + Stop, sessions, light/dark theme.
> - **026-web-agent-signals** (frontend-only) — **Verified** (shipped): reasoning/thinking display, multi-option questions, token usage (signals the backend **already emits**).
> - **027-web-agent-inspection** (additive, metadata-only, **no ADR**) — read-only skills / tools / MCP / memory endpoints + panels.
> - **028-web-agent-model-files** (additive, **no ADR**) — per-session model selection (web/API-layer host registry + shared-checkpoint routing; runtime keeps one model per run) + file attachments (upload endpoint + a **read-upload tool in the Tool Gateway**, Principle V; files read on demand, not embedded). A reference review confirmed the additive path; multimodal embedded content (which would need an ADR) is deferred.
> - **029-web-agent-extras** (frontend-only, no ADR) — i18n, code syntax highlighting, command palette (frontend slash + `@file`/`@skill`), client-side cost estimate.
>
> **025 + 026 are `Verified`** (shipped on `main`); next is **`plan`** for **027**, and autopilot works the remaining **027 → 028 → 029** in order — **all gate-free** (028 was re-scoped to additive after a reference review). Only multimodal embedded file content (needs an ADR), backend-semantic slash commands, and authoritative server-side pricing remain beyond these. *(This supersedes the "no further unit to advance" note in the banner below.)*

> **🏁 CURRENT STATUS — units `000–024` are all `Verified` on `main`; the gap-closure plan
> is COMPLETE.** Beyond the original runtime + release roadmap (**000–019**, shipped as
> **v0.1.0**, MIT), the four-phase **gap-closure** plan is done: **A — model providers
> (020)**, **B — checkpoint persistence + optional SQLite (021)**, **C — per-principal web
> auth (022) + login UI (023)**, **D — desktop packaging (024)**. The Python suite is
> **721 passed, 2 skipped** (ruff + mypy-strict clean; `uv build` green); the isolated JS
> gates cover the web app (**27 Vitest**, tsc-strict + vite build) and the desktop app
> (**8 Vitest**, tsc-strict). LoopPlane now spans four host surfaces — **CLI / web /
> desktop / embedded** — with real model providers, a pluggable checkpoint persistence
> layer, multi-principal authentication, and a desktop packaging pipeline. The autopilot
> has **no further unit to advance**; only reserved maintainer steps remain (publish to a
> package index; build/sign the per-OS desktop installers; cross-platform CI). It stops
> cleanly. *(The two banners below are the historical milestone trail — accurate as of
> v0.1.0 and the 015–019 extension, superseded by this current status.)*

> **🏁 The 015–019 post-release extension is COMPLETE.** All roadmap units **000–019 are
> `Verified`** on `main` (v0.1.0 shipped; MIT). The five post-release features — **015
> hook-system, 016 plugin-system, 017 cli-host, 018 web-frontend, 019 desktop-gui** —
> are implemented, tested, and pushed: the Python suite is **675 passed** (ruff +
> mypy-strict clean), and the isolated JS gates cover the web app (**20 Vitest**) and the
> desktop app (**3 Vitest**, tsc-strict). The autopilot has no further unit to advance;
> it stops cleanly.

> **🏁 v0.1.0 release shipped; roadmap extended.** Units **000–014 are all `Verified`** on `main`,
> the project is licensed under **MIT**, and every release-readiness gate (see
> [`docs/release-readiness.md`](./release-readiness.md)) is met. On **2026-06-15** the maintainer
> authorized extending the roadmap with five post-release feature units — **015 hook-system →
> 016 plugin-system → 017 cli-host → 018 web-frontend → 019 desktop-gui** — to be built with the
> same Spec Kit flow and autopilot rules. The autopilot advances the lowest-numbered unit that is
> not yet `Verified` and whose dependencies are all `Verified`. **018-loopplane-web-frontend is now
> `Verified`** (20 Vitest tests; Python suite unchanged at 672); the next and **final** unit is
> **019-loopplane-desktop-gui** (depends on 012 + 018; an Electron shell reusing the 018 frontend —
> Node is available). Completing 019 closes the post-release 015–019 roadmap extension.

---

## 4. Active Feature

| Field | Value |
| ----- | ----- |
| Active unit | **027 → 028 → 029** (web-UI extension) — **025 + 026 are `Verified`** on `main`. 029 frontend-only; 027 + 028 additive (**no ADR**). Units **000–026** are `Verified` on `main`. |
| Active feature directory | `specs/027-web-agent-inspection` (autopilot works the lowest incomplete unit; advance `.specify/feature.json` → 027). Remaining: `…/028-web-agent-model-files`, `…/029-web-agent-extras`. |
| Current branch | `main` — **main-only autopilot**; all units progress on `main` (see §7 Branch Strategy) |
| Current Spec Kit step | **026 COMPLETE** (plan → tasks → analyze → implement → Verified). Next: **plan** for **027**, then 028 → 029 (`/speckit-plan`). **All gate-free** (no ADR). |
| Depends on | 027 → 011 + 018 + 025; 028 → +020 +021 +022 +001 (model adapters, shared checkpoint, principal scoping, gateway tool); 029 → +026 +027. All run in order under autopilot. |
| Next command | **`/speckit-plan`** for `027`, then 028 → 029 (each: plan → tasks → analyze → implement). Under autopilot the steps chain across the remaining units — **all gate-free**. |
| Stop condition status | **025 + 026 Verified** (shipped); running **027–029** under autopilot (no ADR gate, no hard stop encountered). |

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

**Branch strategy — main-only.** Autopilot runs directly on `main`. All roadmap units (000–024)
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
