# Changelog

All notable changes to LoopPlane are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
Semantic Versioning.

## [Unreleased]

Twelve additive units (064–075) extending the v0.4.0 platform line toward cost
transparency, richer host UX, document-capable model content, platform hardening, and web
parity. The cost-governance arc gains **queryable spend** (064) and a **pre-turn
predictive cost guard** (068); host UX gains **backend-semantic slash commands** (065) and
**named permission modes** (066); the content model gains **document / PDF input** (069)
and Gemini **thought-signature round-trip** (070); the platform line gains **JWKS refresh
hardening** (067), a **durable event replay store** (071), and **per-tenant platform
fairness** (072); a **code-review remediation** pass hardened CI and public-safety seams
(073); and the web app reaches **live-channel parity** (074) and **first-class capability
management** (075). Every unit is additive and default-off where configurable; the runtime
core and the event schema are unchanged (no `SCHEMA_VERSION` bump), and the only
content-model changes are the additive extensions recorded in ADR 0011. Four ADRs recorded
the boundary decisions: **0011** (DocumentBlock content model, units 069–070), **0012**
(durable event replay store), **0013** (platform fairness), **0014** (pre-turn cost
guard).

### Added

- **064** Cost surfacing (`loopplane.webapi`) — owner-scoped, read-only cost queries:
  `GET /v1/sessions/{id}/cost` and `GET /v1/cost/monthly`, host passthroughs
  (`session_cost`, `monthly_spend`), and a `BudgetChecker.session_spent` accessor, so a
  host/UI can see accumulated USD before a `budget-exceeded` termination (the 053/062
  tail of G21/G22).
- **065** Backend-semantic slash commands (`loopplane.commands`) — `/cost`, `/model`,
  `/memory`, and `/compact` answered by the host (CLI REPL interception plus
  `POST /v1/commands`) without a model round-trip, via a fail-safe `CommandRegistry`;
  commands are host UX and do not pass through the Tool Gateway or Event Bus (gap G14).
- **066** Named permission modes (`loopplane.governance`) — a single
  `RuntimeConfig.permission_mode` option (`acceptEdits` / `bypassPermissions` /
  `dontAsk` / `plan`) expanding to preset rule sets over the 039 permission DSL
  (`PERMISSION_MODES`, `permission_mode_ruleset`); deny-wins is preserved and the default
  (`None`) is byte-identical (gap G10).
- **067** JWKS refresh hardening (`loopplane.webapi`, `loopplane[oauth]`) — a bounded
  negative-kid cache, a cross-request refresh throttle
  (`jwt_authenticator(refresh_min_interval=…)`), and single-flight refresh so an
  unknown-kid spray cannot amplify JWKS fetches against the upstream IdP (056 follow-up).
- **068** Pre-turn cost guard (`loopplane.budget`) — estimate a turn's cost before the
  model call (`estimate_request_tokens` plus a configurable
  `RuntimeConfig.pre_turn_max_output_tokens` output bound) and refuse a likely-overage
  turn, reusing the existing `budget-exceeded` reason; default-off and fail-open
  (ADR 0014, extends ADR 0005).
- **069** Document block (`loopplane.model`) — PDF / document input as a new
  `DocumentBlock` content type with native Anthropic and Gemini mappings; adapters
  without document support fail safely before provider submission instead of guessing a
  conversion (gap G24; ADR 0011).
- **070** Gemini thought-signature round-trip (`loopplane.model`,
  `loopplane.adapters.gemini`) — an optional, absent-by-default `provider_signature` on
  tool-call content so native Gemini multi-turn tool use preserves and replays per-call
  `thought_signature` instead of relying on the validator-skip sentinel (037 tail;
  ADR 0011).
- **071** Durable event replay store (`loopplane.webapi`) — an `EventReplayStore`
  protocol keyed by `(session_id, sequence)` with File / SQLite / Postgres backends, so
  `Last-Event-ID` SSE reconnects survive process restarts and multi-worker deployments;
  opt-in — the 058 in-memory ring remains the default (G23 tail; ADR 0012).
- **072** Platform fairness (`loopplane.fairness`) — per-tenant quota and fair in-process
  scheduling of model-call capacity above the 061 per-principal host pool; over-quota
  requests receive a public-safe 429 / SSE rejection; default-off, in-process slice only
  (G20 tail; ADR 0013, extends ADR 0009).
- **073** Code-review remediation — remediation of the 001–072 code review: locked
  `uv sync` / desktop CI gates with `apps/web/**` path coverage, normalized public-safe
  MCP / `web_fetch` errors, `web_fetch` response and cache size limits, and a Spec Kit
  task-drift audit; no runtime schema, event, or public-API change.
- **074** Web parity foundation (`loopplane.webapi` + `apps/web`) — an additive WebSocket
  live channel (bidirectional assistant output / tool progress / approval / abort, with
  reconnect replay) beside the existing REST + SSE contract, backend-owned contract
  fixtures generating a deterministic `generated.ts`, and modern session management
  (draft sessions, model preference, star / fork / search / bulk-delete).
- **075** Web capability management (`loopplane.webapi` + `apps/web`) — first-class
  management of memory, skills (including import), MCP configuration,
  projects / workspaces, schedules, and model defaults from the web UI over new
  owner-scoped `/v1/capabilities/*` routes, extending the 027 read-only inspection into a
  read-write settings surface; the browser still never collects provider credentials.

## [0.4.0] - 2026-06-21

The capability-to-platform line — twenty additive units (044–063) closing the gap-analysis
backlog and growing LoopPlane from a single-tenant harness toward a multi-tenant platform.
Tier-1 agent capabilities (todo, structured output, notebook edit, a keyless search
provider), Tier-2 autonomy (background tasks, scheduling, agent messaging/swarm, worktree
isolation), Tier-3 execution-safety & cost (sandboxed `run_command`, pricing, file undo),
and the headline **G22 cost-governance + Tier-4 platform** arc: per-message/session and
**durable per-user-monthly USD budget caps**, an **OAuth/JWT verifier**, **SSE + WebSocket
MCP transports** and **MCP resources**, **resumable SSE reconnect**, a **PostgreSQL
checkpoint backend**, **per-principal concurrency**, and the **durable USD ledger**. Every
unit is additive, default-off, and byte-identical when unconfigured — the runtime core, the
content model, and the event schema are unchanged (no `SCHEMA_VERSION` bump). Nine ADRs
recorded the boundary decisions: **0002** (background execution), **0003** (agent
messaging), **0004** (command-execution isolation), **0005** (USD budget enforcement),
**0006** (resumable SSE), **0007** (MCP resources), **0008** (Postgres checkpoint —
sync thread-bridge), **0009** (per-principal host pool), **0010** (durable USD ledger +
monthly cap). Two new optional extras: `loopplane[oauth]` and `loopplane[postgres]`.

### Added

- **044** Agent todo tool (`loopplane.tools`) — a `todo_write` Internal-Tool-Adapter tool
  (set-the-whole-list, per-session, metadata-only) for tracking multi-step work (gap G1).
- **045** Native structured output (`loopplane.model`) — model-native `response_format` /
  JSON-schema constrained output where the provider supports it (gap G3).
- **046** Notebook edit (`loopplane.tools`) — a `notebook_edit` tool for Jupyter cells (gap G2).
- **047** Reference search provider (`loopplane.tools`) — a bundled keyless `web_search`
  provider so `web_search` works out of the box (gap G4).
- **048** Background tasks (`loopplane.tools`) — agent-facing create/get/list/stop/output
  for long-running work; a per-run supervisor (Tier-2 autonomy; **ADR 0002**).
- **049** Agent scheduling (`loopplane.tools`) — agent-facing create/get/list/cancel that
  wraps the in-process scheduler to fire child runs (Tier-2).
- **050** Agent messaging & swarm (`loopplane.tools`) — dispatch + a per-member message
  inbox over a separate registry (messages are NOT events; Tier-2; **ADR 0003**).
- **051** Worktree isolation (`loopplane.tools`) — an opt-in per-task git worktree
  (default-off; public-safe relative paths; shielded teardown; Tier-2).
- **052** Sandboxed command execution (`loopplane.tools`) — an injectable `CommandExecutor`
  seam; a POSIX `LocalJailCommandExecutor` (rlimits + env-scrub + a wall-clock timeout);
  default = the verbatim host executor (byte-identical); Windows → `ConfigError` (Tier-3
  G11; **ADR 0004**).
- **053** Server-side pricing (`loopplane.pricing`) — a pure `PricingTable.cost`
  (`TokenUsage → USD` Decimal), unwired by default (Tier-3 G21 Phase A).
- **054** File undo (`loopplane.tools`) — an `undo_file` tool over per-session pre-edit
  snapshots (Tier-3 G16).
- **055** USD budget caps (`loopplane.budget`) — in-loop per-message / per-session USD
  enforcement (reusing 053's pricing) that terminates a run with a new `budget-exceeded`
  `TerminationReason` (additive within the schema version; **no `SCHEMA_VERSION` bump**);
  stop-after-overage; fail-soft on an unpriced model; default-off (G22 Phase B; **ADR 0005**).
- **056** OAuth/JWT verifier (`loopplane.webapi`) — a host-supplied `jwt_authenticator`
  behind the unit-022 `Authenticator` seam (JWKS + iss/aud/exp/nbf, pinned asymmetric algs,
  claim → `Principal`), behind a new import-guarded `loopplane[oauth]` extra; default
  `DENY_ALL` unchanged (Tier-4 G18).
- **057** MCP SSE + WebSocket transports (`loopplane.adapters.mcp`) — two additional client
  transports alongside stdio + http, reusing the SDK's vendored clients; no new dependency
  (Tier-4 G12 A/B).
- **058** Resumable SSE (`loopplane.webapi`) — a bounded per-session ring buffer + an SSE
  `id:` line (the event sequence) + `Last-Event-ID` replay (merge-based, deduped); default-off
  byte-identical; in-memory variant (Tier-4 G23; **ADR 0006**).
- **059** MCP resources + host-token auth (`loopplane.adapters.mcp`) — resources surfaced as
  Gateway-routed synthetic tools (returning existing `TextBlock`/`ImageBlock`; no new content
  type) + a config-supplied `Authorization: Bearer` token on http/sse (Tier-4 G12 C/D;
  **ADR 0007**).
- **060** PostgreSQL checkpoint backend (`loopplane.checkpoint`) — a third `CheckpointStore`
  reusing `records.py` behind a new import-guarded `loopplane[postgres]` extra; the sync
  `CheckpointStore` Protocol + File/SQLite backends are unchanged (the sync thread-bridge);
  default backend stays File/SQLite (Tier-4 G19; **ADR 0008**).
- **061** Per-principal host pool (`loopplane.webapi`) — an optional `TenantHostPool` above
  the host so different principals run concurrently while each principal's host keeps its
  sequential invariant; per-principal in-flight caps; default single-host byte-identical
  (Tier-4 G20-A, the additive isolation slice; **ADR 0009**).
- **062** Durable USD ledger (`loopplane.ledger`) — a new package: a `UsdLedger` Protocol
  keyed by `(principal_id, month)` with an atomic cross-session increment, + File/SQLite/
  Postgres backends (Postgres `ON CONFLICT … RETURNING` is the cross-process-safe path; exact
  `Decimal`); pure storage (G22 Phase C; **ADR 0010**).
- **063** Per-user-monthly USD cap (`loopplane.budget`) — extends 055's `BudgetChecker` with
  an optional monthly dimension over 062's ledger (`record_turn` async; reuses the
  `budget-exceeded` reason — no `SCHEMA_VERSION` bump); fail-open on a ledger outage;
  enforced on create + resume; default-off byte-identical (G22 Phase C; **ADR 0010**).

## [0.3.0] - 2026-06-19

Two additive follow-on units after the 0.2.0 agent-capability line: a **FAIL-SAFE**
optional cheap-model compaction summarizer (042, Tier-3 efficiency) and **model-driven
one-shot subagent spawning** (043, Tier-2 autonomy). Both are additive and reuse-first —
the runtime core, the agent loop, the content model, and the event schema are unchanged
(no `SCHEMA_VERSION` bump).

### Added

- **042** Optional cheap-model compaction summarizer (`loopplane.loop`) — an additive,
  default-`None` `RuntimeConfig.compaction_summarizer: ModelBoundary | None`. When set, a
  **FAIL-SAFE** async overlay asks it to summarize the just-dropped span into the existing
  `SummaryMarkerBlock`; **any** failure (exception, `ContextOverflowError`, an
  `anyio.fail_after` timeout, or empty output) falls back to the mechanical `compact_history`,
  so a run is never broken. Default `None` is byte-identical; the loop turn-cycle,
  `compact_history`, the content model, and the event schema are unchanged. Committed after
  the v0.2.0 tag (ships in the next release).
- **043** Model-driven one-shot subagents (`loopplane.tools` / `loopplane.context` / `loopplane.host`) —
  an additive, opt-in `spawn_subagent` **Tool-Gateway** tool (a new `SpawnSubagentAdapter`) that lets the
  model delegate a focused sub-task: it runs **one** bounded child agent through the **existing** Phase-3
  `loopplane.engineering.run_loop` (the same seam unit-013's host-driven coordinator composes — **no
  agent-loop, orchestration-core, gateway-pipeline, or event-schema change**) and returns the child's
  **final assistant text** to the parent. SAFE under a **hard recursion-depth cap**: an additive
  `RunContext.subagent_depth` (default 0; a child runs at parent + 1) and a configurable
  `RuntimeConfig.max_subagent_depth` (default `1`); the tool **DENIES** a spawn (a normalized error, **no**
  child run started) once `subagent_depth >= max_subagent_depth`, so subagents cannot nest without bound
  (default `max_subagent_depth = 0` registers **no** tool — feature off, byte-identical to today; a host
  sets it to `1` to enable exactly one level). A failing /
  over-running / empty-answer child is **contained** (a normalized, public-safe error to the parent — never
  a raw exception; the parent run continues), mirroring the 013 fail-safe coordinator. The child's events
  are **captured** (driven with no live sink) and surfaced only as metadata-only aggregation (reusing 013's
  `aggregate_events`) — never re-emitted onto the parent's live bus (VI). An optional `allowed_tools`
  restricts the child to a least-privilege subset of the parent's tools. Enforced at the Gateway (V); no new
  dependency, no frontend, no ADR. A Tier-2 autonomy unit. Agent-to-agent messaging, swarm / peer
  coordination, and persistent / named / background subagents are deferred.

## [0.2.0] - 2026-06-19

The agent-capability line: a single, additive sprint that grows what a LoopPlane
agent can do — Tier-1 capabilities (033 file tools, 034 web tools + network
governance, 035 OpenAI-compatible providers, 036 multimodal image input settled by
the project's first ADR, 037 native Gemini), Tier-2 workflow depth (038 plan mode,
039 a declarative permission rule DSL), and Tier-3 cost/efficiency (040 Anthropic
prompt caching, 041 configurable auto-compaction). Every unit is additive and
reuse-first: the runtime core, the content model, and the event schema are
unchanged (no `SCHEMA_VERSION` bump).

### Added

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
- **039** Declarative permission rule DSL (`loopplane.governance` / `loopplane.host`) — a
  **host-suppliable** declarative permission rule set enforced at the Tool Gateway decide
  stage, additive and **no ADR**. A host supplies an ordered `PermissionRuleSet`: each
  `PermissionRuleSpec` names a `tool` (an exact name or an `fnmatch` pattern in the **existing**
  matcher syntax, e.g. `mcp:*`), an optional `match` (a map of input-field → pattern: a
  **path-glob** for path-shaped fields — `path`/`file`/`*_path` — a **regex** otherwise, e.g.
  `{command: "^rm -rf"}`), and a `decision` of `allow` | `deny` | `ask`; a top-level `default`
  applies on no match. A `rule_dsl_policy` decide-stage decider selects the rules whose `tool`
  matcher **and** every `match` pattern match the call (`call.tool_name` + the string form of
  `call.input` fields), combines them **deny-wins** (deny > ask > allow — reusing
  `resolve_rules`' deny-wins for the name dimension), falls back to `default`, and returns the
  **existing** `PolicyVerdict`: `allow` → `PolicyAllow`, `deny` → `PolicyDeny`, **`ask` reuses
  the existing approval round-trip** (`InteractionBroker.request_approval`, the same path the
  Human Approval boundary uses) and maps the human's resolution to allow/deny — **no new
  verdict type, no new approval mechanism, no event-schema change** (the verdict model is
  binary — `PolicyAllow | PolicyDeny`; there is no `PolicyAsk`). It is composed through the
  **existing** decide-stage combinators (`safe_failure(all_of(...))` — deny-wins + fail-closed)
  in `_build_decider` — **no new gateway stage** (V). `match` regexes / path-globs are
  **compiled eagerly at construction**, so a malformed pattern is a clear config error there
  (fail-closed), never a silently-allowed call at decide time. The rules are an additive,
  default-empty, public-safe `RuntimeConfig.permission_rules` field (a tool name + patterns +
  a decision; **no secret**), coerced from a plain mapping in `from_mapping`; absent/empty →
  no DSL policy installed and existing runs are **byte-identical**. No per-run/controller
  change (`ask` reads the per-run `RunContext` the Gateway already hands the decider); every
  existing tool, descriptor, policy, and the approval boundary are unchanged. Deterministic
  offline tests (the governance helpers; a scripted `InteractionBroker` for the `ask`
  round-trip; additive assembly-wiring tests). A Tier-2 governance unit.
- **040** Anthropic prompt caching (`loopplane.adapters.anthropic`) — explicit
  prompt-cache breakpoints so repeated agent-loop turns re-read a stable request
  prefix at ~0.1x input price instead of full price; additive, reuse-first, **no
  ADR**, the **first Tier-3 (cost/efficiency) unit**. A pure, opt-in overlay
  `apply_prompt_caching(messages, tools)` in `anthropic/mapping.py` attaches
  `cache_control: {"type": "ephemeral"}` to the **stable prefix only** — the last
  tool definition (the end of the stable tools segment, which renders first) and
  the last content block of the **first** message (a stable leading-history
  prefix, gated on ≥2 messages so it is **never** the rolling tail) — emitting at
  most 2 of the Anthropic-max 4 breakpoints. A new additive
  `AnthropicConfig.prompt_caching: bool` (default **True** — caching is a
  near-pure win for repeated turns) gates it; the adapter runs the overlay only
  when the toggle is on. When **off**, the assembled request is **byte-identical**
  to the pre-caching request (the overlay is not called; `build_messages` /
  `build_tools` are unchanged, so the unit-020 mapping tests stay green and the
  off path is proven identical by a dedicated test). **Transparent to the loop**:
  caching changes only the provider request shape, not the loop's behavior or the
  normalized event stream — **no event-schema, content-model, or `TokenUsage`
  shape change** (caching is observed through the existing
  `TokenUsage.cached_tokens`, mapped from Anthropic's `cache_read_input_tokens`).
  **OpenAI / OpenRouter / Ollama caching is automatic** and needs **no request
  change** — the adapter sends no cache parameter and
  `prompt_tokens_details.cached_tokens` is already mapped to
  `TokenUsage.cached_tokens` by the existing stream decoder (confirmed + a focused
  test); Gemini's implicit caching is likewise provider-managed and out of scope.
  No new public package / `__all__` name (the toggle is a field on
  `AnthropicConfig`; the helper is a non-exported module function), so the
  unit-014 api-reference bijection stays green with no doc edit. **No change to
  the loop, runtime core, Tool Gateway, or Event Bus.** Deterministic offline
  tests (breakpoint placement / 4-max / never-the-tail / off-path byte-identity /
  purity, plus the OpenAI `cached_tokens` confirmation); any live cache-savings
  observation is opt-in (`docs/real-model-validation.md` §5). Rollback:
  `prompt_caching=False`, or revert the helper + the one adapter call. The next
  Tier-3 follow-on is **041** (configurable compaction).
- **041** Configurable proactive auto-compaction (`loopplane.host` /
  `loopplane.loop` / `loopplane.controller`) — a second Tier-3 (efficiency) unit;
  additive, reuse-first, **no ADR**. LoopPlane's prompt assembler already runs a
  proactive pre-send compaction check at the model's **full** capacity (estimate
  the assembled context via the existing `chars ÷ 4` heuristic; when it exceeds
  `context_capacity()`, run the mechanical `compact_history` once before the model
  call), plus the loop's reactive `ContextOverflowError` compact-and-retry-once
  backstop. This unit makes that proactive trigger **configurable** via an
  additive, default-`None` `RuntimeConfig.auto_compact_threshold: float | None`.
  When `None` (the default), the check compares against the **full** capacity —
  the existing behavior, so the default-off path is **byte-identical** to today.
  When a fraction `f` in `(0, 1]` is set, the check compares against
  `f * context_capacity()`, so the **existing** `compact_history` runs earlier, on
  a safety margin, before the model's limit is reached. It **reuses
  `compact_history` unchanged** (the same mechanical `SummaryMarkerBlock` /
  `SummaryDigest` digest — no new algorithm) and **reuses the existing
  `_estimate_tokens` heuristic** (no tokenizer, no new dependency; the estimate is
  a margin trigger and the reactive overflow path stays the backstop if it
  under-counts). The threshold is threaded through the same wiring as `plan_mode`
  / `allow_network` (`RuntimeConfig` → `assemble()` → `RuntimeController` →
  per-session `PromptAssembler(compact_threshold=...)`), coerced in `from_mapping`,
  and **validated fail-fast** (a non-`None` value must be a finite number in
  `(0, 1]`, else `ConfigError`); it carries no secret. **Transparent to the loop
  and the event stream**: compaction emits **no** runtime event today (it mutates
  in-memory history only; the durable stream keeps the originals via
  `replace_prefix`) and the proactive path emits none either — **no event-schema
  change, no `SCHEMA_VERSION` bump, no content-model / `TokenUsage`-shape change,
  no change to the agent loop's turn cycle, the Tool Gateway, or the Event Bus**.
  No new public package / `__all__` name (the toggle is a field on the existing
  `RuntimeConfig`; the assembler/controller gain only constructor parameters), so
  the unit-014 api-reference bijection stays green with no doc edit. The
  **cheap-model summarizer** (an optional summarizer `ModelBoundary` used during
  compaction) is **deferred** to a documented follow-on (spec 042): folding a
  model call into the compaction path adds real complexity/risk for a secondary
  benefit, and the mechanical digest already frees space. Deterministic offline
  tests (the effective-capacity math; proactive compaction at/over/under the
  threshold incl. a same-history/same-capacity threshold-vs-`None` proof;
  default-`None` byte-identity — no compaction below full capacity, the existing
  full-capacity trigger preserved above it; the reactive backstop unchanged; the
  invalid-threshold `ConfigError`; the `from_mapping` round-trip + no-secret).
  Rollback: `auto_compact_threshold = None`, or revert the assembler/controller/
  config additions → exact pre-threshold behavior.

## [0.1.0] - 2026-06-18

The initial LoopPlane line: a spec-first, embeddable agent-harness runtime and its
additive layers (units 001-013), the hook and plugin extensibility (015-016), the
CLI / web / desktop hosts (017-019), real model providers, storage, auth, and
packaging (020-024), and the web-UI build-out (025-032) — all brought to release
quality by unit 014.

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
- **015** Lifecycle hook system (`loopplane.hooks`) — a hook registry plus eleven
  lifecycle points (pre/post tool use, prompt submit, session start/end, subagent
  start/stop, file changed, model stop) that let host and plugin code observe — and, at
  the two gating points (before-tool, prompt-submit), gate or modify — agent behavior
  without forking the runtime. In-process; honors the single Tool Gateway (V) and
  Runtime Event Bus (VI); fail-safe (a raising or unrecognized hook denies, never
  silently allows). Zero default behavior when no hook is registered.
- **016** Plugin system (`loopplane.plugins`) — a public-safe `plugin.json` manifest
  that bundles skills + namespaced MCP servers (`<plugin>__<server>`) + hooks into a
  discoverable, host-loadable unit; an enable-list gates loading (default none → zero
  default behavior). Loads through the existing skills, toolkit (008), and hook (015)
  seams with no new runtime coupling; a malformed manifest is skipped whole while the
  others still load.
- **017** CLI host (`loopplane.cli`) — a thin terminal host over the Host Application
  Interface (`loopplane.host`): an interactive REPL/chat loop, a one-shot `run` command,
  session list/resume when durable storage is configured, normalized-event rendering (no
  raw tracebacks), and an optional credential-gated real model behind a seam. Executes no
  tool itself (V) and consumes the normalized event stream (VI); adds a `loopplane`
  console entry point. Runtime core unchanged.
- **018** Web frontend (`apps/web`) — a from-scratch single-page UI over the unit-011
  web/API host (REST + SSE): live streamed chat, an event/run timeline, approval and
  question dialogs, and a session list. Written fresh with no private legacy UI (VII);
  the JS toolchain is isolated under `apps/` with its own CI gate (React + Vite +
  Vitest). No change to the Python runtime.
- **019** Desktop GUI (`apps/desktop`) — a local Electron desktop shell that embeds the
  unit-018 frontend and drives a local unit-012 studio sidecar over a bridge (no network
  server); approval/question round-trips go over the bridge; credential-free by default.
  Reuses unit-018 unchanged — launch and shell only; the runtime is unchanged.
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

[0.4.0]: https://github.com/norton77930/loopplane/releases/tag/v0.4.0
[0.3.0]: https://github.com/norton77930/loopplane/releases/tag/v0.3.0
[0.2.0]: https://github.com/norton77930/loopplane/releases/tag/v0.2.0
[0.1.0]: https://github.com/norton77930/loopplane/releases/tag/v0.1.0
