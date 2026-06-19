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
- **LoopPlane** — its own specs (001–043) verified against `src/loopplane/` and `apps/`.

Matrix legend: ✅ has an equivalent capability · ◑ partial / different shape · ❌ absent.
Cells reflect *presence of an equivalent capability*, not feature-for-feature parity. The
LoopPlane column is source-verified; the reference columns are from the inventory
snapshots above.

## C1. Comparison matrix

| Capability | claude-code | orion-agent | LoopPlane |
| ---------- | :---------: | :---------: | :-------: |
| File tools (read/write/edit/glob/grep) | ✅ | ✅ | ✅ |
| Shell execution | ✅ | ✅ | ✅ |
| Web fetch / search | ✅ | ✅ | ◑ (search needs host provider) |
| Durable memory | ✅ | ✅ | ✅ |
| Plan mode | ✅ | ✅ | ✅ |
| Permission rules (allow/deny/ask) | ✅ | ✅ | ✅ |
| Named permission modes (acceptEdits/bypass/dontAsk) | ✅ | ◑ | ◑ |
| One-shot subagents | ✅ | ✅ | ✅ |
| Agent-to-agent messaging / swarm | ✅ | ✅ | ❌ |
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
| MCP tools | ✅ | ✅ | ✅ (stdio + http) |
| MCP resources | ✅ | ✅ | ❌ |
| MCP transports (SSE/WS) + OAuth | ✅ | ✅ | ❌ |
| TodoWrite / task list tool | ✅ | ✅ | ❌ |
| Background / long-running task tools | ✅ | ✅ | ❌ |
| Scheduling / cron exposed as tools | ✅ | ✅ | ◑ (host-driven scheduler) |
| Model-native structured output (json_schema) | ✅ | ✅ | ❌ |
| Worktree isolation | ✅ | ❌ | ❌ |
| Remote / cloud execution | ✅ | ◑ | ❌ |
| Sandbox isolation (local / docker) | ✅ | ✅ | ❌ (policy layer only) |
| File-edit undo / rewind | ✅ | ✅ | ◑ (checkpoint / resume) |
| Output styles | ✅ | ◑ | ❌ |
| Backend-semantic slash commands | ✅ | ◑ | ◑ (frontend palette) |
| Loop engineering (validators / evaluators / scheduler infra) | ❌ | ◑ | ✅ |
| Metadata-only observability contracts | ◑ | ◑ | ✅ |
| Principal auth / session scoping | ✅ | ✅ | ✅ |
| OAuth / JWT + external IdP | ✅ | ✅ | ❌ |
| Storage backends | ◑ | ✅ (Postgres) | ◑ (file / SQLite) |
| Concurrent multi-user execution | ✅ | ✅ | ❌ |
| Multi-level budget / billing | ◑ | ✅ | ◑ (budget policy) |
| Host surfaces (CLI / web / desktop) | ✅ | ✅ | ✅ |
| IDE extension (VS Code / JetBrains) | ✅ | ❌ | ❌ |

## C2. Confirmed gaps

Each gap below is something at least one reference harness exposes and LoopPlane does not
(verified against the source tree).

### Agent capability
- **G1 — TodoWrite / task-list tool.** Both references expose an agent-facing task list;
  LoopPlane has none.
- **G2 — NotebookEdit.** Both references edit Jupyter notebooks; LoopPlane has no
  notebook tool.
- **G3 — Model-native structured output** (`response_format` / json_schema). Both
  references support it; LoopPlane has only the `packs` JSON-schema *validators* (output
  checking, not model-enforced output).
- **G4 — Bundled web-search provider.** References ship a default search provider;
  LoopPlane's `web_search` (034) requires a host-injected `SearchProvider`.

### Autonomy & workflow
- **G5 — Background / long-running task tools** (`TaskCreate/Get/List/Stop/Output`,
  Monitor). Both references; LoopPlane has none.
- **G6 — Agent-facing scheduling / cron tools.** Both references expose scheduling *as
  tools*; LoopPlane has a host-driven in-process scheduler (004) but no agent-callable,
  persistent cron.
- **G7 — Agent-to-agent messaging / swarm** (SendMessage / AgentSend + teams). Both
  references; LoopPlane unit 043 explicitly defers this.
- **G8 — Worktree isolation** (Enter/ExitWorktree). claude-code only; LoopPlane has none.
- **G9 — Remote / cloud agent execution.** claude-code only; LoopPlane has none.
- **G10 — Named permission modes** (acceptEdits / bypassPermissions / dontAsk).
  claude-code has six; LoopPlane has the permission DSL (039) + plan mode (038) but not
  these named convenience modes.

### Execution safety
- **G11 — Real sandbox execution isolation** (local subprocess jail / docker). orion has
  three modes; claude-code has a sandbox; LoopPlane has decision-layer policies (009) and
  working-scope confinement, but `run_command` still executes on the host.

### Integration & breadth
- **G12 — MCP breadth:** resources (list / read), SSE / WebSocket transports, and OAuth.
  Both references; LoopPlane supports `stdio` + `http` tools only (verified in
  `adapters/mcp/config.py`).
- **G13 — IDE extension** (VS Code / JetBrains). claude-code only; LoopPlane has desktop
  but no IDE integration.
- **G14 — Backend-semantic slash commands** (`/compact`, `/cost`, `/model`, `/memory`).
  claude-code has 90+; LoopPlane has a frontend-only command palette (029).
- **G15 — STT / TTS / voice.** Both references; LoopPlane has none.
- **G16 — File-edit undo / rewind / history snapshots.** orion has file-history,
  claude-code has `/rewind`; LoopPlane has checkpoint / resume but no file-edit undo.
- **G17 — Output styles.** claude-code has pluggable output formatters; LoopPlane has
  none.

### Platform / multi-tenant
- **G18 — OAuth / JWT + external IdP.** Both references; LoopPlane's auth boundary (022)
  takes only a host-injected verifier.
- **G19 — Postgres / networked DB.** orion is Postgres-ready; LoopPlane has file + SQLite.
- **G20 — Concurrent multi-user execution.** orion is multi-tenant; LoopPlane has
  ownership scoping but not concurrent execution.
- **G21 — Model proxy / billing + server-side pricing.** orion has a transparent model
  proxy with per-user billing; LoopPlane has none.
- **G22 — Multi-level budget caps** (per-message / session / user-monthly USD). orion has
  these; LoopPlane has a single decide-stage budget policy (009).
- **G23 — Server-side SSE reconnect / resilience.** Deferred.

### Multimodal
- **G24 — PDF / `DocumentBlock` input.** LoopPlane's own deferral (ADR 0001 D2); does not
  map through OpenAI chat-completions and needs binary artifact durability.

## C3. Where LoopPlane is at parity or ahead

The comparison is not one-directional. LoopPlane leads on:

- **Spec-first governance** — a ratified constitution, per-unit specs / plans / tasks, and
  ADRs for every boundary crossing.
- **Determinism & safety posture** — deny-wins, fail-closed deciders; metadata-only,
  deterministic observability contracts (010); additive features that default to
  byte-identical behavior.
- **Loop engineering layer** — first-class validators / evaluators / retry / repair and a
  virtual-clock scheduler (003–005), which neither reference foregrounds as a reusable
  contract.
- **Clean boundaries** — a single Tool Gateway (V) and Event Bus (VI) with enforced
  import boundaries, making the runtime auditable and embeddable.

## C4. Forward roadmap (prioritized, tiered)

This extends the existing Tier framework (Tier-1 capability → Tier-2 autonomy → Tier-3
cost/safety → Tier-4 platform). It is a **suggested priority list only** — no unit below
is specced or implemented yet. Unit numbers are provisional (next free is 044).

**Tier-1 completion — small, high-value agent capability**
- TodoWrite / task-list tool (G1)
- Model-native structured output (G3)
- NotebookEdit (G2)
- A reference web-search provider behind an extra (G4)

**Tier-2 expansion — autonomy & workflow**
- Background / long-running task tools (G5)
- Agent-facing scheduling / cron tools wrapping the unit-004 scheduler (G6)
- Agent-to-agent messaging / swarm extending units 013 + 043 (G7)
- Worktree isolation (G8)

**Tier-3 — execution safety & cost**
- Sandbox execution (local / docker) for `run_command` (G11)
- Multi-level budget caps + server-side pricing (G22, G21)
- File-edit undo / rewind (G16)

**Tier-4 — platform & multi-tenant**
- OAuth / JWT + external IdP (G18)
- Postgres checkpoint backend (G19)
- Concurrent multi-user execution (G20)
- Server-side SSE reconnect (G23)
- MCP breadth: resources + SSE/WS transports + OAuth (G12)

**Parity / polish**
- Backend-semantic slash commands (G14), IDE extension (G13), STT/TTS (G15), output
  styles (G17), PDF / `DocumentBlock` (G24), remote execution (G9), named permission
  modes (G10).

> Promotion of any item into [`loopplane-agent-board.md`](loopplane-agent-board.md) §3 (the
> roadmap autopilot) is a separate, deliberate step so the autopilot is not driven by
> speculative units.
