# Reference Analysis: LoopPlane Runtime Foundation

**Feature**: [spec.md](./spec.md)

**Created**: 2026-06-13

**Updated**: 2026-06-13 — full audit pass against the private reference baseline; structure
corrections, source-of-truth ranking added, capability and extraction tables normalized.

**Provenance & sanitization**: This analysis is derived from a local, private OpenSpec-style
architecture baseline kept under the untracked `openspec/` directory (a reference runtime built
and validated previously). Per the project constitution (Principles II, VII, IX), this document
rewrites *intent only*: it contains no private project names, no internal paths, no copied
implementation code, and references the source material only at module-topic and
requirement-topic granularity. The raw reference is never committed.

---

## 1. OpenSpec Structure Map

Layout of the private reference baseline (topics only, codenames removed):

```text
openspec/                          # untracked private reference — never committed
├── freeze/
│   └── current-baseline.md        # overall status: frozen decisions, per-module status
│                                  # table, milestone history, applied change requests
├── modules/                       # 19 modules, each with the same 5 documents:
│   ├── 01-model-layer/            #   proposal.md   — why the module exists, scope
│   ├── 02-agent-loop/             #   design.md     — locked design decisions
│   ├── 03-tool-system/            #   spec.md       — testable requirements + scenarios
│   ├── 04-permission-system/      #   study-note.md — research notes on prior art
│   ├── 05-session-storage/        #   tasks.md      — implementation task breakdown
│   ├── 06-memory-system/
│   ├── 07-hook-system/
│   ├── 08-skill-system/
│   ├── 09-cli-host/
│   ├── 10-web-api-host/
│   ├── 11-react-frontend/
│   ├── 12-mcp-extension-layer/
│   ├── 13-sandbox-execution-layer/
│   ├── 14-cost-governance/
│   ├── 15-multi-agent/
│   ├── 16-knowledge-indexing/
│   ├── 17-plugin-system/
│   ├── 18-telemetry/
│   └── 19-desktop-host/
└── changes/                       # 9 applied change requests; 8 carry the full set
    └── <change-name>/             #   (reason / diff / migration / post-update-spec),
                                   #   1 is reason-only (fix absorbed directly into the
                                   #   owning module's spec)
```

Conventions observed in the reference:

- **Requirement format**: each module `spec.md` is organized as `Requirement N: <topic>`
  with numbered Given/When/Then scenarios (`Scenario N.M`). Later amendments carry
  module-prefixed requirement IDs (e.g. agent-loop AL9–AL15, session-storage SS15–SS19,
  telemetry TEL12).
- **Lifecycle**: specs move DRAFT → LOCKED → APPLIED; a LOCKED decision may only change
  through a recorded change request (reason + diff + migration + post-update spec).
- **Milestones**: the reference was built inside-out across milestones (conversation core →
  tool-using agent → memory → CLI host → web host), then extended with optional layers
  (MCP, sandbox, cost, multi-agent, recall, plugins, telemetry, desktop host), each gated to
  produce zero behavior change when disabled. A late cross-cutting amendment wave
  ("reliable long tasks") patched the core modules with typed conversation content,
  compaction, large-result offload, and stale-write guards.

Currency assessment (which areas are current vs historical vs implementation-specific):

- **Current**: the freeze/baseline document (status authority, updated through the final
  milestone); all 19 module `spec.md` files (every one LOCKED, several carrying applied
  amendment IDs); all 9 change requests (every one APPLIED and absorbed into the owning
  module specs). Nothing in the reference is superseded by anything newer.
- **Historical (context only)**: the per-module `study-note.md` files — prior-art research
  written before each module was designed. Useful for understanding *why* decisions were
  made; never used as an extraction source.
- **Implementation-specific (not portable)**: package/file layouts, tooling and dependency
  choices, and concrete code paths cited in `design.md`/`tasks.md`; the host modules'
  product surfaces (authentication, REST endpoints, UI components, desktop app shell,
  container runtime mechanics). Extraction takes requirement and architecture intent only.

## 2. Source-of-Truth Ranking

Ranking used to drive the conversion. Where documents disagreed, the higher rank won.

| Rank | Source | Why it ranks here |
|---|---|---|
| 1 | Freeze / baseline document | The only document that records what is actually LOCKED and APPLIED, per-module status, milestone history, and which change requests are absorbed. Used to confirm currency of everything below. |
| 2 | Module `spec.md` files (with applied amendments) | The testable requirements as they stand *after* every change request was absorbed; the primary extraction source for LoopPlane functional requirements. |
| 3 | Applied change requests (reason + post-update spec) | Authority for *why* behavior changed and for late vocabulary/behavior corrections (event types, error-path privacy, orphan-input repair). Used to verify the amended module specs were read correctly. |
| 4 | Module `design.md` files | Locked design decisions and architecture intent (boundaries, ownership, ordering rules). Drives the architecture-intent summary and the plan, not the spec's requirements. |
| 5 | Module `proposal.md` / `tasks.md` files | Scope rationale and milestone sequencing; informs phasing and the incremental delivery strategy only. |
| 6 | Module `study-note.md` files | Prior-art research predating design; lowest authority, never extracted from directly. |

## 3. Capability Map

How reference capabilities map onto LoopPlane. **Decision** is one of: Keep in foundation /
Minimal contract only / Defer / Drop as legacy-specific / Needs clarification.

| Capability | OpenSpec Source Area | Extracted Intent | LoopPlane Area | Decision | Reason |
|---|---|---|---|---|---|
| Agent loop core | agent-loop module (incl. applied long-task amendments) | Turn cycle with enumerated terminal reasons; non-raising cancellation; concurrency-safe tool batching; stateful history with immutable snapshots; compaction with one overflow retry; pristine prompt assembly | Agent Loop | Keep in foundation | The core of the harness; every other component and future layer attaches to it |
| Transport-agnostic session driver | desktop-host module (shared driver portion) + web-api-host module (round-trip handling) | Session round-trip over abstract send/receive channels; pending-interaction registry keyed by request id; disconnect semantics; history replay; increment coalescing without reordering | Runtime Controller / Dispatcher | Keep in foundation | The reference proved host parity by sharing one driver; LoopPlane needs it before any host exists |
| Unified tool execution path | tool-system + permission-system interception + MCP-layer execution rules | Registry, resolution, input validation, policy decision, execution, timeout, error normalization, and output-size management as one pipeline | Tool Gateway | Keep in foundation | Constitution Principle V requires a single governable chokepoint; the reference spread these across loop/tool/permission seams |
| Internal tool contract & baseline tools | tool-system module | One declarative tool contract (name, description, input schema, streaming text/image/error outputs); conservative safety defaults; baseline file/search/command/ask-user tools; stale-write guard on file modification | Internal Tool Adapter | Keep in foundation | Minimum demonstrable tool set; the contract is what the Gateway governs |
| External tool servers | mcp-extension-layer module | Layered configuration with scope override and malformed-entry tolerance; connection lifecycle; source-qualified names; per-server failure isolation; schema translation with safe fallback; identical governance to internal tools | MCP Tool Adapter | Keep in foundation | The control plane's first external integration surface, governed through the same Gateway |
| Declarative skills | skill-system module | Declarative instruction packages with metadata; structure/size validation with skip-on-malformed; deterministic multi-source merge; incremental advertisement within a prompt budget; closed-list variable substitution; invocation controls; post-compaction re-establishment | Skill Execution Profile | Keep in foundation | Reshaped: the reference's invocation/safety toggles become an explicit execution profile honored by Gateway and approval |
| Normalized runtime events | agent-loop events + web-api-host wire schema + desktop-host shared event layer | Closed, versioned vocabulary; loop emits normalized events only; consumers adapt on their side; unknown types skipped; lossless serialization; replay includes past user prompts | Runtime Event Bus | Keep in foundation | Constitution Principle VI: one normalized spine for streaming, history, trace, and observability |
| Durable memory | memory-system module | Typed durable entries; malformed-entry resilience; relevance ranking with deterministic fallback; assembly-time injection that keeps durable history verbatim; agent-writable via a governed tool | Memory | Keep in foundation | Makes the harness useful for real work; proven gateway-governable in the reference |
| Session records & resume | session-storage module (core) | Append-as-you-go records; resume from records alone; dangling-call repair with warnings; corrupted-record skip; concurrent-write safety; session listing by recency | Checkpoint | Keep in foundation | Durability is the precondition for long, loop-engineered work |
| Oversized-result offload | session-storage module (large-result amendments) | Threshold-based artifact persistence; in-conversation preview plus stable reference; aggregate budget with largest-first replacement frozen across resume; persistence boundary outside the loop | Artifact Storage | Keep in foundation | Long tasks fail without bounded conversations; an applied amendment, current behavior |
| Metadata-only telemetry | telemetry module (incl. applied error-path hardening change) | Off-by-default with zero behavior change; nested run/turn/call trace with durations; low-cardinality usage metrics; strictly metadata-only including error paths (error type only) | Observability | Keep in foundation | The operating signal for a control plane; the privacy guarantee is load-bearing |
| Tool authorization & human escalation | permission-system module + ask-user change request | Allow/deny/ask decision before every execution; denial as data; structured ask round-trip; single-use vs session-scoped decisions; persistent rules with scope precedence; disconnect resolves pending as denied; non-permission questions over the same machinery | Human Approval | Keep in foundation | The control plane's first safety promise |
| Loop-engineering extension surface | — (no reference source; derived from constitution Principle III) | Passive event subscription plus session lifecycle as the sanctioned attachment surface for future scheduler/validator/evaluator layers | Future-Layer Extension Points | Keep in foundation | The foundation must leave sanctioned seams without implementing automation |
| Model access | model-layer module | Provider abstraction; normalized streaming increments; per-turn token usage; context-capacity metadata; typed conversation content including a compaction summary marker | Model boundary (supporting) | Minimal contract only | The loop needs a seam to drive models and tests need a scripted substitute; provider integrations are not a phase-1 deliverable |
| Lifecycle hooks | hook-system module | Interception points around tool execution, prompts, and session lifecycle, with blocking/mutation capability | Future hook layer | Defer | The foundation's event vocabulary already covers the same observation points; interception is a future layer attaching at Gateway/Bus seams |
| Interactive terminal host | cli-host module | A REPL host consuming the loop's event stream | Future host phase | Defer | Pure consumer of the public surface; the reference confirms it required zero core changes |
| Multi-user network host | web-api-host module (routes, auth, persistence, multi-tenant session registry) | An authenticated multi-session network host | Future host phase | Defer | Host/transport concern; only its event and round-trip intent is extracted (see driver and event rows) |
| Browser frontend | react-frontend module | A web UI consuming the wire schema | Future host phase | Defer | Presentation layer only |
| Desktop host shell | desktop-host module (app-shell portion) | A desktop application wrapping the shared driver | Future host phase | Defer | App-shell concern; the shared-driver intent is already extracted |
| Execution isolation | sandbox-execution-layer module | Containerized command execution and workspace path policy beneath the tool layer | Future hardening phase | Defer | Gateway timeout/error/policy boundaries suffice for phase 1; the reference confirms no loop coupling |
| Cost & budget governance | cost-governance module | Per-model usage accumulation, price catalog, budget warnings and stops | Future governance layer | Defer | Attaches to usage data already exposed by turn-completion events and metrics |
| Sub-agent orchestration | multi-agent module + agent-spawning tool in tool-system | Typed sub-agent registry, depth-limited spawning, usage rollup to the parent | Future orchestration layer | Defer | Builds on a working harness; the phase-1 baseline tool set deliberately excludes the agent-spawning tool |
| Conversation recall | knowledge-indexing module | Search over past session records via opt-in tools | Future layer | Defer | Builds on Checkpoint records and listing; optional tools with zero core changes |
| Plugin packaging | plugin-system module | Manifest bundles distributing skills and tool-server configurations | Future distribution layer | Defer | Pure packaging/discovery above skills and external-tool config; no runtime coupling |
| Task-progress tool | tool-system module (task-list tool) | A built-in task-list tool for agent self-tracking | Future baseline-tool addition | Defer | Not needed to demonstrate the harness; the spec's baseline set is "at minimum" |
| Per-user editable remote tool-server config | MCP web-editing change request | Web endpoints for per-user external-server CRUD with transport restrictions | — | Drop as legacy-specific | Multi-tenant product policy of the old web host; re-derive if/when a multi-user host phase is specified |
| Host parity REST endpoints | web-parity change request | Model catalog, cost, memory, settings, file listing, and upload endpoints | — | Drop as legacy-specific | Product surface of the old web host, not portable runtime intent |
| Host authentication & database persistence | web-api-host module (auth/persistence requirements) | Token-based auth and a relational session index | — | Drop as legacy-specific | Deployment-specific choices; the foundation stays storage-light and host-free |
| Desktop packaging pipeline | desktop-host module (packaging portion) | Application packaging and distribution mechanics | — | Drop as legacy-specific | Build tooling of the old product |

No capability required **Needs clarification**: every open question had a defensible working
default, recorded in §6 and resolved in [research.md](./research.md).

## 4. Requirement Extraction Table

Mapping from reference requirements (topic level) to public-safe LoopPlane requirements.
Target artifacts: [spec.md](./spec.md) (FR/NFR), [contracts/](./contracts/),
[data-model.md](./data-model.md).

| Reference Topic | Extracted Intent | Public-Safe Requirement | Target Artifact | Notes |
|---|---|---|---|---|
| agent-loop → turn cycle & natural termination | One terminal event per run with enumerated reasons and turn count | FR-001 | spec.md; contracts/runtime-events.md | |
| agent-loop → event emission across the loop | Deterministic normalized event ordering for every observable step | FR-002 | spec.md; contracts/runtime-events.md | |
| agent-loop → cancellation pre-turn and mid-stream | Prompt, non-raising cancellation ending in a "cancelled" terminal event | FR-003 | spec.md | |
| agent-loop → unknown tool / tool exception handling | Failures become error-marked results; the run continues | FR-004 | spec.md | |
| agent-loop → concurrency-safe tool batching | Parallel only when declared safe; deterministic per-call event order | FR-005 | spec.md; contracts/tool-gateway.md | |
| agent-loop → stateful conversation + snapshots | History continuity across turns; immutable point-in-time snapshots | FR-006 | spec.md | |
| agent-loop → empty-turn orphan-input fix | No stranded user input that breaks role alternation | FR-007 | spec.md | applied change request (reason-only; absorbed into module spec) |
| agent-loop → compaction + context-overflow retry | Summarize without splitting a call from its result; exactly one retry | FR-008 | spec.md | applied long-task amendment |
| agent-loop → prompt assembler with pristine persisted input | Augmentation at assembly time; durable history keeps verbatim input | FR-073 | spec.md; contracts/memory.md | applied long-task amendment |
| agent-loop → execution context | Per-run context carries identity, working scope, cancellation, budgets, session approval memory | Run Context entity | data-model.md | applied context-extension change |
| desktop-host → transport-agnostic round-trip driver | Same driver serves any host via abstract channels | FR-010, FR-011 | spec.md; contracts/run-lifecycle.md | |
| web-api-host + desktop-host → pending interaction round-trips | Request-id-matched pending registry for approvals and questions | FR-012, FR-116 | spec.md; contracts/approval.md | |
| desktop-host → disconnect/EOF semantics | Cancel cleanly; deny all pending approvals; never hang | FR-013, FR-115 | spec.md; contracts/run-lifecycle.md | |
| web-api-host → history replay incl. past user prompts | Full visible-conversation reconstruction on reattach | FR-014 | spec.md; contracts/runtime-events.md | applied change request |
| web-api-host → output coalescing & replay batching | Batch increments without reordering; flush before non-increments | FR-015 | spec.md; contracts/runtime-events.md | |
| tool/permission/MCP seams → unified execution path | Single Gateway chokepoint; no bypass; registry + name resolution | FR-020, FR-021 | spec.md; contracts/tool-gateway.md | unification is a LoopPlane decision (constitution V) |
| tool-system → input schema strictness | Undeclared parameters rejected before execution | FR-022 | spec.md; contracts/tool-gateway.md | |
| permission-system → pre-execution interception | A policy decision precedes every execution | FR-023, FR-110 | spec.md; contracts/approval.md | |
| tool-system → per-call timeout | Generalized per-call time limit at the Gateway | FR-024 | spec.md; contracts/tool-gateway.md | reference applied it per command-tool; generalized here |
| tool/MCP boundaries → error conversion | One normalized error-result shape; no raw leakage | FR-025 | spec.md; contracts/tool-gateway.md | |
| tool-system → large-output truncation | Output-size management with artifact handoff | FR-026 | spec.md; contracts/artifacts.md | |
| tool-system → tool contract (streaming text/image/error) | Single internal tool contract; error output marks the call failed | FR-030, FR-032 | spec.md; contracts/tool-gateway.md | |
| agent-loop → conservative safety defaults | Not concurrency-safe / not read-only unless declared | FR-031 | spec.md | |
| tool-system → baseline tool set + ask-user tool | Minimum demonstrable tool set, available only through the Gateway | FR-033 | spec.md | ask-user tool arrived via an applied change request |
| tool-system → file-state safety | Editing/overwriting requires a fresh same-session read; stale writes fail | FR-034 | spec.md | applied long-task amendment; audit addition |
| mcp-extension → layered config with malformed-entry tolerance | Scope override; a bad entry disables only itself | FR-040 | spec.md; contracts/tool-gateway.md | |
| mcp-extension → client/manager lifecycle | Connect, discover, invoke, clean shutdown | FR-041 | spec.md | |
| mcp-extension → qualified tool naming | Source-qualified names prevent collisions | FR-042 | spec.md | |
| mcp-extension → per-server failure isolation | One server's failure leaves the rest available | FR-043 | spec.md | |
| mcp-extension → schema translation with safe fallback | External schemas mapped into the validation model | FR-044 | spec.md; contracts/tool-gateway.md | |
| mcp-extension → permission integration | External tools governed exactly like internal ones | FR-045 | spec.md | |
| skill-system → declarative package + structure/size guards | Skill is metadata + instructions; malformed/oversize skipped safely | FR-050, FR-051 | spec.md | |
| skill-system → multi-source registration, last-wins | Deterministic merge; the more specific source wins | FR-052 | spec.md | |
| skill-system → delta-only listing within budget | Incremental advertisement to the model | FR-053 | spec.md | |
| skill-system → post-compaction re-establishment | Advertised/invoked skill content survives compaction without double budget cost | FR-053 + edge case | spec.md | applied long-task amendment; audit addition |
| skill-system → closed-list variable substitution | Runtime variables substituted; unknown ones pass through literally | FR-054 | spec.md | |
| skill-system → invocation controls | Reshaped into an explicit execution profile honored by Gateway/approval | FR-050, FR-055 | spec.md | |
| loop events vs wire events split | Loop emits normalized only; consumers adapt on their side | FR-060–FR-062 | spec.md; contracts/runtime-events.md | |
| web-api-host → reasoning increments + diagnostic events | Reasoning output streams as its own increment kind; non-fatal failures surface as diagnostics | FR-060 | contracts/runtime-events.md | audit addition |
| agent-loop → turn completion carries usage | Per-turn token usage rides the turn-completion event | FR-060, FR-102 | contracts/runtime-events.md; contracts/model-boundary.md | feeds the future cost layer without new coupling |
| web-api-host → adapter "unknown type → skip" rule | Forward-compatible consumers | FR-063 | spec.md; contracts/runtime-events.md | |
| web-api-host → wire schema round-trip safety | Lossless serialization across a process boundary | FR-064 | spec.md; contracts/runtime-events.md | |
| reference change-control workflow | Event vocabulary changes are governed contract changes | FR-065 | spec.md; contracts/runtime-events.md | |
| memory-system → typed entries, scan resilience | Durable typed memory; malformed entries skipped | FR-070, FR-071 | spec.md; contracts/memory.md | |
| memory-system → relevance ranking with fallback | Deterministic fallback ordering when ranking is unavailable | FR-072 | spec.md; contracts/memory.md | |
| memory-system → memory-write tool | Agent-writable memory through the Gateway | FR-074 | spec.md; contracts/memory.md | |
| session-storage → append-as-you-go records | Durable, immediate, append-only recording | FR-080 | spec.md; contracts/checkpoint.md | |
| session-storage → resume from records (+ typed normalization) | State reconstruction from records alone | FR-081 | spec.md; contracts/checkpoint.md | applied long-task amendment |
| session-storage → dangling tool-call repair | Synthetic error result plus a surfaced warning | FR-082 | spec.md; contracts/checkpoint.md | |
| session-storage → corrupted-record skip | Partial damage never loses the session | FR-083 | spec.md; contracts/checkpoint.md | |
| session-storage → concurrent write safety | No interleaving within a session | FR-084 | spec.md; contracts/checkpoint.md | |
| session-storage → session listing with recency | Identity + recency metadata, newest first | FR-085 | spec.md; contracts/checkpoint.md | |
| session-storage → large-result offload | Threshold-based artifact persistence with preview + reference | FR-090, FR-091 | spec.md; contracts/artifacts.md | applied long-task amendment |
| session-storage → aggregate budget + frozen replacement | Largest-first replacement; decisions stable across resume | FR-092 | spec.md; contracts/artifacts.md | applied long-task amendment |
| session-storage → recorder boundary | The loop never persists directly; deltas flow through the recording boundary | FR-094 | spec.md; contracts/checkpoint.md | |
| telemetry → off-by-default gate | Zero behavior change when disabled | FR-100 | spec.md | |
| telemetry → nested run/turn/call spans + durations | Trace of timed steps | FR-101 | spec.md | |
| telemetry → usage counters, low-cardinality labels | Metrics without label explosion (no per-session labels) | FR-102 | spec.md | |
| telemetry → metadata-only incl. error paths | No content, no exception messages or stack traces; error type only | FR-103 | spec.md | applied change request |
| telemetry → "execution failures only" error metric | Policy denials are not execution failures | FR-104 | spec.md | |
| permission-system → deny-with-reason as data | Denial returns an explained error result; the run continues | FR-111 | spec.md; contracts/approval.md | |
| permission-system → ask policy + decision scopes | Structured escalation; single-use vs session-scoped memory | FR-112, FR-113 | spec.md; contracts/approval.md | applied permission-callback change |
| permission-system → persistent rules with precedence | More local scope over broader; deny over allow within a scope | FR-114 | spec.md; contracts/approval.md | |
| model-layer → provider abstraction + normalized streaming | The loop drives models through one streaming seam | Assumptions; model boundary | contracts/model-boundary.md | minimal contract only |
| model-layer → token accounting & capabilities | Per-turn usage and context capacity exposed by the boundary | Assumptions | contracts/model-boundary.md; data-model.md | consumed by FR-008/FR-102 |
| model-layer → typed conversation content | Content blocks are typed, including a compaction summary marker | Content Block entity | data-model.md | applied long-task amendment |
| — (constitution Principle III) | Extension surface for future layers; no automation now | FR-120–FR-122 | spec.md; contracts/runtime-events.md | not sourced from the reference |

## 5. Architecture Intent Summary

The reference baseline encodes the following architecture intent, which LoopPlane re-derives
(reference-informed, not cloned — constitution Principles VIII & IX):

1. **Inside-out construction.** Build the model boundary first, then the loop, then tools,
   then hosts. The runtime core never depends on any host, transport, or UI.
2. **Core/host separation via an abstract driver.** The session round-trip is driven through
   abstract send/receive channels, so CLI, web, desktop, or scheduler hosts reuse one driver
   instead of reimplementing loop wiring.
3. **One normalized event stream as the spine.** The loop emits a closed vocabulary of
   runtime events; streaming, history, replay, step display, tracing, and observability are
   all downstream consumers. Frontend formatting never happens inside the loop.
4. **A single tool chokepoint with policy interception.** Registration, resolution,
   validation, authorization, execution, timeout, output management, and error normalization
   happen in one place. Denial is data (an error result the model can react to), not an
   exception that kills the run.
5. **Conservative defaults.** Tools are assumed unsafe to parallelize and not read-only
   unless declared otherwise; optional subsystems (observability, memory, skills, external
   tools) are off by default and must produce zero behavior change when disabled.
6. **Durability before features.** Every step is recorded as it happens; a session can be
   reconstructed from its records alone; inconsistencies are repaired and surfaced rather
   than failed; the user's verbatim input is preserved through any prompt augmentation.
7. **Large content leaves the conversation.** Oversized tool results are offloaded to
   artifact storage and replaced by previews with stable references, under an aggregate
   budget whose decisions stay frozen across resume. The loop itself never owns persistence.
8. **Metadata-only observability.** Traces and metrics carry structure (durations, counts,
   types) and never content — a guarantee that explicitly covers error paths (exception
   types only, never messages or stack traces).
9. **Change control as a first-class practice.** Locked decisions change only through
   recorded change requests; LoopPlane mirrors this through its constitution governance and
   spec-first workflow.

Per-area support status (areas the conversion was asked to cover):

| Area | Reference support | Notes |
|---|---|---|
| Agent Harness Runtime | Supported | The whole baseline is one harness runtime built inside-out |
| Agent Loop | Supported | Dedicated module, amended for long-task reliability |
| Runtime Controller / Dispatcher | Supported indirectly | The reference implemented lifecycle inside hosts and extracted a shared round-trip driver late; LoopPlane names both roles explicitly from the start (divergence recorded per Principle IX) |
| Tool execution | Supported | Tool contract + execution rules in the tool module |
| Tool Gateway | Intent supported, shape is LoopPlane's | The reference spread gateway concerns across loop/tool/permission seams; unification follows constitution Principle V |
| MCP adapter | Supported | Dedicated module |
| Internal tool adapter | Supported | Tool contract + baseline tools |
| Permission / approval boundary | Supported | Dedicated module plus applied change requests |
| Skill / execution profile | Supported, reshaped | "Execution profile" is LoopPlane's name for the reference's invocation/safety controls |
| Runtime event model | Supported | Loop events + wire schema + replay rules across two modules and three change requests |
| Streaming / history / trace | Supported | All modeled as consumers of the normalized stream |
| Memory | Supported | Dedicated module |
| Checkpoint | Supported | Session-storage module core |
| Artifact storage | Supported | Session-storage large-result amendments |
| Observability | Supported | Telemetry module with privacy hardening |
| Future loop-engineering extension points | **Not in the reference** | Derived from LoopPlane constitution Principle III; deliberately marked as LoopPlane-originated, not extracted |

## 6. Ambiguity List

Open questions deliberately *not* resolved by the spec. Each has a working default recorded
in the spec's Assumptions and a resolution in [research.md](./research.md):

| ID | Area | Ambiguity | Why It Matters | Working Default | Blocks Plan? |
|---|---|---|---|---|---|
| A1 | Skill Execution Profile | Which constraint fields does the profile carry in phase 1 (invocation toggle, approval class, tool restrictions, isolation mode)? | Determines how tightly the Gateway and approval boundary couple to skills | Profile minimally controls autonomous invocation + approval requirement (FR-055); richer fields deferred | No — resolved in research.md (A1) |
| A2 | Controller / Dispatcher boundary | One component or two? The reference merged host session management with the round-trip driver late in its life | Affects the public embedding API and where pending interactions live | Two named roles: Controller owns lifecycle (FR-010), Dispatcher owns the round-trip (FR-011–FR-015); may share a subsystem | No — resolved in research.md (A2) |
| A3 | Artifact thresholds & budgets | Fixed defaults vs configurable per deployment | Affects test design and host configuration surface | Configurable threshold + budget with sane defaults (FR-090, FR-092) | No — defaults set in research.md (A3) |
| A4 | Event versioning mechanism | Envelope version field vs per-type versions vs additive-only evolution | Event schema is the runtime's most public contract | Envelope carries a schema version; evolution is additive within a major version (FR-065) | No — resolved in research.md (A4) |
| A5 | Memory relevance ranking | Deterministic heuristic only, or a pluggable ranker seam now? | Ranking quality vs determinism and test stability | Lexical heuristic with deterministic fallback (FR-072); pluggability deferred | No — resolved in research.md (A5) |
| A6 | Compaction summary production | Mechanical summarization vs model-generated summaries in phase 1 | Cost, determinism, and test reproducibility | Mechanical summary marker (FR-008); model-generated summaries deferred | No — resolved in research.md (A6) |
| A7 | Future-layer attachment shape | Passive event subscription only, or an active control surface (pause/inject/steer)? | Defines the extension contract future layers depend on | Passive subscription + session lifecycle only (FR-120, FR-122) | No — resolved in research.md (A7) |
| A8 | Concurrent session consumers | Can an observer attach to a live session alongside the driving consumer? | Affects Dispatcher channel and event fan-out design | Single driving consumer per session; concurrent observers deferred | No — resolved in research.md (A8) |
| A9 | External-server transports | Local-process servers only, or also remote HTTP transports? | Affects adapter configuration schema and failure modes | Both local-process and remote streaming-HTTP transports accepted via config (FR-040–FR-041) | No — resolved in research.md (A9) |
| A10 | Checkpoint storage ownership | Runtime-owned default location vs host-supplied | Affects embedding API and test isolation | Runtime-owned default, host-overridable | No — resolved in research.md (A10) |
