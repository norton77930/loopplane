# LoopPlane Capabilities

> A functional-scope overview of what LoopPlane provides today, derived from units 001–088
> and verified against the source tree. For per-unit status and the
> roadmap autopilot, see [`loopplane-agent-board.md`](loopplane-agent-board.md); for the
> comparison against reference agent harnesses and the forward roadmap, see
> [`gap-analysis.md`](gap-analysis.md); for release history, see
> [`../CHANGELOG.md`](../CHANGELOG.md).

## What LoopPlane is

LoopPlane is a **spec-first, embeddable agent-harness runtime**. It drives a
"model ↔ tools" conversation loop through a single normalized **Event Bus** and a unified
**Tool Gateway**, and extends outward into loop automation, governance, multi-provider
model support, agent-capability tools, and full CLI / web / desktop host surfaces.

Units 001–083 are released through **v0.5.0**. Units 084–088 are recorded in the
**Unreleased** section of [`../CHANGELOG.md`](../CHANGELOG.md).

Unit 087 adds explicitly selected tenant-weighted model-start scheduling through
`WeightedPlatformFairness`, with memory and isolated Postgres coordination. Weights
divide start opportunities across ready tenants without multiplying entitlement by
queue depth; active/consecutive caps remain hard. Coordinator outages fall back to
local fairness. This unit is not a release; current validation status is on the board.

Unit 088 adds an opt-in drain on one admission worker. The worker refuses new
runs, finishes the run it already holds, and a peer can then accept that person.
An in-progress turn does not move. This unit is not a release; current validation
status is on the board.

LoopPlane is built under a project constitution. The principles most visible in the
capability surface are:

- **Tool Gateway ownership (V)** — every tool resolve / authorize / execute / normalize
  flows through one chokepoint.
- **Event Bus ownership (VI)** — one normalized, versioned event stream is the only
  public observable; schema changes are versioned and tested.
- **Testable, reversible evolution (X)** — features are additive and default to
  byte-identical behavior (prompt caching, auto-compaction, dynamic subagents, the Tier-2
  autonomy supervisors, USD budget caps, the durable ledger, and the per-principal host
  pool are all opt-in / off by default).
- **Reference, not clone (IX)** — claude-code-like concepts may inform the architecture
  but are re-derived through LoopPlane's own specs.

## Functional scope, by layer

| Layer | Units | What it provides | Packages |
| ----- | ----- | ---------------- | -------- |
| **Runtime core** | 001, 002, 021, 060 | Agent loop (reason ↔ tool call ↔ result), unified Tool Gateway (internal + MCP), normalized Event Bus, durable checkpoint / resume (File + SQLite + Postgres), memory, skill execution profiles, human-approval boundary, artifact storage, and the Host Application Interface (declarative `RuntimeConfig` + single entry point). | `loopplane.{controller,gateway,events,loop,memory,artifacts,approval,skills,checkpoint,host}` |
| **Loop engineering & automation** | 003–006 | Loop Definition + Controller (validate → evaluate → stop / retry / repair / human-review), an in-process scheduler (manual / interval / condition triggers on an injectable clock), reusable validator / evaluator packs, and human-review workflows. | `loopplane.{engineering,scheduling,packs,review}` |
| **Knowledge, governance & observability** | 007–010 | Memory recall + knowledge index with an injection policy and retrieval budget; an advanced tool gateway (catalog / plugin bundles / capability manifest / versioning / diagnostics — discovery only, never execution); sandbox / policy deciders (permission / path / budget / quota / capability, deny-wins); and metadata-only observability (diagnostics / trace / timeline / replay). | `loopplane.{recall,toolkit,governance,inspect}` |
| **Multi-agent & autonomy** | 013, 043, 048–051 | Host-driven orchestration (agent registry + coordinator + aggregated event / artifact views) and model-driven one-shot subagents (`spawn_subagent`, with a hard recursion-depth cap and failure containment); plus the Tier-2 autonomy supervisors — background / long-running tasks (048), agent-facing scheduling (049), agent-to-agent messaging / swarm over a separate registry (050), and per-task worktree isolation (051) — all cap-gated and default-off. | `loopplane.orchestration`, `loopplane.tools` |
| **Model providers** | 020, 035, 037, 045, 070 | Anthropic and OpenAI native adapters; OpenRouter and Ollama (reusing the OpenAI wire format); a native Google Gemini adapter — with per-call `thought_signature` preservation and replay for multi-turn tool use (070, ADR 0011); and native structured output (`response_format` / json_schema, OpenAI-family) negotiated as a model-boundary capability. Each provider is behind its own optional extra and registers with the `/v1/models` selector. | `loopplane.adapters.{anthropic,openai,openai_compat,gemini}`, `loopplane.model` |
| **Agent-capability tools** | 033, 034, 036, 044, 046, 047, 054, 069 | File tools (`edit_file`, `glob_files`, `grep`); web tools (`web_fetch`, `web_search`) with default-deny network-egress governance plus a bundled keyless search provider (047); multimodal image input (`ImageBlock`) with `accepts_media()` negotiation and document / PDF input (`DocumentBlock`, 069, ADR 0011 — native Anthropic / Gemini mappings, unsupported adapters fail safely); an agent task list (`todo_write`, 044); Jupyter cell editing (`notebook_edit`, 046); and file-edit undo (`undo_file`, 054, when snapshots are enabled). | `loopplane.tools.{internal,web}`, `loopplane.model` |
| **Autonomy & workflow governance** | 038, 039, 066 | Plan mode (read-only investigation → human approval → execute); a declarative permission rule DSL (host-supplied allow / deny / ask rules), both enforced at the Tool Gateway decide stage; and named permission modes (`acceptEdits` / `bypassPermissions` / `dontAsk` / `plan`) as a single `RuntimeConfig.permission_mode` option expanding to preset rule sets over the DSL (066, deny-wins preserved, default off). | `loopplane.governance.{plan_mode,rule_dsl,modes}` |
| **Execution safety** | 052 | Opt-in sandboxed command execution: an injectable POSIX `LocalJailCommandExecutor` (rlimits + env-scrub + `setsid` + a wall-clock timeout). Default = the verbatim host executor (byte-identical); Windows raises; docker is deferred. | `loopplane.tools` |
| **Cost governance** | 053, 055, 062–064, 068 | A pure pricing table (`TokenUsage → USD`, host-supplied rates, unwired by default); in-loop USD budget caps per-message / session (055, terminating with the `budget-exceeded` reason within schema v1); a durable `UsdLedger` keyed by `(principal, month)` with File / SQLite / Postgres backends (062); a per-user-monthly cap that folds the ledger total into enforcement (063, fail-open on a ledger outage); owner-scoped queryable spend — per-session and per-principal-monthly USD endpoints plus host accessors (064); and a pre-turn predictive cost guard that refuses a likely-overage turn before the model call (068, ADR 0014, default-off and fail-open). | `loopplane.{pricing,budget,ledger}`, `loopplane.webapi` |
| **Cost & efficiency** | 040–042 | Anthropic prompt caching (explicit stable-prefix breakpoints), configurable proactive auto-compaction (threshold-based), and an optional fail-safe cheap-model compaction summarizer. | `loopplane.adapters.anthropic`, `loopplane.loop` |
| **Extensibility** | 015, 016 | A lifecycle hook system (a registry + eleven lifecycle points; two gating points may gate / modify) and a manifest-based plugin system bundling skills + namespaced MCP servers + hooks behind an enable-list. | `loopplane.{hooks,plugins}` |
| **Host surfaces** | 011, 012, 017–019, 022, 023, 056, 065 | A web / API host (REST + SSE) with principal authentication and per-principal session scoping; an in-process studio / desktop host; a CLI host; a from-scratch web SPA with a login flow; an Electron desktop GUI over a local sidecar bridge; an optional OAuth / JWT verifier (056, behind `loopplane[oauth]`) that drops into the auth seam; and backend-semantic slash commands (`/cost`, `/model`, `/memory`, `/compact`) answered by the CLI and web hosts without a model round-trip (065 — host UX over a fail-safe `CommandRegistry`, not a gateway tool). | `loopplane.{webapi,studio,cli,commands}`, `apps/web`, `apps/desktop` |
| **Transports & platform** | 057–061, 067, 071, 072, 084–086 | MCP across all four transports — `stdio` / `http` / `sse` / `websocket` (057) — plus MCP resources surfaced as gateway-routed synthetic tools (059) and opt-in interactive OAuth for `http` / `sse` through host-owned authorization and token-store seams (084, ADR 0019); resumable session SSE via an in-memory ring buffer + `Last-Event-ID` replay (058), made durable across processes and workers by an opt-in `EventReplayStore` with File / SQLite / Postgres backends (071, ADR 0012); a Postgres checkpoint backend (060, behind `loopplane[postgres]`); a per-principal `TenantHostPool` giving each principal an isolated host with in-flight caps (061) plus opt-in cross-process admission grants so those caps stay cluster-scoped across web/API workers (085, ADR 0020, default-off); per-tenant fairness / quota above the pool with public-safe 429 / SSE rejection (072, ADR 0013, default-off) and opt-in cluster-wide fair model-turn interleaving for already-admitted work (086, ADR 0021, default-off); and JWKS refresh hardening for the JWT verifier — negative-kid cache, refresh throttle, single-flight (067). | `loopplane.adapters.mcp`, `loopplane.{webapi,checkpoint,fairness}` |
| **Web UI product experience** | 025–032, 074–077, 080–081 | A modern agent UI: markdown + collapsible tool cards + theming + two-pane shell + stop control (025); reasoning / question-options / token-usage signals (026); read-only inspection panels (027); model selection + file attachments (028); i18n + syntax highlighting + command palette + cost estimate (029); session management (030); message actions (031); interaction resilience — modals / retry / toasts / skeletons (032); live WebSocket/session parity (074); first-class capability management (075), durable/principal-safe hardening (076), and safe shared-detail plus lifecycle remediation (081); an accessible responsive presentation refactor (080); and host-owned Agent Controls (077) with one-run permission selection, mutable plan posture, authoritative exact cost/enum-only budget status, structured upload and metadata-only artifact/context references, and deterministic zero-request suggestions. The browser never owns enforcement or receives provider credentials, raw rules, caps/rates, private paths, or resource content. | `apps/web`, `loopplane.{host,webapi,governance,budget}` |
| **Desktop cowork parity** | 078 | Desktop reaches cowork parity with Web and becomes independently installable. The cowork surface moves into the first-party `@loopplane/cowork-presentation` package that both apps render from through their own adapters (Web keeps talking to the unit-011 HTTP host; Desktop talks to a local sidecar). Adds a JSON-RPC V1 stdio protocol whose sidecar negotiates before composing the Host, OS profile ownership with validated generations, projects and chooser-bound workspaces, multi-pane single-active interactive leases, a checkpoint audit view, and an unencrypted-by-disclosure portable backup excluding unsent drafts and credentials with a validate / commit / cancel restore lease. Delivery replaces the unit-024 bare route with four scripts behind a third external-human review: one tokenized verifier emitting a bounded descriptor, two token-free descriptor-only wrappers for the PyInstaller freeze and the `electron-builder` package, and a built-in .NET UI-Automation smoke over a copy outside the checkout. PyInstaller stays build-only, absent from `pyproject.toml` and `uv.lock`. Web outward contracts, the Event Bus, checkpoint records, Gateway invocation, and every default are unchanged. | `packages/cowork-presentation`, `apps/desktop`, `loopplane.host` |
| **Desktop capability parity** | 083 | Desktop's operator gains the governance surface Web already had, with zero runtime change (`src/loopplane` untouched). Cost visibility: a `cost.get` projection joins session spend (live tracker) and month-to-date spend (durable ledger) with the unpriced / partially-priced / unavailable / zero distinction carried from the host's agent-controls budget posture — shown in the conversation pane and Inspection, never rendered as `$0` when unpriced. The six Web settings panels move into `@loopplane/cowork-presentation` behind narrow service ports (Web becomes thin `ApiClient` adapters; its untouched contract + Vitest suites prove outward behavior unchanged). Capability management over sidecar RPC: MCP / skills / memory (14 methods) and schedules / workspace contexts / model default (15 methods) — every projection a field-by-field allowlist (no endpoint URL, credential, owner id, or raw problem text reaches the renderer), every durable mutation behind the profile mutation lease with main-generated mutation ids, per-domain availability cards on `capabilities.list`, and 29 guarded IPC channels each with an untrusted-sender test. Settings grows from three tabs to nine, bilingual (en / zh-TW). Per-session model *selection* (US2) and composer host commands (US5) are deliberately stopped pending maintainer decisions: a selection cannot take effect on a single-adapter host (`ModelRequest` carries no model id), and `CommandRegistry` lives outside the sidecar boundary allow-list. | `apps/desktop`, `packages/cowork-presentation` |
| **Packaging & release** | 014, 024, 073 | Release packaging and docs (wheel / sdist, `py.typed`, public API reference, CI gates); desktop packaging (a PyInstaller-frozen sidecar + electron-builder + a spawn resolver); and a code-review remediation pass over units 001–072 — locked CI gates with `apps/web/**` path coverage, public-safe MCP / `web_fetch` error seams, `web_fetch` size limits, and a Spec Kit task-drift audit (073). | packaging metadata, `apps/desktop` |

## MCP interactive authorization (unit 084)

An `http` or `sse` MCP server may declare `authorization="interactive"`. The runtime
then composes the MCP SDK's authorization-code flow through two host-owned seams: one
handles the browser/callback interaction and one stores token material. Waiting for the
human is explicitly time-bounded across both transports; state is single-use and
constant-time checked. Refresh failure is fail-closed: unattended work reports that
authorization is required and never falls through to an anonymous request or opens a
browser. Static bearer-token configuration remains a separate, mutually exclusive mode;
`stdio` and `websocket` do not accept interactive authorization.

Desktop supplies both seams in its main/sidecar boundary. Main owns the system browser,
loopback callback, and OS-encrypted vault; refresh-token rotation is written back so a
later restart can reconnect without another browser approval. The renderer receives only
`{server, mode, state}`, and profile backups contain no authorization material.

**Rollback:** the feature is inert unless a host supplies an authorization handler *and* a
server declares interactive mode. A missing token store uses the process-only in-memory
default; a host supplies one only when it needs durability. Removing the handler (and the
mode declaration) restores the pre-084 path. There is no dependency, data migration,
event/content schema change, or default-value change to reverse; a host-owned encrypted
vault can be removed independently.

## Internal tools and model providers

**Tools reachable through the Tool Gateway** (verified in `src/loopplane/tools/`):

| Tool | Purpose | Read-only |
| ---- | ------- | --------- |
| `read_file` | Read a text file. | yes |
| `write_file` | Write / overwrite a text file (stale-write guard). | no |
| `edit_file` | Replace a uniquely-occurring substring in a file. | no |
| `search_files` | Substring search for lines under a directory. | yes |
| `glob_files` | List files matching a glob within the working scope. | yes |
| `grep` | Regex content search (`content` / `files_with_matches` / `count`). | yes |
| `run_command` | Run a shell command inside the working scope. | no |
| `ask_user` | Ask the user structured question(s). | no |
| `exit_plan_mode` | Submit a plan for approval to leave plan mode. | no |
| `memory_write` | Create or update a durable memory entry. | no |
| `todo_write` | Maintain the per-run task list (set-the-whole-list). | no |
| `notebook_edit` | Edit a single Jupyter notebook cell. | no |
| `undo_file` | Revert a file to its pre-edit snapshot (when snapshots enabled). | no |
| `web_fetch` | Fetch an http(s) URL to readable text (network-gated). | — |
| `web_search` | Query a search provider (a keyless reference provider ships; network-gated). | — |
| `read_upload` | Read an uploaded attachment by id (web/API). | yes |
| `spawn_subagent` | Delegate a bounded sub-task to one child agent (opt-in). | no |

> Tool calls run concurrently where safe: the loop batches concurrency-safe calls in
> parallel and runs the rest sequentially.
>
> The cap-gated Tier-2 autonomy supervisors (048–051) register **additional** tool
> families when enabled — background tasks, scheduling, agent-to-agent messaging, and
> worktree management — each off by default. Structured output (045) is a model-boundary
> capability negotiated per provider, not a gateway tool. The backend slash commands
> (065) are host UX answered by the CLI / web hosts and likewise never pass through the
> Tool Gateway.

**Model providers:** Anthropic, OpenAI, OpenRouter, Ollama, and native Google Gemini —
each behind its own optional install extra; OpenRouter additionally brokers 100+ models
behind the OpenAI wire format.

## Scope boundaries (out of scope / deferred)

The following are intentionally **not** in scope today (each is recorded in the relevant
spec / ADR or roadmap). Items shipped since v0.4.0 by the 064–075 line — document / PDF
input (069), queryable cost surfacing and the pre-turn cost guard (064 / 068), backend
slash commands (065), named permission modes (066), Gemini `thought_signature`
round-trip (070), durable cross-process SSE replay (071), and per-tenant fairness /
quota (072) — are **no longer** in this list.

- **Multimodal:** binary artifact durability (document / PDF *input* shipped in 069;
  OCR, text extraction, and document-search workflows remain separate features).
- **Billing:** a model proxy / billing layer on top of pricing and the USD caps (spend is
  now queryable via 064, but there is no metering / invoicing surface).
- **Execution isolation:** docker / container sandboxing (the POSIX jail ships in 052;
  Windows `run_command` is unsandboxed); remote / distributed agent execution (children
  run in-process).
- **Platform tail:** many-writer durability and cross-process / distributed pooling and
  scheduling above the per-principal host pool (061) — 071 makes SSE replay durable and
  072 adds in-process fairness / per-tenant quota, but execution remains in-process
  single-worker.
- **Editing & history:** prior-message editing and in-session message search (074 added
  session-level fork / search / star, not per-message editing or search).
- **Parity:** IDE extension (VS Code / JetBrains), STT / TTS / voice, and output styles.

For where these sit relative to reference agent harnesses and a prioritized way to close
them, see [`gap-analysis.md`](gap-analysis.md).

## Note on spec status

The per-unit `specs/*/spec.md` files are marked `Status: Draft` even though every unit
(001–075) is implemented and verified (001–063 released, 064–075 pending release). The
marker reflects the spec template default, not the implementation status; the
authoritative per-unit status lives in
[`loopplane-agent-board.md`](loopplane-agent-board.md) (all units **Verified**) and the
release history in [`../CHANGELOG.md`](../CHANGELOG.md).
