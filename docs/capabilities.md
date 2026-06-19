# LoopPlane Capabilities

> A functional-scope overview of what LoopPlane provides today, derived from the unit
> specs (001–043) and verified against the source tree. For per-unit status and the
> roadmap autopilot, see [`loopplane-agent-board.md`](loopplane-agent-board.md); for the
> comparison against reference agent harnesses and the forward roadmap, see
> [`gap-analysis.md`](gap-analysis.md); for release history, see
> [`../CHANGELOG.md`](../CHANGELOG.md).

## What LoopPlane is

LoopPlane is a **spec-first, embeddable agent-harness runtime**. It drives a
"model ↔ tools" conversation loop through a single normalized **Event Bus** and a unified
**Tool Gateway**, and extends outward into loop automation, governance, multi-provider
model support, agent-capability tools, and full CLI / web / desktop host surfaces.

Units 001–043 are implemented and verified; the line is released as **v0.1.0 → v0.3.0**.

LoopPlane is built under a project constitution. The principles most visible in the
capability surface are:

- **Tool Gateway ownership (V)** — every tool resolve / authorize / execute / normalize
  flows through one chokepoint.
- **Event Bus ownership (VI)** — one normalized, versioned event stream is the only
  public observable; schema changes are versioned and tested.
- **Testable, reversible evolution (X)** — features are additive and default to
  byte-identical behavior (prompt caching, auto-compaction, and dynamic subagents are
  opt-in / off by default).
- **Reference, not clone (IX)** — claude-code-like concepts may inform the architecture
  but are re-derived through LoopPlane's own specs.

## Functional scope, by layer

| Layer | Units | What it provides | Packages |
| ----- | ----- | ---------------- | -------- |
| **Runtime core** | 001, 002, 021 | Agent loop (reason ↔ tool call ↔ result), unified Tool Gateway (internal + MCP), normalized Event Bus, durable checkpoint / resume (File + SQLite), memory, skill execution profiles, human-approval boundary, artifact storage, and the Host Application Interface (declarative `RuntimeConfig` + single entry point). | `loopplane.{controller,gateway,events,loop,memory,artifacts,approval,skills,checkpoint,host}` |
| **Loop engineering & automation** | 003–006 | Loop Definition + Controller (validate → evaluate → stop / retry / repair / human-review), an in-process scheduler (manual / interval / condition triggers on an injectable clock), reusable validator / evaluator packs, and human-review workflows. | `loopplane.{engineering,scheduling,packs,review}` |
| **Knowledge, governance & observability** | 007–010 | Memory recall + knowledge index with an injection policy and retrieval budget; an advanced tool gateway (catalog / plugin bundles / capability manifest / versioning / diagnostics — discovery only, never execution); sandbox / policy deciders (permission / path / budget / quota / capability, deny-wins); and metadata-only observability (diagnostics / trace / timeline / replay). | `loopplane.{recall,toolkit,governance,inspect}` |
| **Multi-agent** | 013, 043 | Host-driven orchestration (agent registry + coordinator + aggregated event / artifact views) and model-driven one-shot subagents (`spawn_subagent`, with a hard recursion-depth cap and failure containment). | `loopplane.orchestration`, `loopplane.tools.subagent` |
| **Model providers** | 020, 035, 037 | Anthropic and OpenAI native adapters; OpenRouter and Ollama (reusing the OpenAI wire format); and a native Google Gemini adapter. Each provider is behind its own optional extra and registers with the `/v1/models` selector. | `loopplane.adapters.{anthropic,openai,openai_compat,gemini}` |
| **Agent-capability tools** | 033, 034, 036 | File tools (`edit_file`, `glob_files`, `grep`); web tools (`web_fetch`, `web_search`) with default-deny network-egress governance; and multimodal image input (`ImageBlock`) with `accepts_media()` capability negotiation. | `loopplane.tools.{internal,web}`, `loopplane.model` |
| **Autonomy & workflow** | 038, 039 | Plan mode (read-only investigation → human approval → execute) and a declarative permission rule DSL (host-supplied allow / deny / ask rules), both enforced at the Tool Gateway decide stage. | `loopplane.governance.{plan_mode,rule_dsl}` |
| **Cost & efficiency** | 040–042 | Anthropic prompt caching (explicit stable-prefix breakpoints), configurable proactive auto-compaction (threshold-based), and an optional fail-safe cheap-model compaction summarizer. | `loopplane.adapters.anthropic`, `loopplane.loop` |
| **Extensibility** | 015, 016 | A lifecycle hook system (a registry + eleven lifecycle points; two gating points may gate / modify) and a manifest-based plugin system bundling skills + namespaced MCP servers + hooks behind an enable-list. | `loopplane.{hooks,plugins}` |
| **Host surfaces** | 011, 012, 017–019, 022, 023 | A web / API host (REST + SSE) with principal authentication and per-principal session scoping; an in-process studio / desktop host; a CLI host; a from-scratch web SPA with a login flow; and an Electron desktop GUI over a local sidecar bridge. | `loopplane.{webapi,studio,cli}`, `apps/web`, `apps/desktop` |
| **Web UI product experience** | 025–032 | A modern agent UI: markdown + collapsible tool cards + theming + two-pane shell + stop control (025); reasoning / question-options / token-usage signals (026); read-only inspection panels (027); model selection + file attachments (028); i18n + syntax highlighting + command palette + cost estimate (029); session management (030); message actions (031); and interaction resilience — modals / retry / toasts / skeletons (032). | `apps/web` |
| **Packaging & release** | 014, 024 | Release packaging and docs (wheel / sdist, `py.typed`, public API reference, CI gates) and desktop packaging (a PyInstaller-frozen sidecar + electron-builder + a spawn resolver). | packaging metadata, `apps/desktop` |

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
| `web_fetch` | Fetch an http(s) URL to readable text (network-gated). | — |
| `web_search` | Query a host-injected search provider (network-gated). | — |
| `read_upload` | Read an uploaded attachment by id (web/API). | yes |
| `spawn_subagent` | Delegate a bounded sub-task to one child agent (opt-in). | no |

> Tool calls run concurrently where safe: the loop batches concurrency-safe calls in
> parallel and runs the rest sequentially.

**Model providers:** Anthropic, OpenAI, OpenRouter, Ollama, and native Google Gemini —
each behind its own optional install extra; OpenRouter additionally brokers 100+ models
behind the OpenAI wire format.

## Scope boundaries (out of scope / deferred)

The following are intentionally **not** in scope today (each is recorded in the relevant
spec / ADR or roadmap):

- **Multimodal:** PDF / `DocumentBlock` input (deferred, ADR 0001 D2) and binary
  artifact durability.
- **Gemini:** real per-call `thought_signature` preservation (multi-turn tool use works
  today via Google's official validator-skip sentinel).
- **Commands & pricing:** backend-semantic slash commands; authoritative server-side
  pricing (the web UI shows a client-side cost estimate only).
- **Multi-agent:** agent-to-agent messaging, swarm / peer coordination, and persistent /
  named / background subagents.
- **Identity & multi-tenancy:** OAuth / JWT and external identity providers (the auth
  boundary takes a host-injected verifier); concurrent multi-user execution; networked
  database backends.
- **Execution isolation:** OS / container sandboxing of tool execution (governance is a
  decision layer; `run_command` runs within the working scope on the host).
- **Editing & history:** prior-message editing / conversation branching, in-session
  message search, and file-edit undo beyond checkpoint / resume.

For where these sit relative to reference agent harnesses and a prioritized way to close
them, see [`gap-analysis.md`](gap-analysis.md).

## Note on spec status

The per-unit `specs/*/spec.md` files are marked `Status: Draft` even though every unit
(001–043) is implemented, verified, and released. The marker reflects the spec template
default, not the implementation status; the authoritative per-unit status lives in
[`loopplane-agent-board.md`](loopplane-agent-board.md) (all units **Verified**) and the
release history in [`../CHANGELOG.md`](../CHANGELOG.md).
