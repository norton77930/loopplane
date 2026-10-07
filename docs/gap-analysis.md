# LoopPlane Gap Analysis & Forward Roadmap

> How LoopPlane's functional scope compares to two reference agent harnesses —
> **claude-code** and **orion-agent** — and a prioritized, tiered roadmap for closing the
> gaps. Companion to [`capabilities.md`](capabilities.md) (what LoopPlane has today) and
> [`loopplane-agent-board.md`](loopplane-agent-board.md) (per-unit status).
>
> Per Constitution IX (*reference, not clone*), these harnesses inform direction only;
> any capability LoopPlane adopts is re-derived through its own spec.

## Sources & method

- **claude-code** — feature inventory of the `@anthropic-ai/claude-code` 2.1.x line
  (40+ built-in tools, 90+ slash commands, 28 hook events, 6 permission modes,
  multi-agent / worktree / remote, MCP + resources + OAuth).
- **orion-agent** — feature inventory of a full-stack Python + TS sibling harness (30+
  tools, parallel executor, swarm peer messaging, background tasks, scheduling, STT/TTS,
  model proxy + billing, 3 sandbox modes, 4 MCP transports + OAuth, multi-level budgets,
  Postgres).
- **LoopPlane** — its own specs (001–084; 001–083 released through v0.5.0, 084 implemented
  in the current worktree and awaiting its final board gate) verified against
  `src/loopplane/` and `apps/`. The v0.4.0 line (044–063) closed the large majority of the
  gaps below and the later line closed most of what remained; this document reflects the
  implemented capability surface through unit 084.

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
| Named permission modes (acceptEdits/bypass/dontAsk) | ✅ | ◑ | ✅ (066 presets over DSL 039) |
| One-shot subagents | ✅ | ✅ | ✅ |
| Agent-to-agent messaging / swarm | ✅ | ✅ | ✅ (050) |
| Parallel tool execution | ✅ | ✅ | ✅ |
| Prompt caching | ✅ | ✅ | ✅ |
| Auto-compaction | ✅ | ✅ | ✅ |
| Cheap-model compaction summary | ◑ | ✅ | ✅ |
| Providers (Anthropic/OpenAI/Gemini/OpenRouter/Ollama) | ◑ | ✅ | ✅ |
| Multimodal image input | ✅ | ✅ | ✅ |
| Multimodal PDF / documents | ✅ | ◑ | ✅ (`DocumentBlock` 069) |
| STT / TTS / voice | ✅ | ✅ | ❌ |
| Hooks | ✅ | ✅ | ✅ |
| Plugins / skills | ✅ | ✅ | ✅ |
| MCP tools | ✅ | ✅ | ✅ (stdio/http/sse/ws 057) |
| MCP resources | ✅ | ✅ | ✅ (059) |
| MCP transports (SSE/WS) + OAuth | ✅ | ✅ | ✅ (SSE/WS 057; interactive OAuth 084) |
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
| Backend-semantic slash commands | ✅ | ◑ | ✅ (065 `loopplane.commands`) |
| Loop engineering (validators / evaluators / scheduler infra) | ❌ | ◑ | ✅ |
| Metadata-only observability contracts | ◑ | ◑ | ✅ |
| Principal auth / session scoping | ✅ | ✅ | ✅ |
| OAuth / JWT + external IdP | ✅ | ✅ | ✅ (056) |
| Storage backends | ◑ | ✅ (Postgres) | ✅ (file / SQLite / Postgres 060) |
| Concurrent multi-user execution | ✅ | ✅ | ◑ (pool 061 + fairness/quota 072, in-process) |
| Multi-level budget / billing | ◑ | ✅ | ◑ (USD caps 055/063 + pre-turn guard 068 + ledger 062; no proxy/billing) |
| Server-side pricing surfacing (queryable spend) | ◑ | ✅ | ✅ (064 cost endpoints + `/cost` 065) |
| Host surfaces (CLI / web / desktop) | ✅ | ✅ | ✅ |
| IDE extension (VS Code / JetBrains) | ✅ | ❌ | ❌ |

## C2. Gap status (through unit 083)

The original G1–G24 gaps and where they now stand. The v0.4.0 line (044–063) closed or
partially closed the large majority, and the 064–075 line (verified, pending release)
closed most of the rest; the implementing unit is cited. Units 076–083 closed **no
further G1–G24 gap** — that line was parity, presentation, and delivery work (web
capability durability, Desktop cowork and capability parity, CLI/remote parity, open-source
release readiness), not gap closure. The list below is therefore unchanged by them, which is
worth stating rather than leaving a reader to infer it from silence.

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

### Closed in 064–084

- **G10 — Named permission modes** → **066** (acceptEdits / bypassPermissions / dontAsk /
  plan as preset rule sets over the 039 DSL, selected by `RuntimeConfig.permission_mode`).
- **G14 — Backend-semantic slash commands** → **065** (`/cost`, `/model`, `/memory`,
  `/compact` on the CLI and web hosts via `loopplane.commands`; host UX, not a gateway
  tool).
- **G23 — Server-side SSE reconnect** → **058 + 071** (`Last-Event-ID` replay over an
  in-memory ring, ADR 0006; made durable across processes / workers by the opt-in
  `EventReplayStore` with File / SQLite / Postgres backends, ADR 0012).
- **G24 — PDF / `DocumentBlock` input** → **069** (a new `DocumentBlock` content type with
  native Anthropic / Gemini mappings, ADR 0011; unsupported adapters fail safely before
  provider submission — binary artifact durability remains a separate deferral).
- **G12 — MCP breadth** → **057** (SSE + WebSocket transports) + **059** (resources as
  gateway-routed synthetic tools + host-injected bearer token) + **084** (host-owned,
  authorization-code OAuth for HTTP/SSE, including Desktop persistence and unattended
  refresh). The tracked G12 transport/resource/interactive-authorization scope is closed.

### Partially closed

- **G11 — Sandbox execution isolation** → **052** (a POSIX `LocalJailCommandExecutor`:
  rlimits / env-scrub / `setsid`). Still open: Windows (raises) and docker / container
  isolation.
- **G20 — Concurrent multi-user execution** → **061** (a per-principal `TenantHostPool`,
  ADR 0009) + **072** (per-tenant fairness / quota above the pool, ADR 0013, in-process)
  + **085** (cross-process admission grants so in-flight / outstanding caps stay
  cluster-scoped across web/API workers, ADR 0020) + **086** (cluster-wide fair
  *turn* interleaving for already-admitted work, ADR 0021, default-off)
  + **087** (opt-in weighted model-start shares). Still open: live run migration.
  Unit **088** takes only the between-run handoff when one worker drains; moving
  an in-progress turn stays open.
- **G21 — Model proxy / billing + server-side pricing** → **053** (a pure pricing table) +
  **064** (owner-scoped queryable spend endpoints) + **068** (a pre-turn predictive cost
  guard, ADR 0014). Still open: any model proxy / metering / billing layer.

### Still open

- **G9 — Remote / cloud agent execution.** Children run in-process via `run_loop`; no
  out-of-process or networked agent execution (deferred, ADR 0003). Unit **079** is adjacent
  but does not close this: its remote bridge is remote *control* of a running host from a
  terminal, as an ordinary client of the outward web contract (ADR 0018). The agents
  themselves still run in the host's own process.
- **G13 — IDE extension** (VS Code / JetBrains). Desktop only; no IDE integration.
- **G15 — STT / TTS / voice.** None.
- **G17 — Output styles** / pluggable formatters. None.

## C3. Where LoopPlane is at parity or ahead

The comparison is not one-directional. LoopPlane leads on:

- **Spec-first governance** — a ratified constitution, per-unit specs / plans / tasks, and
  ADRs for every boundary crossing.
- **Determinism & safety posture** — deny-wins, fail-closed deciders; metadata-only,
  deterministic observability contracts (010); additive features that default to
  byte-identical behavior — the entire v0.4.0 line (044–063) shipped without a single core
  rewrite, `SCHEMA_VERSION` bump, or content-model change, and the 064–083 line kept the
  pattern (no `SCHEMA_VERSION` bump; the only content-model changes are the additive
  extensions recorded in ADR 0011).
- **Loop engineering layer** — first-class validators / evaluators / retry / repair and a
  virtual-clock scheduler (003–005), which neither reference foregrounds as a reusable
  contract.
- **Clean boundaries** — a single Tool Gateway (V) and Event Bus (VI) with enforced
  import boundaries, making the runtime auditable and embeddable.

## C4. Forward roadmap (through unit 084, prioritized)

The previous edition of this roadmap (written post-v0.4.0) has itself been largely
executed by the 064–077 line plus the out-of-sequence 080–081 delivery work: every former
P1 item shipped — cost surfacing (064), backend slash commands (065), named permission
modes (066), JWKS-refresh hardening (067) — as did most of P2 — durable SSE replay (071),
in-process fairness/quota (072), PDF / `DocumentBlock` (069), the pre-turn cost guard
(068), native Gemini `thought_signature` (070), code-review remediation (073), web
parity/capability management and hardening (074–076), responsive presentation and
security remediation (080–081), and host-owned Web Agent Controls (077). What remains is
the tail below. It is a **suggested priority list only**. `078-desktop-cowork-parity` has
since closed `Verified` on `docs/loopplane-agent-board.md`, which remains the only
completion authority; new roadmap items would be specced as later units.

Since that paragraph was written, **078** (Desktop cowork parity), **079** (CLI/remote
parity), **082** (open-source release readiness) and **083** (Desktop capability parity)
have all closed `Verified`; **084** closes the tracked G12 interactive-OAuth tail in the
current worktree. The other units do not change the remaining tail below: 078 and 083
brought Desktop to parity with an existing surface, 079 added remote *control* rather than
the remote *execution* G9 asks for, and 082 was repository tooling. G13 (IDE extension) in
particular is untouched — a packaged Desktop app is not an IDE integration. The agent board
remains the authority for 084's final delivery status.

**P1 — platform depth (the remaining distributed tail)**
- **G20 remaining** — live run migration of an in-progress turn. Unit 087
  implements opt-in weighted tenant model-start shares. Unit 088 lets one worker
  drain: it refuses new runs, finishes the run it already holds, and then another
  worker can accept that person. That is not billing, CPU-time allocation, or a
  guarantee that an in-progress turn moves to another process.
- **Docker / container sandbox** for `run_command` (G11 tail; the POSIX jail shipped in
  052; Windows still raises).

**P2 — tail & parity**
- Remote / distributed agent execution (G9).
- A model proxy / metering / billing layer (G21 tail; pricing, caps, and queryable spend
  are done).
- File / SQLite ledger cross-process atomicity (document loudly or add a process lock;
  Postgres is the multi-process story today).
- A subagent aggregate fan-out cap (today `max_subagent_depth` bounds depth, not total
  count / aggregate budget across the tree).
- `resume()` working-scope persistence (resume rebuilds with the current working directory,
  not the session's original scope).
- Binary artifact durability (the 069 deferral) and document OCR / extraction workflows.
- IDE extension (G13), STT / TTS (G15), output styles (G17), and event-schema v1→v2
  migration tooling.

> Promotion of any item into [`loopplane-agent-board.md`](loopplane-agent-board.md) §3 (the
> roadmap autopilot) is a separate, deliberate step so the autopilot is not driven by
> speculative units.
