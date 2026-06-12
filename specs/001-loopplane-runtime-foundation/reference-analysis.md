# Reference Analysis: LoopPlane Runtime Foundation

**Feature**: [spec.md](./spec.md)

**Created**: 2026-06-13

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
│   └── current-baseline.md        # overall status: frozen decisions, module states,
│                                  # milestone history, applied change requests
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
└── changes/                       # 9 applied change requests, each with:
    └── <change-name>/             #   reason.md / diff.md / migration.md /
                                   #   post-update-spec.md
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
  produce zero behavior change when disabled.

## 2. Capability Map

How reference modules map onto LoopPlane Phase 1 components:

| Reference module (topic) | LoopPlane Phase-1 component | Disposition | Notes |
|---|---|---|---|
| 02 agent-loop | **Agent Loop boundary** | Extract | Turn cycle, terminal reasons, cancellation, tool batching, stateful conversation, compaction, pristine-input prompt assembly |
| 19 desktop-host (shared driver portion) + 10 web-api-host (wire schema / adapter / interaction round-trips) | **Runtime Controller / Dispatcher** | Extract (driver intent only) | Transport-agnostic session round-trip driver over abstract send/receive channels; pending-interaction registry; disconnect semantics; replay; coalescing. Hosts themselves are out of scope |
| 03 tool-system (registry, execution, timeout, truncation, error conversion) + 04 permission interception point | **Tool Gateway** | Extract & unify | Constitution Principle V requires one chokepoint; reference spread these across loop/tool/permission seams |
| 03 tool-system (tool contract + baseline tools) | **Internal Tool Adapter** | Extract | Streaming tool contract (text/image/error outputs), conservative safety defaults, baseline tool set |
| 12 mcp-extension-layer | **MCP Tool Adapter** | Extract | Layered config, connection lifecycle, qualified naming, per-server failure isolation, schema translation fallback, same permission path as internal tools |
| 08 skill-system | **Skill Execution Profile** | Extract & reshape | Frontmatter parsing, two-source last-wins merge, delta listing within budget, closed-list variable substitution, invocation controls → reshaped into an explicit "execution profile" concept |
| 02 loop events + 10 wire events/adapter + 19 shared event layer | **Runtime Event Bus** | Extract & unify | Constitution Principle VI: one normalized vocabulary; loop never formats for frontends; replay includes past user prompts; consumers adapt and tolerate unknown types |
| 06 memory-system | **Memory** | Extract | Typed durable entries, malformed-entry resilience, relevance ranking with deterministic fallback, prompt-assembly injection, agent-writable via tool |
| 05 session-storage (core) | **Checkpoint** | Extract | Append-as-you-go records, resume from records alone, dangling-call repair with warnings, corrupted-record skip, concurrency safety, session listing |
| 05 session-storage (large-result amendments) | **Artifact Storage** | Extract | Oversized-result offload, preview + reference marker, aggregate budget with largest-first replacement, frozen decisions across resume, persistence boundary outside the loop |
| 18 telemetry | **Observability** | Extract | Off-by-default zero-behavior-change gate, nested run/turn/call trace, usage metrics with low-cardinality labels, strict metadata-only guarantee including error paths |
| 04 permission-system | **Human Approval boundary** | Extract | allow/deny/ask policies, structured ask round-trip, once vs session-scoped decisions, persistent rules with scope precedence (local wins; deny over allow), disconnect ⇒ deny pending |
| 01 model-layer | (supporting) model access boundary | Fold in | Provider abstraction + normalized streaming consumed by the Agent Loop; treated as an assumption/boundary of the loop, not a Phase-1 component |
| — (no reference module) | **Future scheduler / validator / loop-engineering layer** | Define extension points only | Constitution Principle III: not implemented in Phase 1 |
| 07 hook-system | — | Defer | Future phase; lifecycle interception not needed for foundation |
| 09 cli-host / 10 web-api-host (routes, auth, multi-tenant) / 11 frontend / 19 desktop-host (app shell) | — | Defer | Hosts and UIs are future phases; only the transport-agnostic driver intent is extracted |
| 13 sandbox-execution-layer | — | Defer | Execution isolation is a future hardening phase; Gateway timeout/error boundaries suffice for Phase 1 |
| 14 cost-governance | — | Defer | Budget/cost layers attach later via usage data already exposed by Observability |
| 15 multi-agent | — | Defer | Sub-agent orchestration is a future layer on top of the harness |
| 16 knowledge-indexing | — | Defer | Conversation recall builds on Checkpoint later |
| 17 plugin-system | — | Defer | Packaging/distribution concern, not runtime foundation |

## 3. Requirement Extraction Table

Mapping from reference requirements (topic level) to LoopPlane functional requirements in
[spec.md](./spec.md):

| Source (reference module → requirement topic) | Extracted intent | LoopPlane FR |
|---|---|---|
| 02 → turn cycle & natural termination | One terminal event per run with enumerated reasons | FR-001 |
| 02 → event emission across the loop | Deterministic normalized event ordering | FR-002 |
| 02 → cancellation pre-turn and mid-stream | Prompt, non-raising cancellation with terminal event | FR-003 |
| 02 → unknown tool / tool exception handling | Failures become error results; loop continues | FR-004 |
| 02 → concurrency-safe tool batching | Parallel only when declared safe; deterministic event order | FR-005 |
| 02 → stateful conversation + snapshots | History continuity and immutable snapshots | FR-006 |
| 02 → empty-turn orphan-input fix (change request) | No orphan user input that breaks role alternation | FR-007 |
| 02 → compaction + context-overflow retry (amendments) | Summarize-don't-split; one retry then surface | FR-008 |
| 02 → prompt assembler with pristine persisted input (amendments) | Injection at assembly time; durable history keeps verbatim input | FR-073 |
| 19 → transport-agnostic round-trip driver | Same driver for any host via abstract channels | FR-010, FR-011 |
| 10/19 → pending interaction round-trips (permission, ask-user) | Request-id-matched pending interaction registry | FR-012, FR-116 |
| 19 → disconnect/EOF semantics | Cancel cleanly; deny all pending approvals; never hang | FR-013, FR-115 |
| 10 → history replay incl. past user prompts (change request) | Full visible-conversation reconstruction on reattach | FR-014 |
| 10 → output coalescing & replay batching | Batch increments without reordering | FR-015 |
| 03+04+12 → unified execution path | Single Gateway chokepoint, no bypass | FR-020, FR-021 |
| 02/03 → input schema strictness (undeclared params rejected) | Validate before execution | FR-022 |
| 04 → pre-execution interception | Policy check precedes every execution | FR-023, FR-110 |
| 03 → per-call timeout (command tool) | Generalized per-call time limit at the Gateway | FR-024 |
| 03/12 → error conversion at boundaries | One normalized error-result shape; no raw leakage | FR-025 |
| 03 → large-output truncation | Output size management with artifact handoff | FR-026 |
| 02/03 → tool contract (streaming text/image/error) | Single internal tool contract | FR-030, FR-032 |
| 02 → conservative safety defaults | Not-safe/not-read-only unless declared | FR-031 |
| 03 → baseline tool set + ask-user tool (change request) | Minimum demonstrable tool set via Gateway only | FR-033 |
| 12 → layered config with malformed-entry tolerance | Scope override; bad config disables entry, never crashes | FR-040 |
| 12 → client/manager lifecycle | Connect, discover, invoke, clean shutdown | FR-041 |
| 12 → qualified tool naming | Source-qualified names prevent collisions | FR-042 |
| 12 → per-server failure isolation | One server's failure leaves the rest available | FR-043 |
| 12 → schema translation with safe fallback | External schemas mapped into validation model | FR-044 |
| 12 → permission integration | External tools governed exactly like internal | FR-045 |
| 08 → frontmatter parsing + size/structure guards | Declarative skill package; skip malformed safely | FR-050, FR-051 |
| 08 → two-source registration, last-wins | Deterministic merge, specific source wins | FR-052 |
| 08 → delta-only listing within budget | Incremental advertisement to the model | FR-053 |
| 08 → closed-list variable substitution | Runtime variables substituted; unknown left literal | FR-054 |
| 08 → invocation controls (model-invocation toggle, safety flag, forked execution) | Reshaped into explicit execution profile honored by Gateway/approval | FR-050, FR-055 |
| 10 → wire schema round-trip safety | Lossless serialization across process boundary | FR-064 |
| 10 → adapter "unknown type → skip" rule | Forward-compatible consumers | FR-063 |
| 02/10 → loop events vs wire events split | Loop emits normalized only; consumers adapt | FR-060–FR-062 |
| Reference change-control workflow | Event vocabulary changes are contract changes | FR-065 |
| 06 → typed entries, scan resilience | Durable memory with malformed-entry skip | FR-070, FR-071 |
| 06 → relevance ranking with fallback | Deterministic fallback ordering | FR-072 |
| 06 → memory-write tool | Agent-writable memory through the Gateway | FR-074 |
| 05 → append-as-you-go records | Durable, immediate, append-only recording | FR-080 |
| 05 → resume from records (+ typed normalization amendment) | State reconstruction from records alone | FR-081 |
| 05 → dangling tool-call repair | Synthetic error result + warning | FR-082 |
| 05 → corrupted-line skip | Partial damage never loses the session | FR-083 |
| 05 → concurrent write safety | No interleaving within a session | FR-084 |
| 05 → session listing with recency | Identity + recency metadata, newest first | FR-085 |
| 05 → large-result offload (amendment) | Threshold-based artifact persistence | FR-090, FR-091 |
| 05 → aggregate budget + frozen replacement (amendments) | Largest-first replacement; stability across resume | FR-092 |
| 05 → recorder boundary (loop never persists directly) | Persistence delta owned outside the loop | FR-094 |
| 18 → off-by-default gate, no-op safety | Zero behavior change when disabled | FR-100 |
| 18 → nested run/turn/call spans + durations | Trace of timed steps | FR-101 |
| 18 → usage counters, low-cardinality labels | Metrics without label explosion | FR-102 |
| 18 → metadata-only incl. error paths (change request) | No content, no exception messages/stack traces | FR-103 |
| 18 → "execution failures only" error metric | Policy denials are not execution failures | FR-104 |
| 04 → deny-with-reason as data | Denial returns explained error result; run continues | FR-111 |
| 04 → ask policy + once/session-scoped decisions | Structured escalation; session memory of decisions | FR-112, FR-113 |
| 04 → persistent rules with precedence | Local over broad; deny over allow | FR-114 |
| — (constitution Principle III) | Extension surface for future layers; no automation now | FR-120–FR-122 |

## 4. Architecture Intent Summary

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

## 5. Ambiguity List

Open questions deliberately *not* resolved by this spec. Each has a working default recorded
in the spec's Assumptions; revisit during `/speckit-clarify` or `/speckit-plan`:

| # | Ambiguity | Working default in spec |
|---|---|---|
| A1 | **Skill Execution Profile granularity** — which constraint fields does the profile carry in Phase 1 (autonomous-invocation toggle, approval class, tool restrictions, isolation mode)? The reference only had invocation/safety toggles plus a forked-execution mode. | Profile minimally controls autonomous invocation + approval requirement (FR-055); richer fields deferred |
| A2 | **Runtime Controller vs Dispatcher boundary** — one component or two? The reference merged host session management with the round-trip driver late in its life. | Controller owns session lifecycle (FR-010); Dispatcher owns the round-trip + pending interactions (FR-011–FR-015); may merge at design time |
| A3 | **Artifact thresholds and budgets** — fixed defaults vs configurable per deployment. | Configurable threshold + budget with sane defaults (FR-090, FR-092); exact values are a plan decision |
| A4 | **Event vocabulary versioning mechanism** — envelope version field vs per-type versions vs additive-only evolution. | Treated as a governed contract change (FR-065); mechanism chosen at plan time |
| A5 | **Memory relevance ranking** — deterministic heuristic only, or a pluggable ranker seam now? | Heuristic with deterministic fallback (FR-072); pluggability deferred |
| A6 | **Compaction summary production** — mechanical summarization vs model-generated summaries in Phase 1. | Summary marker required (FR-008); production method is a plan decision |
| A7 | **Future-layer attachment shape** — passive event subscription only, or an active control surface (pause/inject/steer)? | Phase 1 exposes passive subscription + lifecycle only (FR-120, FR-122) |
| A8 | **Concurrent session consumers** — can an observer attach to a live session alongside the driving consumer? | Single driving consumer per session; concurrent observers deferred |
| A9 | **MCP transports in Phase 1** — local-process servers only, or also remote HTTP transports? | Both local-process and remote transports accepted via config (FR-040–FR-041); host-level restrictions deferred |
| A10 | **Checkpoint storage layout ownership** — runtime-owned default location vs host-supplied. | Runtime-owned default, host-overridable (Assumptions) |
