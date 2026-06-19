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
| **027-web-agent-inspection** | `specs/027-web-agent-inspection` | **Verified** | Web Agent Inspection Panels (maintainer-authorized extension): **read-only** inspection of the agent's capabilities/context in the web UI — loaded **skills** (+ load problems), registered **tools**, connected **MCP servers** (+ their tools), and **memory/knowledge** entries. Adds **additive, metadata-only** web/API read endpoints + host query methods composing existing internal layers, rendered as tabbed panels in the 025 shell. **No ADR** (touches neither Tool Gateway execution (V) nor Event Bus (VI); strictly additive — runtime/gateway/bus/existing endpoints unchanged). Read-only (no execute/edit). Model switching + file upload (need an ADR) → unit 028. | 011, 018, 025 | None — implemented & verified on `main` (additive host query methods + 4 `/v1/inspect/*` endpoints + tabbed panel; **747 pytest** + ruff + mypy, **64 Vitest** + build green; no tool exec, no mutation). |
| **028-web-agent-model-files** | `specs/028-web-agent-model-files` | **Verified** | Web Agent Model Selection & File Attachments (maintainer-authorized extension): per-session **model selection** (web/API-layer registry of pre-configured single-model hosts; routes the session's next turn, resuming from the shared checkpoint — runtime keeps **one model per run**) + **file attachments** (upload endpoint, per-principal; agent reads on demand via a **read-upload tool in the Tool Gateway** — files = transient input by id, **not** embedded/artifact/memory). **Additive — NO ADR** (a reference review confirmed neither blurs a runtime boundary; like 027). Tool Gateway (V) / Event Bus (VI) / content model preserved. Multimodal embedded content + cost/pricing out of scope (the former would need an ADR → later unit). | 011, 018, 020, 021, 022, 025 | None — implemented & verified on `main` (model catalog + run routing + upload endpoint + `read_upload` gateway tool + composer selector/attachments; **757 pytest** + ruff + mypy, **68 Vitest** + build green; additive, no ADR). |
| **029-web-agent-extras** | `specs/029-web-agent-extras` | **Verified** | Web Agent Parity Extras (maintainer-authorized extension): **frontend-only** parity polish, **no backend, no ADR** — **i18n** (en + zh-TW + switcher), **code syntax highlighting** (in 025 markdown), a **command palette** (frontend-doable slash + `@file`/`@skill` from the 027 inspection data; backend-semantic commands out of scope), and a **client-side cost estimate** (026 token usage × a bundled price table; server-side pricing deferred). Builds on 025–027. | 011, 018, 025, 026, 027 | None — the final unit; implemented & verified on `main` (i18n + syntax highlighting + command palette + client-side cost; **79 Vitest** + tsc + build green; Python unchanged). The web-UI extension (025–029) is COMPLETE. |
| **030-web-session-management** | `specs/030-web-session-management` | **Verified** | Web Session Management (product-polish sprint): **full-stack, additive, no ADR** — persistent session **title** + **rename** + **delete**. `CheckpointStore.set_title` (append a fresh session-meta; latest wins) + `delete_session` (real removal) on both backends → controller → host → webapi **PATCH/DELETE `/v1/sessions/{id}`** (owner-scoped, non-owner 404); `SessionSummaryView` gains `last_active_at`/`created_at`. Sidebar shows titles grouped Today/Yesterday/Earlier with a rename/delete menu. Tool Gateway (V) / Event Bus (VI) untouched. | 011, 018, 021, 022, 025 | None — implemented & verified on `main` (both checkpoint backends + host/controller + PATCH/DELETE + non-owner 404; **767 pytest** + ruff + mypy + webapi boundary green, **84 Vitest** + build green). |
| **031-web-message-actions** | `specs/031-web-message-actions` | **Verified** | Web Message Actions (product-polish sprint): **frontend-only** — per-message **copy** + **regenerate** (re-run the last user turn via the existing send path) + a **code-block copy** button (react-markdown `pre` override). No backend change. | 025 | None — implemented & verified on `main` (clipboard helper + MessageList copy/regenerate + Markdown code-copy; **90 Vitest** + tsc + build green; Python unchanged). |
| **032-web-interaction-resilience** | `specs/032-web-interaction-resilience` | **Verified** | Web Interaction Resilience & States (product-polish sprint): **frontend-only** — approval/question dialogs become **true modals** (`Modal` + `useFocusTrap`; Esc = safe default; keyboard nav); **error retry + toasts**; **loading skeletons + richer empty state + first-run prompts**. No backend change. | 025, 026 | None — implemented & verified on `main` (Modal/useFocusTrap/Toast/Skeleton + dialog/banner/list wiring; **101 Vitest** + tsc + build green; Python unchanged). The product-polish sprint (030–032) is COMPLETE. |
| **033-file-tool-parity** | `specs/033-file-tool-parity` | **Verified** | File-tool parity (Tier-1 agent-capability sprint, **first unit**): three **additive** baseline tools on the Internal Tool Adapter — `edit_file` (surgical unique-string replacement reusing the `write_file` stale-write guard), `glob_files` (scope-relative filename globbing), and `grep` (regex content search with `content` / `files_with_matches` / `count` modes) — each reachable **only through the Gateway** (V) and confined to the run working scope. `search_files` unchanged; no new dependency, no frontend, no ADR. Closes the "thin built-in toolset" gap vs the reference harnesses. | 001, 009 | None — implemented & verified on `main` (`loopplane.tools.internal`; 21 new offline tests; **788 pytest** + `ruff check` + `mypy`(src, strict) + `ruff format --check` green). |
| **034-web-tools** | `specs/034-web-tools` | **Verified** | Web tools (Tier-1 agent-capability sprint, **second unit**): two **additive** NETWORK tools on a new Web Tool Adapter — `web_fetch` (fetch an http(s) URL to readable text, with a per-session in-memory cache) and `web_search` (run a query through a **host-injected** `SearchProvider`; **no bundled API key/provider** → unconfigured yields a clear normalized error) — each reachable **only through the Gateway** (V). Network egress is gated by an additive `ToolDescriptor.network` flag (default `False`) + a `network_policy` decider that **denies network-flagged tools unless the host opts in** (`RuntimeConfig.allow_network`, default-deny), composed through the **existing** decide-stage combinators (`safe_failure(all_of(...))` — deny-wins + fail-closed) in `_build_decider` — **no new gateway stage**. All failures normalized to `ErrorOutput` with no leaked secret/transport internal (V, VII). `httpx` promoted to an optional extra (`net`), imported lazily; core install unchanged. No frontend, no ADR. | 001, 009 | None — implemented & verified on `main` (`loopplane.tools.web` + `loopplane.governance.network` + `_build_decider` wiring; 26 new offline tests + an opt-in live fetch; **814 pytest** + `ruff check` + `ruff format --check` + `mypy`(src, strict) green). |
| **035-openai-compatible-providers** | `specs/035-openai-compatible-providers` | **Verified** | OpenAI-compatible providers (Tier-1 sprint, **third unit**): two **additive** model providers in a new `loopplane.adapters.openai_compat` package that **reuse** the unit-020 `OpenAIModel` + chat-completions mapping unchanged, differing only in the client `base_url` — `openrouter_model` (OpenRouter; brokers 100+ models incl. Claude/Gemini/Llama behind the OpenAI wire format; injected key) and `ollama_model` (local Ollama; no key — placeholder + overridable `base_url`). **No new dependency** (rides the existing `openai` extra; SDK imported lazily → imports without it; offline-tested via a fake `openai` module). They register like the OpenAI host, so the existing `/v1/models` selector lists them with **no frontend change**. **Native Gemini (direct Google API) deferred** to a follow-up — reachable via OpenRouter today. | 020 | None — implemented & verified on `main` (`loopplane.adapters.openai_compat`; offline base_url / reuse tests; four gates green incl. the 014 api-reference bijection). |
| **038-plan-mode** | `specs/038-plan-mode` | **Verified** | Plan mode (the **first Tier-2 unit** — agentic workflow depth): a LoopPlane-native **read-only investigation → human approval → execute** workflow, **additive, no ADR**, enforced **only at the Tool Gateway decide stage** (V). A `plan_mode_policy` decider (`loopplane.governance.plan_mode`) **denies** any tool with `ToolDescriptor.read_only == False` while plan mode is active, **except** an allowlist (`ask_user`, `exit_plan_mode`) needed to make/submit a plan; read-only tools stay allowed; a **no-op** when inactive. Composed through the **existing** combinators (`safe_failure(all_of(...))` — deny-wins + fail-closed) in `_build_decider` — **no new gateway stage**. Plan-mode activity is a minimal per-run holder `PlanModeState(active)` on an additive `RunContext.plan_mode` field — the **single sharing channel** between the decider (reads it) and a new **`exit_plan_mode`** Internal Tool Adapter tool (flips it on approval), since the Gateway hands **both** the *same* per-run `RunContext` (no process-global state). `exit_plan_mode` (input `plan`, `read_only=False`, allowlisted) submits the plan for a human decision by **reusing the existing human round-trip** (`InteractionBroker.ask_question`, the path `ask_user` uses): approve → clear plan mode (non-read-only tools then allowed) + success; reject / no-human → stay in plan mode + a normalized outcome (no raise across the boundary, V). Entering plan mode is an additive, default-off `RuntimeConfig.plan_mode` flag wired through the controller (one additive constructor kwarg + the per-run `drive()` line — the **only** per-run wiring; the core agent loop / turn cycle is untouched). **No event-schema change** (the round-trip reuses the existing question/answer events; no `SCHEMA_VERSION` bump, VI); every existing tool / descriptor / policy unchanged. | 001, 006, 009 | None — implemented & verified on `main` (`loopplane.governance.plan_mode` + `loopplane.context.PlanModeState` + `exit_plan_mode` + `_build_decider`/controller wiring; 19 new offline tests — 9 policy (deny/allow/allowlist/no-op/fail-closed/deny-wins/off-equals-no-policy), 6 tool (approve-clears / reject-keeps / no-human / no-broker round-trip via a scripted `InteractionBroker` + descriptor flags), 4 assembly wiring; four gates green: ruff + ruff-format + mypy(src, strict) + pytest — **882 passed, 4 skipped** (the prior 863 + the 19 new)). Opens the Tier-2 (agentic workflow depth) line. |
| **039-permission-rule-dsl** | `specs/039-permission-rule-dsl` | **Verified** | Declarative permission rule DSL (a **Tier-2 governance unit**): a **host-suppliable** declarative permission rule set enforced **only at the Tool Gateway decide stage** (V), additive and **no ADR**. A host supplies a `PermissionRuleSet` of `PermissionRuleSpec` rules — each a `tool` (exact name or `fnmatch` pattern, e.g. `mcp:*`), an optional `match` (input-field → **regex**, or a **path-glob** for path-shaped fields `path`/`file`/`*_path`, e.g. `{command: "^rm -rf"}`), and a `decision` of `allow` | `deny` | `ask` — plus a top-level `default` for no match. A `rule_dsl_policy` (`loopplane.governance.rule_dsl`) decider selects the rules whose `tool` matcher **and** every `match` match the call, combines **deny-wins** (deny > ask > allow — reusing `resolve_rules`' deny-wins for the name dimension), falls back to `default`, and returns the **existing** `PolicyVerdict`: `allow`→`PolicyAllow`, `deny`→`PolicyDeny`, **`ask` reuses the existing approval round-trip** (`InteractionBroker.request_approval`, the Human Approval path) mapping the human's resolution to allow/deny. **Verdict-model finding**: the decide-stage verdict is **binary** (`PolicyAllow | PolicyDeny`; **no `PolicyAsk`**), so "ask" is decider behaviour reusing `request_approval`, making `rule_dsl_policy` an async, context-reading decider (like `plan_mode_policy`). Composed through the **existing** combinators (`safe_failure(all_of(...))` — deny-wins + fail-closed) in `_build_decider` — **no new gateway stage**. `match` patterns are **compiled eagerly at construction** → a malformed regex/glob is a clear config error there (fail-closed), never a silent decide-time allow. The rules are an additive, default-empty, public-safe `RuntimeConfig.permission_rules` field (tool names + patterns + decisions only; **no secret**), coerced in `from_mapping`; absent/empty → no policy installed and existing runs **byte-identical**. **No event-schema change** (`ask` reuses the existing approval events, VI); **no per-run/controller/loop change** (`ask` reads the per-run `RunContext` the Gateway already hands the decider); the approval boundary + every existing tool/descriptor/policy unchanged. | 001, 006, 009 | None — implemented & verified on `main` (`loopplane.governance.rule_dsl` + `RuntimeConfig.permission_rules` + `_build_decider` composition; 24 new offline tests — 20 policy (arg-regex / path-glob / fnmatch / absent-field / coercion / empty-no-op / ask approve-reject-no-reviewer / default-ask / deny-wins / default / invalid-regex-config-error / fail-closed / deny-wins-in-chain) + 4 assembly wiring (decider denies the matching call + allows the non-matching / no-rules + empty-rules keep the allow-all fast-path / from_mapping round-trip + no-secret); four gates green: ruff + ruff-format + mypy(src, strict) + pytest — **906 passed, 4 skipped** (the prior 882 + the 24 new)). A Tier-2 governance unit (reuses the existing rule/verdict/approval machinery; a new decider + config field + assembly composition only). |
| **040-prompt-caching** | `specs/040-prompt-caching` | **Verified** | Anthropic prompt caching (the **first Tier-3 / cost-efficiency unit**): explicit prompt-cache breakpoints so repeated agent-loop turns re-read a stable request prefix at ~0.1x input price instead of full price — **additive, reuse-first, no ADR**. A pure, opt-in overlay `apply_prompt_caching(messages, tools)` in `anthropic/mapping.py` attaches `cache_control: {"type": "ephemeral"}` to the **stable prefix only** — the **last tool definition** (the end of the stable tools segment, which renders first in the `tools → system → messages` order) + the **last content block of the first message** (a stable leading-history prefix; LoopPlane carries the system prompt as the leading message — there is no top-level `system` key — so this *is* the system/tools-equivalent boundary), **gated on ≥2 messages so it is NEVER the rolling tail** — emitting **at most 2 of the Anthropic-max 4** breakpoints. An additive `AnthropicConfig.prompt_caching: bool` (default **True** — a near-pure win: a cache read is ~0.1x and a write ~1.25x, so two turns sharing a prefix already break even, and an agent loop re-sends the prefix every turn) gates it; the adapter runs the overlay only when on. **Off → byte-identical request** (the overlay is not called; `build_messages` / `build_tools` stay unchanged → the unit-020 mapping tests stay green and a dedicated test proves identity). **Transparent to the loop** — caching changes only the provider request shape, not loop behavior or the event stream: **no event-schema / content-model / `TokenUsage`-shape change** (caching is observed through the existing `TokenUsage.cached_tokens`, mapped from Anthropic `cache_read_input_tokens`). **OpenAI / OpenRouter / Ollama caching is automatic — NO request change**: the adapter sends no cache parameter and `prompt_tokens_details.cached_tokens` is already mapped (confirmed + a focused test); Gemini implicit caching is provider-managed and out of scope. **No new public package / `__all__` name** (toggle = a field on `AnthropicConfig`; helper = a non-exported module function) → the unit-014 api-reference bijection stays green with no doc edit. **No change to the loop, runtime core, Tool Gateway, or Event Bus.** | 020, 035 | None — implemented & verified on `main` (`apply_prompt_caching` overlay + `AnthropicConfig.prompt_caching` + the one `adapter.py` call site; **16 new offline tests** — overlay placement / 4-max / never-the-tail / no-tools / single-message / empty-content / purity + adapter on/off/default/no-tools, plus a focused OpenAI `cached_tokens` confirmation; the unit-020 Anthropic mapping tests **unchanged**; four gates green: ruff + ruff-format + mypy(src, strict) + pytest). The next Tier-3 follow-on is **041** (configurable compaction). |
| **041-auto-compaction** | `specs/041-auto-compaction` | **Verified** | Configurable proactive auto-compaction (the **second Tier-3 / efficiency unit**): make LoopPlane's **existing** proactive pre-send compaction trigger **configurable**, additive and reuse-first, **no ADR**. The prompt assembler (`loop/assembly.py`) already estimates the assembled context (the existing `_estimate_tokens` `chars ÷ 4` heuristic — **the** reusable size measurement; there is no exact tokenizer, and the artifacts/recall code measures bytes/recall-candidates, not assembled context) and, when it exceeds the model's **full** `context_capacity()`, runs the **mechanical** `compact_history` once before the model call; the loop keeps the **reactive** `ContextOverflowError` compact-and-retry-once backstop (FR-008). This unit adds an additive, default-`None` `RuntimeConfig.auto_compact_threshold: float | None`: `None` → the pre-send check uses the **full** capacity (today's exact behavior → **byte-identical** off), a fraction `f` in `(0, 1]` → the check uses `f * context_capacity()` (a tiny `_effective_capacity` helper), so the **same** compaction runs **earlier**, on a safety margin. **Reuses `compact_history` verbatim** (the `SummaryMarkerBlock` / `SummaryDigest` digest is unchanged — no new algorithm) and **reuses `_estimate_tokens` unchanged** (no tokenizer, no new dependency; the estimate is a margin trigger and the reactive overflow path stays the backstop if it under-counts). Threaded through the same wiring as `plan_mode`/`allow_network` (`RuntimeConfig` → `assemble()` → `RuntimeController` → per-session `PromptAssembler(compact_threshold=...)`), coerced in `from_mapping`, **validated fail-fast** (a non-`None` value must be a finite number in `(0, 1]`, else `ConfigError`; `1.0` is valid = the full-window trigger), no secret. **Compaction stays silent** — it emits **no** runtime event today (mutates in-memory history only; the durable stream keeps the originals via `replace_prefix`) and the proactive path emits none either: **no event-schema change, no `SCHEMA_VERSION` bump (VI), no content-model / `TokenUsage`-shape change, no change to the agent loop's turn cycle (III — a bounded opt-in efficiency trigger reusing existing compaction, NOT the reserved loop-automation layer), the Tool Gateway, or the Event Bus**. No new public package / `__all__` name (a field on `RuntimeConfig`; constructor params on the assembler/controller; a private `_effective_capacity`), so the unit-014 api-reference bijection stays green with no doc edit. The **cheap-model summarizer** (an optional summarizer `ModelBoundary` during compaction) is **deferred** to spec 042 — folding a model call into the compaction path adds real complexity/risk for a secondary benefit (research.md Decision 3). | 001, 020, 040 | None — implemented & verified on `main` (`PromptAssembler.compact_threshold` + `_effective_capacity` + `RuntimeController.auto_compact_threshold` + `RuntimeConfig.auto_compact_threshold` with `from_mapping`/`validate_config` + the `assemble()` wiring; **19 new offline test nodes** (`tests/unit/test_auto_compaction.py`) — effective-capacity math, proactive at/over/under threshold incl. a same-history/same-capacity threshold-vs-`None` proof, default-`None` byte-identity (no compaction below full capacity, the existing full-capacity trigger preserved above), the reactive backstop unchanged, the invalid-threshold `ConfigError` (parametrized over 0 / negative / >1 / NaN / inf), `from_mapping` round-trip + no-secret; the existing compaction/assembly/loop tests **unchanged**; four gates green: ruff + ruff-format + mypy(src, strict) + pytest **938 passed, 4 skipped** = the prior 919 + 19 new). The remaining Tier-3 follow-on is the **cheap-model summarizer (spec 042, deferred)**. |
| **042-compaction-summarizer** | `specs/042-compaction-summarizer` | **Verified** | Optional cheap-model compaction summarizer (the **third Tier-3 / efficiency unit — the deferred half of 041**): an **optional**, **FAIL-SAFE** model-written compaction summary, additive and reuse-first, **no ADR**. Today `compact_history` produces a **mechanical** digest (`SummaryMarkerBlock` → `SummaryDigest` with turn count + tool names + bounded excerpts). This unit adds a default-`None` `RuntimeConfig.compaction_summarizer: ModelBoundary | None`: when a host supplies a (cheap) summarizer model, compaction asks it to summarize the dropped conversation span and stores the model summary in the **existing** `SummaryMarkerBlock` (replacing the mechanical `excerpts`; `turn_count` / `tool_names` stay mechanical); `None` → the mechanical digest, **byte-identical** to today. **Seam findings (verified)**: `compact_history` and `PromptAssembler.assemble` are **synchronous**, and `assemble` has a direct synchronous production caller (`AgentLoop._assemble`) plus synchronous test callers, so it **cannot** become async (forbidden breaking change); a model call (`ModelBoundary.stream_turn`) is async. The summary text lives in the existing `SummaryDigest.excerpts`. **Design**: the summarizer runs as an **additive async overlay at the loop's two existing async compaction seams** — once after assembly (the proactive 041 trigger, which the assembler signals via a one-shot `take_compacted()` flag) and once in the `except ContextOverflowError` handler (the reactive 041 backstop). `compact_history` is **unchanged** — the mechanical marker is always produced first and is the fail-safe **fallback**; the overlay (`loopplane.loop.summarizer.summarize_compaction`) only augments it, swapping the marker in place via a tiny additive `SessionHistory.replace_entry` (durable stream keeps the originals, like `replace_prefix`). The agent loop's **turn-cycle structure is preserved** (one awaited overlay step at the two existing points). **FAIL-SAFE (the non-negotiable property)**: **any** summarizer failure — an exception, `ContextOverflowError`, an `anyio.fail_after` timeout, or empty/whitespace output — is swallowed so the mechanical digest stands; compaction always succeeds and **a run is never broken by the summarizer**. The summarizer is a single plain model turn (no assembler, no tools), so it **cannot recurse** into compaction. It is an object collaborator like `model`, threaded through the same wiring as `auto_compact_threshold` (`RuntimeConfig` → `assemble()` → `RuntimeController` → per-session `AgentLoop(summarizer=...)`), passes through `from_mapping` unchanged, and carries **no secret**. **Reuses the existing `SummaryMarkerBlock` / `SummaryDigest` — no new block, no event-schema change, no `SCHEMA_VERSION` bump (VI), no content-model change, no Tool Gateway / Event Bus change**. No new public package / `__all__` name (the summarize helper is an internal module without `__all__`; `RuntimeConfig` already exported, `ModelBoundary` already public), so the unit-014 api-reference bijection stays green with no doc edit. | 001, 020, 041 | None — implemented & verified on `main` (`loopplane.loop.summarizer.summarize_compaction` + `SessionHistory.replace_entry` + `PromptAssembler.take_compacted` one-shot flag + `AgentLoop.summarizer` param & two overlay calls + `RuntimeController.compaction_summarizer` + `RuntimeConfig.compaction_summarizer` with `from_mapping` pass-through + the `assemble()` wiring; **16 new offline test nodes** (`tests/unit/test_compaction_summarizer.py`) — the overlay in isolation (success / dropped-span+no-tools / raise / overflow / empty / timeout), driven reactive compaction (model summary lands; `None` byte-identical to the bare `compact_history` marker + no model call; the parametrized FAIL-SAFE raise/empty/overflow + a monkeypatched-timeout case), proactive (041-threshold) compaction also summarizes, and `from_mapping` round-trip + no-secret; the existing compaction/assembly/loop tests **unchanged**; four gates green: ruff + ruff-format + mypy(src, strict) + pytest **954 passed, 4 skipped** = the prior 938 + 16 new). Closes the deferred 041 follow-on; the Tier-3 efficiency line (040–042) is COMPLETE. |
| **043-dynamic-subagents** | `specs/043-dynamic-subagents` | **Verified** | Model-driven one-shot subagents (a **Tier-2 autonomy unit**): an **additive**, opt-in `spawn_subagent` **Tool-Gateway** tool (a new `SpawnSubagentAdapter` in `loopplane.tools.subagent`) that lets the model delegate a focused sub-task to **one** bounded child agent — the autonomy primitive both reference harnesses expose (claude-code `Agent`, orion `SubAgentCreate`). **Reuse-first, no loop rewrite**: the child is driven through the **existing** public Phase-3 `loopplane.engineering.run_loop` (the same seam unit-013's **host-driven** coordinator composes) — the adapter builds a **one-shot `LoopDefinition`** (a `ManualTrigger` + `StaticInput(task)` + a `HostRuntimeProfile` selector building a depth-incremented child host + an always-pass `ValidationPolicy` + `max_iterations(1)` + `ObservationPolicy(emit_loop_events=True)`, mirroring `tests/orchestration_helpers.py`), calls `run_loop` with **no live sink**, and returns the child's **final assistant text** (recovered from the child host's `history_snapshot(session_id)`). **The agent loop, the orchestration core (`loopplane.orchestration` keeps its strict engineering-only import boundary — the tool lives in the `tools` layer and only *reuses* `aggregate_events` from the allowed direction), the gateway pipeline, the event schema, and the content model are UNCHANGED.** **SAFE under a hard recursion-depth cap (the non-negotiable, fail-safe property)**: an additive `RunContext.subagent_depth` (default 0; a child runs at parent + 1, threaded through an additive defaulted `RuntimeController(subagent_depth=...)` kwarg → the one `RunContext` construction site in `drive()`) + a configurable `RuntimeConfig.max_subagent_depth` (default `0` = off, byte-identical to today; a host sets it to `1` to enable exactly one level); the tool **DENIES** a spawn (a normalized `POLICY_DENIAL` error, **no** child run created) once `subagent_depth >= max_subagent_depth`, so subagents cannot nest without bound (a counting child-host factory proves **zero** child builds at the cap). `max_subagent_depth = 0` registers **no** tool (feature off). **Failure contained** (mirrors the 013 coordinator): a child that raises / fails to complete / pauses / answers empty → a fixed public-safe normalized `ErrorOutput` (never a raw exception/stack trace/secret); the parent run continues. Defense in depth: the Gateway's own `invoke` try/except + per-call time limit also bound an over-run. **Events** (Constitution VI): the child's loop events are **captured** in its `LoopOutcome` and surfaced only as **metadata-only** aggregation (the 013 `aggregate_events` view) — never re-emitted onto the parent's live bus (a test asserts no foreign-session event leaks). An optional `allowed_tools` restricts the child to a least-privilege subset of the parent's tools (host-declared `ToolSpec`s filtered by name; a multi-tool adapter is kept only when **every** tool it advertises is allowlisted, else dropped whole — the Tool Gateway stays the single owner of tool dispatch, V). Reachable **only** through the Gateway (V); no new dependency, no frontend, **no ADR**. Agent-to-agent messaging, swarm / peer coordination, and persistent / named / background subagents are **deferred**. | 001, 002, 003, 013 | None — implemented & verified on `main` (`loopplane.tools.subagent.SpawnSubagentAdapter` + `RunContext.subagent_depth` + `RuntimeConfig.max_subagent_depth` (+ `from_mapping`/`validate_config`) + `RuntimeController.subagent_depth` kwarg & the `drive()` line + the `host/assembly.py` registration/child-host factory/`_restrict_config`; **18 new offline test nodes** (`tests/unit/test_subagent_spawn.py` + `tests/subagent_helpers.py`) — the spawn round-trip (parent gets the child's final text; one child host at depth 1), descriptor shape, the **depth-cap denial with ZERO child runs** + child-depth=parent+1 + default-cap-blocks-a-grandchild, raising/empty-child containment, restricted-`allowed_tools` filtering + inherit-when-omitted, child-events-not-on-the-parent-bus, the assembly gating (tool present iff cap ≥ 1), and missing-`task` validation with no child run; the agent-loop/orchestration/gateway/event tests **unchanged**; four gates green: ruff + ruff-format + mypy(src, strict) + pytest). A Tier-2 autonomy unit (adds the model-driven counterpart to 013's host-driven orchestration). |
| **037-gemini-adapter** | `specs/037-gemini-adapter` | **Verified** | Native Google Gemini adapter (the deferred 035 follow-up, named in 035 research Decision 2 + ADR 0001 Follow-up #3): a **native** `loopplane.adapters.gemini` (`GeminiModel` + `GeminiConfig`) over the **direct** Google GenAI API (the official `google-genai` SDK, behind a new optional `gemini` extra), distinct from the OpenAI-compatible OpenRouter path. Mirrors the unit-020 adapters — lazy SDK import inside the client factory (imports without the extra), duck-typed stream mapping, offline stub-tested. `gemini/mapping.py` maps content/tools to Gemini's `contents`/`function_declarations`/`inline_data` and decodes the chunk stream (text / thought→`ReasoningIncrement` / `function_call`→raw `ToolCallRequest`; `usage_metadata`→`TokenUsage`; one `TurnEnd`); overflow→`ContextOverflowError`, other faults→public-safe `ModelProviderError` (shared `_model_errors`, no key/raw-body leak). Advertises `accepts_media()` (default `True`; `ImageBlock`→`inline_data`) and registers as a `/v1/models` host with **no frontend change**. **The content model + event schema are UNCHANGED** (no `ToolCallBlock` field, **no `SCHEMA_VERSION` bump**, **no ADR**): multi-turn tool use is made functional via Google's official `"skip_thought_signature_validator"` sentinel (attached on a re-mapped `function_call` part, never in the `args` the gateway validates) — preserving the *real* per-call signature is a documented deferred VI/ADR follow-up. Tool calls surface **raw** (V); only normalized increments reach the loop (VI); the SDK enters only as a model-boundary adapter (VIII). New optional extra `gemini` (`google-genai>=1`); **no required** runtime dependency. | 020, 035, 036 | None — implemented & verified on `main` (`loopplane.adapters.gemini` 4-file package; offline mapping/stream/tool-round-trip tests + the parametrized overflow/failure/usage suites now exercising "gemini" + an opt-in live turn; four gates green: **863 passed, 4 skipped** + ruff + ruff-format + mypy(src, strict); the api-reference bijection + packaging-extras set updated). |
| **036-multimodal-input** | `specs/036-multimodal-input` | **Verified** | Multimodal input (Tier-1 sprint, **fourth + final unit**; carries the repo's **first ADR**, `docs/adr/0001-multimodal-content.md`): **image input end-to-end**, additive. Image content was already modeled and contract-safe (`ImageBlock` in `ContentBlock`/`OutputBlock`, round-trips through the event schema, maps to Anthropic/OpenAI — OpenRouter/Ollama inherit), so **the content model + event schema are UNCHANGED** (no `SCHEMA_VERSION` bump; ADR D1). The unit wires the 028 upload path into the model at the **web edge** — optional `RunRequest.uploads` (`UploadRef`) → **leading `ImageBlock`s** via a pure `webapi.multimodal.assemble_blocks` (image-type sniffing; non-image uploads stay `read_upload`-readable) — plus **provider capability negotiation**: an additive duck-typed `loopplane.model.accepts_media(model)` probe (the `ModelBoundary` Protocol stays two methods; ADR D5) + an `accepts_media` flag on the two adapter configs (default `True`) / `openrouter_model` (`True`) / `ollama_model` (`False`); the web/API layer rejects an image to a text-only model (HTTP 400) and `/v1/models` advertises `accepts_media`; an oversized image is capped (HTTP 413; ADR D6). The input vocabulary (`Prompt`/`ContentBlock`/`TextBlock`/`ImageBlock`) is exposed via the `loopplane.host` seam. **PDF (`DocumentBlock`) deferred** (no base64 PDF in OpenAI chat-completions → would pull in binary artifact durability + a non-text gateway handoff; ADR D2/D3/D4 follow-up); artifact store + Tool Gateway **unchanged**. | 020, 028, 035 | None — implemented & verified on `main` (`loopplane.model.capabilities` + adapter flags + `loopplane.webapi.multimodal` + run-endpoint wiring; 28 new offline tests incl. the `ImageBlock`-bearing event round-trip; four gates green: **846 pytest** + ruff + ruff-format + mypy(src, strict)). |
| **044-todo-tool** | `specs/044-todo-tool` | **Verified** | Tier-1 agent-capability (closes gap **G1** vs the reference harnesses, per `docs/gap-analysis.md`): an agent-facing task-list tool (e.g. `todo_write`) on the Internal Tool Adapter so the model can track multi-step work — an ordered list of items, each with a status (pending / in_progress / completed), surfaced as metadata only. Additive, reachable **only** through the Gateway (V); no event-schema / content-model change; no ADR. | 001 | None — implemented & verified on `main` (`todo_write` in `loopplane.tools.internal`; 11 offline tests; four gates green, pytest 977 passed). |
| **045-structured-output** | `specs/045-structured-output` | **Verified** | Tier-1 agent-capability (closes gap **G3**): model-native structured output — let a caller request a JSON-schema-constrained response (`response_format`) mapped through the existing model boundary / adapters, with graceful degradation when a provider lacks native support. Additive; reuses the `packs` JSON-schema validators for verification; no event-schema change; no ADR. | 001, 020 | None — implemented & verified on `main` (OpenAI-family `response_format` json_schema; `supports_structured_output` capability probe; 13 offline tests; four gates green, pytest 990 passed). |
| **046-notebook-edit** | `specs/046-notebook-edit` | **Verified** | Tier-1 agent-capability (closes gap **G2**): a `notebook_edit` Internal Tool Adapter tool to edit Jupyter (`.ipynb`) cells within the working scope (insert / replace / delete a cell by index or id), reusing the stale-write guard pattern. Additive, Gateway-only (V); no schema change; no ADR. | 001, 033 | None — implemented & verified on `main` (`notebook_edit` in `loopplane.tools.internal`; stdlib-json round-trip; 10 offline tests; four gates green, pytest 1000 passed). |
| **047-search-provider** | `specs/047-search-provider` | **Verified** | Tier-1 agent-capability (closes gap **G4**): a reference `SearchProvider` implementation behind an optional extra so `web_search` (034) works out of the box — host-configurable, with **no** bundled API key required at import (lazy). Additive; reuses the 034 web-tool seam + network governance; no ADR. | 034 | None — implemented & verified on `main` (`ReferenceSearchProvider` in `loopplane.tools.search`; keyless DuckDuckGo default; 9 offline tests; four gates green, pytest 1009 passed). |
| **048-background-tasks** | `specs/048-background-tasks` | **Not started** | Tier-2 autonomy (closes gap **G5** vs the reference harnesses, per `docs/gap-analysis.md`): agent-facing background / long-running task tools (create / get / list / stop / output) so the model can launch and manage work that outlives a single turn, building on the existing run/loop seams. Likely touches the controller/host run path — a plan-stage boundary review decides additive-vs-ADR. | 001, 003 | Run `/speckit.specify` (autopilot). |
| **049-agent-scheduling** | `specs/049-agent-scheduling` | **Not started** | Tier-2 autonomy (closes gap **G6**): agent-facing scheduling / recurring-run tools that wrap the unit-004 in-process scheduler so the model can schedule, list, and cancel triggers (host-governed). Reuses the 004 scheduler; no new scheduling engine. | 004 | Run `/speckit.specify` (autopilot). |
| **050-agent-messaging** | `specs/050-agent-messaging` | **Not started** | Tier-2 autonomy (closes gap **G7**): agent-to-agent messaging / lightweight swarm coordination extending unit-013 (host-driven orchestration) + unit-043 (one-shot subagents) — peer message passing between coordinated agents. The most architecturally significant Tier-2 unit (explicitly deferred by 043); **likely needs an ADR** + a maintainer decision at plan. | 013, 043 | Run `/speckit.specify` (autopilot). |
| **051-worktree-isolation** | `specs/051-worktree-isolation` | **Not started** | Tier-2 autonomy (closes gap **G8**): per-agent git worktree isolation so a subagent / run can work in an isolated copy of the repo without disturbing the main worktree, then be cleaned up. | 001 | Run `/speckit.specify` (autopilot). |

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
- **027 — Web Agent Inspection Panels (maintainer-authorized extension, 2026-06-19), COMPLETE.**
  Additive, read-only, metadata-only inspection of the agent's capabilities/context. Backend:
  `assemble()` retains the `gateway` / `skills` / `memory_store` on `AssembledRuntime` (additive);
  `loopplane/host/inspect.py` holds pure projections (skills drop `instructions`; tools; MCP servers
  derived from the `external-server:` descriptor source — never the config's `args`/`url`; a bounded
  memory snippet) behind four `LoopPlaneHost` query methods; four auth-gated
  `GET /v1/inspect/{skills,tools,mcp,memory}` endpoints (Pydantic views). Frontend: api types +
  client methods + a tabbed `InspectionPanel` (empty states + memory search) in the 025 shell,
  toggled from the header. **Executes no tool, mutates nothing** (V/VI untouched); **no ADR**.
  **747 pytest** (pure-projection unit + a webapi integration suite: auth-gated, metadata-only,
  no-tool-exec, empty-state) + ruff + mypy(strict) green; **64 Vitest** + tsc-strict + vite build
  green. Additive — existing tests unchanged. Rollback = drop the endpoints/panel + the retained
  refs. → **Verified**.
- **028 — Web Agent Model Selection & File Attachments (maintainer-authorized extension,
  2026-06-19), COMPLETE.** Additive, web/API-layer, **no ADR**. **Model selection**:
  `create_app(host, *, models=…)` holds a catalog of pre-configured single-model hosts (the
  `ModelHost` entries) sharing the unit-021 checkpoint root; `GET /v1/models` lists it; runs +
  session-open accept a `model` id that `_select_host` routes to the chosen host — the runtime
  receives **one model per run** (never switches internally). **Files**: a pure per-reference
  `UploadStore` (`webapi/uploads.py`) + `POST /v1/uploads` (raw octet-stream body, auth-gated,
  per-principal, size-limited) + a `read_upload` gateway tool (`loopplane.host.upload_tool`, a
  capability read by reference) the agent calls on demand — transient input by id, **never embedded**
  into the content model. Frontend: a composer `ModelSelector` + `Attachments`. The webapi boundary
  is preserved (it imports only host/events — the tool lives in the host layer). **757 pytest**
  (UploadStore + read_upload unit; catalog/routing/upload integration: routed run, unknown→400,
  per-principal, size-limit, auth) + ruff + mypy(strict) green; **68 Vitest** + tsc-strict + build
  green. Multimodal embedded content (a Principle IV change) is deferred. Rollback = drop the
  catalog/routing + upload endpoint/store/tool + composer UI. → **Verified**.
- **029 — Web Agent Parity Extras (maintainer-authorized extension, 2026-06-19), COMPLETE.**
  Frontend-only, no backend, no ADR. **i18n**: an in-house `t()` over `en` + `zh-TW` string maps
  (`src/i18n/`), an `I18nProvider` persisting `localStorage["loopplane-locale"]`, a
  `LanguageSwitcher`, with an English fallback (key chrome localized; assistant content untranslated).
  **Highlighting**: `rehype-highlight` on the unit-025 `Markdown` with theme-bound `hljs` token CSS
  and a plain fallback. **Command palette**: a composer `CommandPalette` — `/` lists frontend-doable
  commands (toggle inspection) and `@` autocompletes skill/tool mentions from the unit-027 inspection
  data; backend-semantic commands are out of scope (`@file` has no frontend inventory). **Cost
  estimate**: `pricing.ts` (bundled table) × the unit-026 usage for the unit-028 selected model,
  shown by `UsageIndicator` as a labeled estimate (token counts only when no price). Each degrades
  gracefully. **79 Vitest** (i18n / switcher / palette / pricing / markdown-hljs / usage-cost + the
  025–028 suites) + tsc-strict + `vite build` green; one new dep (`rehype-highlight`); the Python
  suite is unchanged (frontend-only). Rollback = revert the `apps/web` diff → units 025–028.
  → **Verified**. **With 029, the web-UI extension (025–029) is COMPLETE.**

> **✅ PRODUCT-POLISH SPRINT COMPLETE — `030-web-session-management` → `031-web-message-actions` → `032-web-interaction-resilience` (maintainer-authorized, 2026-06-19).** After the web-UI extension (025–029, COMPLETE — banner below), the maintainer authorized a **product-polish sprint** (high-impact UX + session usability), frontend-first plus one additive backend unit. Three units, **all `Verified` on `main`**:
> - **030-web-session-management** (full-stack, additive, **no ADR**) — **Verified** (shipped): persistent session **title** + **rename** + **delete** (`CheckpointStore.set_title`/`delete_session` on both backends → controller → host → **PATCH/DELETE `/v1/sessions/{id}`**, owner-scoped non-owner 404; `SessionSummaryView` gains `last_active_at`/`created_at`); sidebar titles grouped Today/Yesterday/Earlier with a rename/delete menu. Python **767 passed** + ruff + mypy-strict + webapi boundary green; apps/web **84 Vitest** + tsc + build green.
> - **031-web-message-actions** (frontend-only) — **Verified** (shipped): per-message copy + regenerate (re-run the last user turn) + code-block copy. **90 Vitest** + tsc + build green.
> - **032-web-interaction-resilience** (frontend-only) — **Verified** (shipped): true modals (`Modal` + `useFocusTrap`, Esc = safe default), error retry + toasts, loading skeletons + richer empty state + first-run prompts. **101 Vitest** + tsc + build green.
>
> Sequence **030 → 031 → 032** on `main`. **030 + 031 + 032 are all `Verified`** — the **product-polish sprint is COMPLETE**. The autopilot has no further unit and the `/loop` was stopped (CronDelete). *(The web-UI-extension banner below — 025–029 — remains COMPLETE; this sprint built on it.)*

> **✅ WEB-UI EXTENSION COMPLETE — `025-web-agent-ui` → `026-web-agent-signals` → `027-web-agent-inspection` → `028-web-agent-model-files` → `029-web-agent-extras` (maintainer-authorized web-UI extension, 2026-06-19).** The original roadmap (000–019, v0.1.0; MIT) and the four-phase gap-closure (020–024) remain COMPLETE and `Verified`. Beyond them, the maintainer authorized a **web-UI extension** to bring the unit-018 SPA to parity with a modern agent app. Five units, **all `Verified` on `main`**:
> - **025-web-agent-ui** (frontend-only) — **Verified** (shipped): two-pane shell, markdown, inline tool cards, styled dialogs, status + Stop, sessions, light/dark theme.
> - **026-web-agent-signals** (frontend-only) — **Verified** (shipped): reasoning/thinking display, multi-option questions, token usage (signals the backend **already emits**).
> - **027-web-agent-inspection** (additive, metadata-only, **no ADR**) — **Verified** (shipped): read-only skills / tools / MCP / memory endpoints + tabbed panel.
> - **028-web-agent-model-files** (additive, **no ADR**) — **Verified** (shipped): per-session model selection (web/API-layer host registry + shared-checkpoint routing; runtime keeps one model per run) + file attachments (upload endpoint + a **read-upload tool in the Tool Gateway**, Principle V; files read on demand, not embedded). Multimodal embedded content (which would need an ADR) is deferred.
> - **029-web-agent-extras** (frontend-only, no ADR) — **Verified** (shipped): i18n (en + zh-TW), code syntax highlighting, command palette (frontend slash + `@skill`/`@tool` from 027 data), client-side cost estimate.
>
> **025–029 are all `Verified`** (shipped on `main`) — the **web-UI extension is COMPLETE**. The unit-018 SPA now has: a styled two-pane shell + markdown + tool cards + dialogs + theme (025); reasoning / multi-option questions / token usage (026); read-only skills/tools/MCP/memory inspection panels (027); per-session model selection + file attachments (028); and i18n + syntax highlighting + a command palette + a client-side cost estimate (029). The autopilot has **no further unit to advance** and stops cleanly. Only reserved/out-of-scope items remain: multimodal embedded file content + backend-semantic slash commands (need an ADR / backend) and authoritative server-side pricing.

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
| Active unit | **043-dynamic-subagents COMPLETE** — a **Tier-2 autonomy unit**: the **model-driven** counterpart to unit-013's **host-driven** orchestration. An **additive**, opt-in `spawn_subagent` Tool-Gateway tool (`SpawnSubagentAdapter` in `loopplane.tools.subagent`) lets the model delegate a focused sub-task to **one** bounded child agent, driven through the **existing** public Phase-3 `run_loop` (no agent-loop rewrite; the adapter builds a one-shot `LoopDefinition`, passes no live sink, and returns the child's final assistant text from the child host's history snapshot). **SAFE under a hard recursion-depth cap (fail-safe, non-negotiable)**: an additive `RunContext.subagent_depth` (default 0; child = parent + 1, threaded via an additive `RuntimeController(subagent_depth=...)` kwarg → the one `drive()` `RunContext` site) + a configurable `RuntimeConfig.max_subagent_depth` (default 0 = off; set to 1 to enable one level); the tool **DENIES** a spawn (a normalized error, **no** child run) once `subagent_depth >= max_subagent_depth` — proven by zero child builds at the cap. `max_subagent_depth = 0` (the default) registers no tool (off). A failing/over-running/empty child is **contained** (a public-safe normalized error; the parent continues), mirroring the 013 coordinator. The child's events are **captured** and surfaced only as metadata-only aggregation (the 013 `aggregate_events` view), never on the parent's live bus (VI). An optional `allowed_tools` gives least-privilege child toolsets. Enforced at the Gateway (V); the **agent loop, orchestration core, gateway pipeline, event schema, and content model are UNCHANGED**; no new dependency, no frontend, no ADR. All prior units (001–042) plus 043 are `Verified` on `main`. **Tier-1 (044–047) is COMPLETE — all `Verified` on `main`. Tier-2 autonomy units 048–051 are now registered in §3; the active unit is `048-background-tasks` (Not started) — next step `/speckit.specify`.** |
| Active feature directory | `.specify/feature.json` → `specs/047-search-provider` (047 verified). The next active unit `specs/048-background-tasks` is created by `/speckit.specify`, which updates `feature.json`. |
| Current branch | `main` — **main-only autopilot**; all units progressed on `main` (see §7 Branch Strategy) |
| Current Spec Kit step | **043 COMPLETE** (specify → plan → tasks → implement → Verified; `loopplane.tools.subagent.SpawnSubagentAdapter` + `RunContext.subagent_depth` + `RuntimeConfig.max_subagent_depth` (+ `from_mapping`/`validate_config`) + `RuntimeController.subagent_depth` kwarg & the `drive()` line + the `host/assembly.py` registration / child-host factory / `_restrict_config`; the child run reuses the **existing** `run_loop` — **no agent-loop / orchestration-core / gateway-pipeline / event-schema / content-model change, no new core public `__all__` name beyond the additive `SpawnSubagentAdapter` tools export, no ADR**). The hard depth cap denies a spawn at/over the max with zero child runs (a test proves no unbounded nesting); a child failure is contained; the child's events never touch the parent's live bus. |
| Depends on | 043 built on 001/002 (the runtime + host/`RuntimeConfig`/`assemble` wiring + the `RunContext` the Gateway hands every tool), 003 (the public Phase-3 `run_loop` / `LoopDefinition` / `LoopOutcome` it composes for the child run), and 013 (the orchestration seam it mirrors — the same `run_loop` composition + the reused metadata-only `aggregate_events`). |
| Next command | `/speckit.specify` for **048-background-tasks** (autopilot). The Tier-2 autonomy line now has both host-driven (013) and model-driven one-shot (043) subagents. Other untouched lines remain (agent-to-agent messaging / swarm / persistent subagents [deferred], backend slash commands, server-side pricing, multimodal embedded content [needs an ADR]). |
| Stop condition status | **Active** — 001–047 are all `Verified`; Tier-2 autonomy units 048–051 are registered and pending. Autopilot proceeds to `048-background-tasks`. |

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
