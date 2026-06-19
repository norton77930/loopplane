# Changelog

All notable changes to LoopPlane are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
Semantic Versioning.

## [0.1.0] - 2026-06-18

The initial LoopPlane line: a spec-first, embeddable agent-harness runtime and its
additive layers (units 001-013), brought to release quality by unit 014.

### Added

- **001** Runtime foundation — the agent loop, runtime controller, dispatcher, the
  tool gateway, internal and MCP tool adapters, skill execution profiles, the
  normalized runtime event bus, memory, checkpointing, artifact storage, the
  observability overlay, and the human-approval boundary.
- **002** Host interface (`loopplane.host`) — the Host Application Interface, a
  programmatic runtime configuration object, and a reference runner.
- **003** Loop engineering (`loopplane.engineering`) — loop definitions, the loop
  controller, triggers, validators, evaluators, retry/repair, reconstructable loop
  state, and loop events.
- **004** Scheduling (`loopplane.scheduling`) — the local scheduler and trigger
  engine with an injectable clock.
- **005** Validator & evaluator packs (`loopplane.packs`) — reusable validators and
  scoring evaluators.
- **006** Human review (`loopplane.review`) — human-review workflows over the
  approval boundary.
- **007** Memory recall & knowledge (`loopplane.recall`) — recall and knowledge
  indexing as loop-aware context sources.
- **008** Advanced tool gateway (`loopplane.toolkit`) — tool discovery, registry,
  packages, manifests, versioning, and diagnostics.
- **009** Sandbox, policy & governance (`loopplane.governance`) — sandbox, path,
  permission, budget, quota, and cost policies.
- **010** Observability & debug (`loopplane.inspect`) — read-only trace, timeline,
  replay, and diagnostics data contracts.
- **011** Web/API host (`loopplane.webapi`) — the web/API host transport.
- **012** Desktop/studio host (`loopplane.studio`) — the local desktop/studio host.
- **013** Multi-agent orchestration (`loopplane.orchestration`) — subagents, a
  coordinator, delegation, and aggregated event/artifact views.
- **014** Release packaging & docs — packaging metadata, a single-source version, a
  PEP 561 `py.typed` marker, the public API reference, the getting-started guide,
  docs and examples indexes, this changelog, the release-readiness checklist, and
  CI build verification.
- **020** Model-provider adapters (`loopplane.adapters.anthropic`,
  `loopplane.adapters.openai`) — real Anthropic and OpenAI adapters implementing the
  model boundary, each behind its own optional extra (`anthropic`, `openai`), with
  duck-typed stream mapping, offline stub-based tests, and an opt-in live check.
- **021** Checkpoint store backends — the checkpoint store is now a `CheckpointStore`
  interface (Protocol) with two interchangeable implementations: `FileCheckpointStore`
  (the unchanged default) and an optional `SqliteCheckpointStore` (standard-library
  `sqlite3`, no new dependency), selected via `StorageConfig(checkpoint_backend=...)`.
  Multi-user/`principal_id` and a networked database remain deferred.
- **022** Web principal authentication & per-principal session scoping
  (`loopplane.webapi`) — the web/API auth boundary now identifies the caller (a
  `Principal`) instead of only admitting/denying, and every session is scoped to the
  principal that opened it (the listing is filtered; a non-owner gets a `404`). The owner
  is recorded in the checkpoint metadata (`principal_id`) so scoping survives restarts,
  and a reference `token_authenticator` ships for dev/tests. **Breaking:** the web/API
  `Authenticator` return type changes from a bool to `Principal | None` (the unit-011
  web/API surface; embedders with a boolean verifier must return a principal or `None`).
  No new runtime dependency; the runtime core is unchanged.
- **023** Web frontend login UI (`apps/web`) — a login screen captures an access token and
  gates the single-page app over the unit-022 secured backend: the token is sent as a
  bearer credential, persisted in `sessionStorage` (cleared on tab close), and cleared on
  logout or an authorization failure (a 401 returns the user to login). Frontend only; the
  runtime and the existing unit-018 app are unchanged.
- **024** Desktop packaging (`apps/desktop`) — the Electron app can be packaged into a
  distributable installer that bundles a **PyInstaller-frozen** sidecar, so an end-user
  needs no system Python: a freeze spec, an electron-builder config, and a unit-tested
  spawn resolver that runs the bundled frozen sidecar in a packaged app and
  `python bridge.py` in development. Desktop-only; the runtime is unchanged; producing and
  signing the per-OS installer is a reserved manual / CI step.
- **025** Web agent UI (`apps/web`) — a frontend-only visual + UX overhaul of the
  single-page app into a modern agent UI: a two-pane shell (sessions sidebar + a chat
  column with a sticky header and composer), assistant **markdown** rendering (safe — no
  raw HTML), inline **collapsible tool cards** (running -> success/failure), styled
  approval/question dialogs, a run-status indicator + a **Stop** control, a non-blocking
  error banner, auto-scroll with jump-to-latest, a **light/dark theme** (persisted, system
  default), and a restyled login. The reducer now folds events into one **ordered entry
  list** so tool cards interleave with messages. Reuses the api layer + the unit-023 auth
  gate unchanged; no backend change.
- **026** Web agent signals (`apps/web`) — a frontend-only extension that surfaces three signals
  the backend **already emits** but the UI ignored: a distinct, de-emphasized, **collapsible
  thinking block** (`assistant-reasoning-increment`), **selectable question options** with a
  free-text fallback (the question payload's `text` + `options`; corrects the unit-018 `prompt`
  mis-mapping), and a **per-turn + session token-usage** indicator (`turn-completed`). Each
  degrades gracefully when its data is absent. No backend change.
- **027** Web agent inspection panels (`loopplane.host` / `loopplane.webapi` + `apps/web`) —
  additive, read-only, metadata-only inspection of the agent's capabilities/context: four
  `GET /v1/inspect/{skills,tools,mcp,memory}` endpoints (auth-gated) backed by `LoopPlaneHost`
  query methods that compose the existing skills / gateway / MCP / memory layers, rendered as a
  tabbed inspection panel in the web UI. MCP servers are derived from the `external-server:`
  descriptor source (never the config's args/url); no tool is executed and no state is mutated
  (the Tool Gateway and the Event Bus are untouched). No ADR.
- **028** Web agent model selection & file attachments (`loopplane.webapi` / `loopplane.host` +
  `apps/web`) — additive, web/API-layer, **no ADR**. A model catalog (`GET /v1/models`) of
  pre-configured single-model hosts sharing the unit-021 checkpoint root; runs/sessions accept a
  `model` id routed to the chosen host (one model per run). An upload endpoint
  (`POST /v1/uploads`, auth-gated, per-principal, size-limited) + a per-reference `UploadStore` +
  a `read_upload` Tool Gateway tool (`loopplane.host.upload_tool`) the agent calls to read a file
  on demand — transient input by id, never embedded into the content model. The composer gains a
  model selector + file attachments. The runtime, content model, Tool Gateway, and Event Bus are
  unchanged.
- **029** Web agent parity extras (`apps/web`) — frontend-only polish, no backend, no ADR:
  **i18n** (an in-house `t()` over en + zh-TW string maps, an `I18nProvider` persisting the choice,
  a `LanguageSwitcher`, with an English fallback; UI chrome localized, assistant content
  untranslated); **code syntax highlighting** (`rehype-highlight` on the unit-025 markdown, with
  theme-bound tokens + a plain fallback); a composer **command palette** (a `/` toggle-inspection
  command + `@skill`/`@tool` autocomplete from the unit-027 inspection data; backend-semantic
  commands out of scope); and a **client-side cost estimate** (the unit-026 usage × a bundled price
  table for the unit-028 model, clearly labeled an estimate, graceful when no price). Each degrades
  gracefully; the backend is untouched. With 029, the web-UI extension (025–029) is complete.
- **030** Web session management (`loopplane.checkpoint` / `loopplane.controller` / `loopplane.host` /
  `loopplane.webapi` + `apps/web`) — additive, **no ADR**, the first unit of the product-polish sprint
  (030–032). Sessions can be **renamed** and **deleted**, and the sidebar shows **titles** (not raw
  ids) grouped by recency. `CheckpointStore` gains `set_title` (append a fresh session-meta; the latest
  title wins in the listing and on rebuild) and `delete_session` (real removal), on both the file and
  SQLite backends; `RuntimeController` / `LoopPlaneHost` delegate (working with or without a checkpoint
  store). The web/API host adds owner-scoped `PATCH` / `DELETE /v1/sessions/{id}` (a non-owner → 404),
  and `SessionSummaryView` gains `last_active_at` / `created_at`. The frontend sidebar renders titles +
  Today / Yesterday / Earlier groups with a per-session rename/delete menu, and deleting the open
  session returns to an empty state. The Tool Gateway, Event Bus, and content model are unchanged.
- **031** Web message actions (`apps/web`) — frontend-only, no backend, no ADR. Each message gains
  **copy** + **regenerate** actions, and fenced code blocks gain a **copy button**: a `lib/clipboard`
  helper (the async Clipboard API + an `execCommand` fallback, never throwing); per-message Copy +
  Regenerate in `MessageList` (Regenerate sits on the latest assistant message, is disabled while a
  run is in flight, and re-runs the last user turn via the existing send path); and a code-block copy
  button via react-markdown's `pre` override (the unit-029 highlighting is unchanged). Second unit of
  the product-polish sprint (030–032); the backend is untouched.
- **032** Web interaction resilience & states (`apps/web`) — frontend-only, no backend, no ADR, the
  final unit of the product-polish sprint (030–032). The approval/question dialogs become **true
  modals** (a `Modal` wrapper + a `useFocusTrap` hook — backdrop, focus trap, Esc resolving to the
  safe default, keyboard-navigable options, focus restored on close); the connection-error banner
  gains a **Retry** that re-establishes the stream; a small **toast** system surfaces transient
  outcomes (rename / delete); and the UI gains **loading skeletons**, a **richer empty state**, and
  **first-run example prompts**. With 032, the product-polish sprint (030–032) is complete; the
  backend is untouched throughout (only unit 030 was additive backend, no ADR).
- **033** File-tool parity (`loopplane.tools`) — three additive baseline tools on the Internal
  Tool Adapter, reachable only through the Gateway and confined to the run working scope:
  `edit_file` (surgical unique-string replacement reusing the `write_file` stale-write guard),
  `glob_files` (filename pattern matching), and `grep` (regex content search with
  `content` / `files_with_matches` / `count` output modes). `search_files` is unchanged; no new
  dependency, no frontend, no ADR. First unit of the Tier-1 agent-capability sprint (033–036).
- **034** Web tools (`loopplane.tools` / `loopplane.governance` / `loopplane.host`) — two additive
  **NETWORK** tools on a new Web Tool Adapter, reachable only through the Gateway: `web_fetch`
  (fetch an http(s) URL to readable text, with a per-session in-memory cache) and `web_search` (run
  a query through a **host-injected** `SearchProvider` — LoopPlane bundles **no API key** and **no
  provider**; unconfigured → a clear normalized error, never a crash). Network egress is gated by an
  additive `ToolDescriptor.network` flag (default `False`; only the two web tools set it) and a
  `network_policy` decider that **denies network-flagged tools unless the host opts in**
  (default-deny / opt-in via `RuntimeConfig.allow_network`), composed through the **existing**
  decide-stage combinators (`safe_failure(all_of(...))` — deny-wins + fail-closed) in
  `_build_decider` — **no new gateway stage**. Every failure (bad/non-http(s) URL, timeout,
  transport error, missing `httpx`, raising provider) is a normalized `ErrorOutput` with no leaked
  secret/transport internal (V, VII). `httpx` is promoted to a declared **optional extra** (`net`),
  imported lazily; the core install gains no required dependency. Deterministic offline tests
  (mocked transport + stub provider) plus an opt-in, secret-gated live fetch; existing tools /
  descriptors / policies unchanged. No frontend, no ADR. Second unit of the Tier-1
  agent-capability sprint (033–036).
- **035** OpenAI-compatible providers (`loopplane.adapters.openai_compat`) — two additive model
  providers that **reuse** the unit-020 `OpenAIModel` + chat-completions mapping unchanged, differing
  only in the client `base_url`: `openrouter_model` (OpenRouter — brokers 100+ models incl.
  Claude/Gemini/Llama behind the OpenAI wire format, injected key) and `ollama_model` (a local
  Ollama endpoint, no key — placeholder + overridable `base_url`). No new dependency (rides the
  existing `openai` extra; the SDK is imported lazily), so the package imports without it and is
  tested offline (a fake `openai` module asserts the base_url / key wiring). They register as model
  hosts like the OpenAI host, so the existing `/v1/models` selector lists them with no frontend
  change. **Native Gemini (direct Google API) is deferred** to a follow-up — reachable via
  OpenRouter today. Third unit of the Tier-1 agent-capability sprint (033–036).
- **036** Multimodal input (`loopplane.model` / `loopplane.adapters.{anthropic,openai,openai_compat}` /
  `loopplane.host` / `loopplane.webapi`) — image input end-to-end, settled by the repository's first
  ADR (`docs/adr/0001-multimodal-content.md`). Image content was already modeled and contract-safe
  (`ImageBlock` is in `ContentBlock`/`OutputBlock`, round-trips through the event schema, and maps to
  Anthropic/OpenAI — OpenRouter/Ollama inherit via the OpenAI mapping), so **the content model and the
  event schema are UNCHANGED** (no `SCHEMA_VERSION` bump; ADR D1). The unit wires the existing upload
  path (028) into the model at the web edge: an optional `RunRequest.uploads` (`UploadRef`) whose image
  uploads become **leading `ImageBlock`s** on the user message (a pure `webapi.multimodal.assemble_blocks`
  helper; image-type sniffing in `webapi.uploads.image_media_type`; non-image uploads stay
  `read_upload`-readable, 028). **Provider capability negotiation** is an additive, duck-typed
  `loopplane.model.accepts_media(model)` probe (the `ModelBoundary` Protocol is unchanged — not a new
  required method; ADR D5) + an `accepts_media` flag on `AnthropicConfig`/`OpenAIConfig` (default `True`)
  and the `openrouter_model` (default `True`) / `ollama_model` (default `False`) constructors; the
  web/API layer (which owns model selection, 028) rejects an image sent to a text-only model with a
  clear normalized error (HTTP 400) and `/v1/models` advertises `accepts_media` per model. A media size
  cap rejects an oversized image at the conversion point (HTTP 413; ADR D6). The content vocabulary for
  building multimodal input (`Prompt`, `ContentBlock`, `TextBlock`, `ImageBlock`) is exposed through the
  `loopplane.host` seam. **PDF (a `DocumentBlock`) is deferred** — it does not map through OpenAI
  chat-completions and would pull in binary artifact durability + a non-text gateway handoff (the ADR's
  recommended follow-up, D2/D3/D4); the artifact store and the Tool Gateway are **unchanged**. Native
  Gemini remains a separate deferred 035 follow-up. Deterministic offline tests (a scripted/recording
  model + an in-process client + a real PNG); the event serde round-trip now asserts an
  `ImageBlock`-bearing `UserInputEvent` is lossless (Constitution VI). No new dependency, no frontend.
  Fourth and final unit of the Tier-1 agent-capability sprint (033–036).
- **037** Native Google Gemini adapter (`loopplane.adapters.gemini`) — the deferred 035 follow-up: a
  **native** model-provider adapter (`GeminiModel` + `GeminiConfig`) over the **direct** Google GenAI
  API (the official `google-genai` SDK, behind a new optional `gemini` extra), distinct from the
  OpenAI-compatible OpenRouter path. Mirrors the unit-020 adapters exactly — the SDK is imported
  **lazily** inside the client factory (so the package imports without the extra), the stream is mapped
  by **duck-typing**, and the whole adapter is tested **offline with a stub client**. `gemini/mapping.py`
  maps the loop's content/tools to Gemini's `contents`/`function_declarations`/`inline_data` and decodes
  the chunk stream (`candidates[].content.parts` → text / thought→`ReasoningIncrement` / `function_call`
  →raw `ToolCallRequest`; `usage_metadata`→`TokenUsage`; one `TurnEnd`); a context-overflow signal →
  `ContextOverflowError`, every other fault → a public-safe `ModelProviderError` (no key/raw-body leak,
  reusing the shared `_model_errors`). It advertises `accepts_media()` (default `True`; Gemini is
  vision-capable — an `ImageBlock` → an `inline_data` part) and registers as a `/v1/models` host like
  the others, so the existing selector lists it with **no frontend change**. **The shared content model
  and the event schema are UNCHANGED** (no new `ToolCallBlock` field, **no `SCHEMA_VERSION` bump**, **no
  ADR**): Gemini 3 hard-requires a per-`function_call` `thought_signature` for multi-turn tool use, but
  Google's official `"skip_thought_signature_validator"` sentinel skips validation, so multi-turn tool
  use is made functional by attaching that sentinel when re-mapping a prior `ToolCallBlock` (on the part
  only — never in the `args` the gateway validates) rather than carrying a signature in the model.
  Preserving the *real* per-call signature (best cross-turn reasoning continuity) is a documented
  deferred follow-up (it would need a content-model field — a Constitution VI / ADR matter). Tool calls
  surface **raw** for the gateway (V); only normalized increments reach the loop (VI); the SDK enters
  only as a model-boundary adapter (VIII). New optional extra `gemini` (`google-genai>=1`); **no
  required** runtime dependency. Deterministic offline tests (a Gemini-shaped stub: request mapping +
  stream decoding + a tool round-trip; the shared parametrized overflow/failure/usage suites now
  exercise "gemini") + an opt-in, secret-gated live turn. The deferred follow-up from spec 035 (research
  Decision 2) and ADR 0001 (Follow-up #3).
- **038** Plan mode (`loopplane.governance` / `loopplane.context` / `loopplane.tools` /
  `loopplane.host` / `loopplane.controller`) — a LoopPlane-native **plan mode** (read-only
  investigation → human approval → execute), additive and **no ADR**, the **first Tier-2
  unit** (agentic workflow depth). A `plan_mode_policy` decide-stage decider denies any
  tool whose `ToolDescriptor.read_only` is `False` while plan mode is active, **except** a
  small allowlist (`ask_user`, `exit_plan_mode`) that must stay usable to make and submit a
  plan; read-only tools stay allowed; a **no-op** when inactive. It is composed through the
  **existing** decide-stage combinators (`safe_failure(all_of(...))` — deny-wins +
  fail-closed) in `_build_decider` — **no new gateway stage** (V). Plan-mode activity is a
  minimal per-run holder `PlanModeState(active)` carried on an additive
  `RunContext.plan_mode` field: the **single sharing channel** between the decider (which
  reads it) and a new **`exit_plan_mode`** Internal Tool Adapter tool (which flips it on
  approval) — both receive the **same** per-run `RunContext`, so no process-global state.
  `exit_plan_mode` (input `plan`, `read_only=False`, allowlisted) submits the plan for a
  human decision by **reusing the existing human round-trip** (`InteractionBroker.ask_question`,
  the same path `ask_user` uses): on **approve** it clears plan mode (subsequent non-read-only
  tools become allowed) and returns success; on **reject / no human** it leaves plan mode
  active and returns a normalized outcome — never a raised exception across the boundary (V).
  Entering plan mode is an additive, default-off `RuntimeConfig.plan_mode` flag wired through
  the controller (one additive constructor kwarg + the per-run `drive()` line — the **only**
  per-run wiring; the core agent loop / turn cycle is untouched). **No event-schema change**
  (the round-trip reuses the existing question/answer events; no `SCHEMA_VERSION` bump, VI);
  every existing tool, descriptor, and policy is unchanged. Deterministic offline tests (a
  scripted `InteractionBroker`; the governance + internal-tool harnesses). First unit of the
  Tier-2 (agentic workflow depth) line.

[0.1.0]: https://github.com/norton77930/loopplane/releases/tag/v0.1.0
