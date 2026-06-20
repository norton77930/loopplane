# LoopPlane Gap Analysis & Forward Roadmap

> How LoopPlane's functional scope compares to two reference agent harnesses —
> **claude-code** and **orion-agent** — and a prioritized, tiered roadmap for closing the
> gaps. Companion to [`capabilities.md`](capabilities.md) (what LoopPlane has today) and
> [`loopplane-agent-board.md`](loopplane-agent-board.md) (per-unit status).
>
> Per Constitution IX (*reference, not clone*), these harnesses inform direction only;
> any capability LoopPlane adopts is re-derived through its own spec.

## Sources & method

- **claude-code** — feature inventory from a source-reconstructed copy at the
  `@anthropic-ai/claude-code` 2.1.x level (40+ built-in tools, 90+ slash commands, 28
  hook events, 6 permission modes, multi-agent / worktree / remote, MCP + resources +
  OAuth).
- **orion-agent** — feature inventory of a full-stack Python + TS sibling harness (30+
  tools, parallel executor, swarm peer messaging, background tasks, scheduling, STT/TTS,
  model proxy + billing, 3 sandbox modes, 4 MCP transports + OAuth, multi-level budgets,
  Postgres).
- **LoopPlane** — its own specs (001–063, released as v0.4.0) verified against
  `src/loopplane/` and `apps/`. The v0.4.0 line (044–063) closed the large majority of the
  gaps below; this document is the post-v0.4.0 status.

Matrix legend: ✅ has an equivalent capability · ◑ partial / different shape · ❌ absent.
Cells reflect *presence of an equivalent capability*, not feature-for-feature parity. The
LoopPlane column is source-verified; the reference columns are from the inventory
snapshots above.

## C1. Comparison matrix

| Capability | claude-code | orion-agent | LoopPlane |
| ---------- | :---------: | :---------: | :-------: |
| File tools (read/write/edit/glob/grep) | ✅ | ✅ | ✅ |
| Shell execution | ✅ | ✅ | ✅ |
| Web fetch / search | ✅ | ✅ | ✅ (keyless provider 047) |
| Durable memory | ✅ | ✅ | ✅ |
| Plan mode | ✅ | ✅ | ✅ |
| Permission rules (allow/deny/ask) | ✅ | ✅ | ✅ |
| Named permission modes (acceptEdits/bypass/dontAsk) | ✅ | ◑ | ◑ (DSL 039 + plan mode 038; no named modes) |
| One-shot subagents | ✅ | ✅ | ✅ |
| Agent-to-agent messaging / swarm | ✅ | ✅ | ✅ (050) |
| Parallel tool execution | ✅ | ✅ | ✅ |
| Prompt caching | ✅ | ✅ | ✅ |
| Auto-compaction | ✅ | ✅ | ✅ |
| Cheap-model compaction summary | ◑ | ✅ | ✅ |
| Providers (Anthropic/OpenAI/Gemini/OpenRouter/Ollama) | ◑ | ✅ | ✅ |
| Multimodal image input | ✅ | ✅ | ✅ |
| Multimodal PDF / documents | ✅ | ◑ | ❌ |
| STT / TTS / voice | ✅ | ✅ | ❌ |
| Hooks | ✅ | ✅ | ✅ |
| Plugins / skills | ✅ | ✅ | ✅ |
| MCP tools | ✅ | ✅ | ✅ (stdio/http/sse/ws 057) |
| MCP resources | ✅ | ✅ | ✅ (059) |
| MCP transports (SSE/WS) + OAuth | ✅ | ✅ | ◑ (SSE/WS 057; interactive OAuth deferred) |
| TodoWrite / task list tool | ✅ | ✅ | ✅ (044) |
| NotebookEdit | ✅ | ✅ | ✅ (046) |
| Background / long-running task tools | ✅ | ✅ | ✅ (048) |
| Scheduling / cron exposed as tools | ✅ | ✅ | ✅ (049) |
| Model-native structured output (json_schema) | ✅ | ✅ | ✅ (045) |
| Worktree isolation | ✅ | ❌ | ✅ (051) |
| Remote / cloud execution | ✅ | ◑ | ❌ |
| Sandbox isolation (local / docker) | ✅ | ✅ | ◑ (POSIX jail 052; docker/Windows no) |
| File-edit undo / rewind | ✅ | ✅ | ✅ (undo_file 054) |
| Output styles | ✅ | ◑ | ❌ |
| Backend-semantic slash commands | ✅ | ◑ | ◑ (frontend palette only) |
| Loop engineering (validators / evaluators / scheduler infra) | ❌ | ◑ | ✅ |
| Metadata-only observability contracts | ◑ | ◑ | ✅ |
| Principal auth / session scoping | ✅ | ✅ | ✅ |
| OAuth / JWT + external IdP | ✅ | ✅ | ✅ (056) |
| Storage backends | ◑ | ✅ (Postgres) | ✅ (file / SQLite / Postgres 060) |
| Concurrent multi-user execution | ✅ | ✅ | ◑ (per-principal pool 061, in-process) |
| Multi-level budget / billing | ◑ | ✅ | ◑ (USD caps 055 + ledger 062/063; no proxy/billing) |
| Server-side pricing surfacing (queryable spend) | ◑ | ✅ | ❌ (pricing computes 053; no endpoint) |
| Host surfaces (CLI / web / desktop) | ✅ | ✅ | ✅ |
| IDE extension (VS Code / JetBrains) | ✅ | ❌ | ❌ |

## C2. Gap status (post-v0.4.0)

The original G1–G24 gaps and where they now stand. The v0.4.0 line (044–063) closed or
partially closed the large majority; the implementing unit is cited.

### Closed in v0.4.0

- **G1 — TodoWrite / task-list tool** → **044** (`todo_write`).
- **G2 — NotebookEdit** → **046** (`notebook_edit`).
- **G3 — Model-native structured output** (`response_format` / json_schema) → **045**
  (a model-boundary capability, not just `packs` validators).
- **G4 — Bundled web-search provider** → **047** (a keyless DuckDuckGo reference provider;
  `web_search` no longer requires a host-injected provider).
- **G5 — Background / long-running task tools** → **048**.
- **G6 — Agent-facing scheduling / cron tools** → **049** (wraps the unit-004 scheduler).
- **G7 — Agent-to-agent messaging / swarm** → **050** (a separate in-run message registry,
  ADR 0003 — the 043 deferral is now lifted).
- **G8 — Worktree isolation** → **051** (per-task git worktree, default-off).
- **G16 — File-edit undo / rewind** → **054** (`undo_file` over per-session snapshots).
- **G18 — OAuth / JWT + external IdP** → **056** (a JWT verifier behind `loopplane[oauth]`
  dropping into the 022 auth seam).
- **G19 — Postgres / networked DB** → **060** (a Postgres checkpoint backend, ADR 0008).
- **G22 — Multi-level budget caps** (per-message / session / user-monthly USD) →
  **055 + 062 + 063** (in-loop USD caps + a durable per-(principal, month) ledger).

### Partially closed in v0.4.0

- **G11 — Sandbox execution isolation** → **052** (a POSIX `LocalJailCommandExecutor`:
  rlimits / env-scrub / `setsid`). Still open: Windows (raises) and docker / container
  isolation.
- **G12 — MCP breadth** → **057** (SSE + WebSocket transports) + **059** (resources as
  gateway-routed synthetic tools + host-injected bearer token). Still open: interactive
  OAuth authorization-code flow.
- **G20 — Concurrent multi-user execution** → **061** (a per-principal `TenantHostPool`,
  ADR 0009). Still open: the in-process single-worker limit and the fairness / quota /
  many-writer / distributed tail.
- **G23 — Server-side SSE reconnect** → **058** (`Last-Event-ID` replay over an in-memory
  ring, ADR 0006). Still open: durable cross-process / multi-worker replay.
- **G21 — Model proxy / billing + server-side pricing** → **053** (a pure pricing table).
  Still open: a queryable spend endpoint / `/cost` surfacing and any proxy / billing.

### Still open

- **G9 — Remote / cloud agent execution.** Children run in-process via `run_loop`; no
  out-of-process or networked agent execution (deferred, ADR 0003).
- **G10 — Named permission modes** (acceptEdits / bypassPermissions / dontAsk). The
  permission DSL (039) + plan mode (038) exist, but not these named convenience presets.
- **G13 — IDE extension** (VS Code / JetBrains). Desktop only; no IDE integration.
- **G14 — Backend-semantic slash commands** (`/compact`, `/cost`, `/model`, `/memory`).
  Only the frontend command palette (029); no backend command surface.
- **G15 — STT / TTS / voice.** None.
- **G17 — Output styles** / pluggable formatters. None.
- **G24 — PDF / `DocumentBlock` input.** LoopPlane's own deferral (ADR 0001 D2); needs an
  OpenAI chat-completions mapping decision, binary artifact durability, and a content-model
  change.

## C3. Where LoopPlane is at parity or ahead

The comparison is not one-directional. LoopPlane leads on:

- **Spec-first governance** — a ratified constitution, per-unit specs / plans / tasks, and
  ADRs for every boundary crossing.
- **Determinism & safety posture** — deny-wins, fail-closed deciders; metadata-only,
  deterministic observability contracts (010); additive features that default to
  byte-identical behavior — the entire v0.4.0 line (044–063) shipped without a single core
  rewrite, `SCHEMA_VERSION` bump, or content-model change.
- **Loop engineering layer** — first-class validators / evaluators / retry / repair and a
  virtual-clock scheduler (003–005), which neither reference foregrounds as a reusable
  contract.
- **Clean boundaries** — a single Tool Gateway (V) and Event Bus (VI) with enforced
  import boundaries, making the runtime auditable and embeddable.

## C4. Forward roadmap (post-v0.4.0, prioritized)

The original tiered roadmap (Tier-1 capability → Tier-2 autonomy → Tier-3 cost/safety →
Tier-4 platform) is essentially **fully executed** by the v0.4.0 line. What remains is a
smaller, mostly tail / polish backlog, re-prioritized below. It is a **suggested priority
list only** — no unit below is specced or implemented yet; unit numbers start at the next
free (064).

**P1 — high leverage, backing pieces already exist**
- **Cost surfacing** (the 053/062 tail) — a queryable per-run / per-principal-monthly spend
  endpoint and a `/cost` view; pricing already computes USD and the ledger already records
  it, but nothing exposes it (only the `budget-exceeded` termination is observable).
- **Backend-semantic slash commands** (G14) — `/compact`, `/cost`, `/model`, `/memory` on
  the backend hosts (compaction, pricing, the model registry, and inspection already back
  them); must route through the Gateway / Event Bus, not bypass them.
- **Named permission modes** (G10) — acceptEdits / bypassPermissions / dontAsk as preset
  `PermissionRuleSet`s composing over the existing 039 DSL (small, high-ergonomics).
- **JWKS-refresh hardening** (056 follow-up) — a bounded negative-kid cache + cross-request
  throttle so an unknown-kid spray cannot amplify upstream IdP fetches.

**P2 — platform depth**
- **Durable cross-process / multi-worker SSE reconnect** (the 058/ADR 0006 D6 tail) — a
  shared / durable event-replay store distinct from the checkpoint's reduced projection;
  needed before horizontal web scale-out.
- **G20 platform tail** — resource fairness / fair model-call scheduling, per-tenant quota
  beyond in-flight counts, many-writer durability, cross-process / distributed pooling.
- **PDF / `DocumentBlock`** (G24) — needs an OpenAI chat-completions mapping decision,
  binary artifact durability, and a content-model ADR.
- **Pre-turn predictive cost guard** (the 055/ADR 0005 tail) — refuse a likely-overage turn
  before it runs (budget is enforced post-turn today).
- **Native Gemini per-call `thought_signature`** (037 tail) — a `ToolCallBlock`
  content-model field, so a Constitution-VI / ADR matter.

**P3 — tail & parity**
- Docker / container sandbox for `run_command` (G11 tail; POSIX shipped in 052).
- Remote / distributed agent execution (G9).
- File / SQLite ledger cross-process atomicity (document loudly or add a process lock;
  Postgres is the multi-process story today).
- A subagent aggregate fan-out cap (today `max_subagent_depth` bounds depth, not total
  count / aggregate budget across the tree).
- `resume()` working-scope persistence (resume rebuilds with the current working directory,
  not the session's original scope).
- MCP interactive OAuth authorization-code flow (G12 tail; bearer token shipped in 059).
- IDE extension (G13), STT / TTS (G15), output styles (G17), and event-schema v1→v2
  migration tooling.

> Promotion of any item into [`loopplane-agent-board.md`](loopplane-agent-board.md) §3 (the
> roadmap autopilot) is a separate, deliberate step so the autopilot is not driven by
> speculative units.
