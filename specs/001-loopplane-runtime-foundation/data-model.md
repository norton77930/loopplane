# Data Model: Agent Harness Runtime Foundation

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Date**: 2026-06-13

**Scope**: Interface-level definition of the entities named in the spec's Key Entities
section, their relationships, and their state machines. Field types are abstract
(`identifier`, `timestamp`, `enum`, …); concrete representations are an implementation
concern. Event payloads are specified in
[contracts/runtime-events.md](./contracts/runtime-events.md); this document covers what the
runtime *stores and shares*, not what it streams.

## Conventions

- **Identifiers** are opaque, unique strings; session identifiers are globally unique, call
  and request identifiers are unique within their session.
- **Timestamps** are timezone-aware instants recorded by the runtime.
- **Schema versions** are integers governed by the additive-evolution policy in
  [research.md](./research.md) (A4) and FR-065.

## Entities

### Session

One governed conversation run (FR-006, FR-010, FR-085).

| Field | Type | Notes |
|---|---|---|
| session_id | identifier | Globally unique |
| created_at | timestamp | |
| last_active_at | timestamp | Drives newest-first listing (FR-085) |
| label | string, optional | Host-supplied display label |
| lifecycle_state | enum | See Session lifecycle state machine |
| storage_root | opaque location | Where this session's records and artifacts live |

### Run Context

The per-run execution scope handed to tools and policies (Key Entities; FR-003, FR-113).

| Field | Type | Notes |
|---|---|---|
| session_id | identifier | |
| working_scope | path-like | The directory scope file tools operate in |
| cancellation | signal | Observed before each turn and during streaming (FR-003) |
| turn_budget | integer, optional | Maximum turns for the run (FR-001) |
| session_approval_memory | map: tool name → decision | Session-scoped approval decisions (FR-113) |
| feature_toggles | map, optional | Enablement of optional subsystems (NFR-002) |

### Content Block

The typed unit of conversation content (audit addition; reference long-task amendments).

| Kind | Payload | Notes |
|---|---|---|
| text | string | |
| image | media reference + format | |
| tool-call | call_id, tool name, input | The model's request |
| tool-result | call_id, outcome, outputs, error info | Pairs with its tool-call by call_id |
| summary-marker | structured digest | Produced by compaction (FR-008); replaces a span of older content without splitting a tool-call from its tool-result |

### History Entry

One entry in a session's reconstructed conversation.

| Field | Type | Notes |
|---|---|---|
| role | enum: user, assistant | Tool results attach as tool-result blocks |
| blocks | ordered Content Blocks | |
| recorded_at | timestamp | |

Durable history retains the user's verbatim input; prompt augmentation (memory, skill
listings) exists only in the assembled model context (FR-073).

### Checkpoint Record

One append-only durable entry (FR-080–FR-084). Envelope fields are common to all kinds.

| Envelope field | Type | Notes |
|---|---|---|
| record_kind | enum | See kinds below |
| schema_version | integer | |
| session_id | identifier | |
| sequence | integer | Monotonic within the session |
| recorded_at | timestamp | |
| payload | kind-specific | |

Record kinds: **session-meta** (first record: identity, created_at, label),
**user-input** (verbatim text/blocks), **assistant-message** (blocks incl. tool-calls),
**tool-result** (call_id, outcome, outputs or artifact reference),
**replacement-decision** (see Replacement Record), **termination** (reason, turn count).
A corrupted record is skipped with a warning; the rest of the stream loads (FR-083).

### Runtime Event

The normalized, versioned unit of observable behavior (FR-060–FR-065). Envelope: event
type, schema_version, session_id, sequence, occurred_at, replay, payload. The closed
vocabulary and ordering rules live in
[contracts/runtime-events.md](./contracts/runtime-events.md).

### Tool Descriptor

The registered identity of a tool (FR-021, FR-030, FR-031, FR-042).

| Field | Type | Notes |
|---|---|---|
| name | string | Source-qualified for external tools (FR-042) |
| description | string | |
| input_schema | JSON Schema | Undeclared properties rejected (FR-022) |
| concurrency_safe | boolean | Default **false** (FR-031) |
| read_only | boolean | Default **false** (FR-031) |
| source | enum: internal, external-server(ref) | |

### Tool Invocation / Tool Result

| Tool Invocation | Type | Notes |
|---|---|---|
| call_id | identifier | |
| tool_name | string | |
| input | validated object | Post-validation (FR-022) |
| turn_index | integer | |

| Tool Result | Type | Notes |
|---|---|---|
| call_id | identifier | |
| outcome | enum: success, failure | An error output marks failure, run stays alive (FR-032) |
| outputs | Content Blocks (text/image) | Possibly reduced, with artifact reference (FR-091) |
| error | Normalized Error, optional | Present when outcome = failure |
| duration | duration | |

### Normalized Error

The single failure shape crossing the Gateway boundary (FR-025).

| Field | Type | Notes |
|---|---|---|
| category | enum: unknown-tool, validation, policy-denial, timeout, execution, adapter-fault | FR-021–FR-025 |
| reason | string | Safe to show to the model; raw adapter internals never leak |

### Approval Request / Approval Decision

| Approval Request | Type | Notes |
|---|---|---|
| request_id | identifier | Matches exactly one decision (FR-012) |
| session_id, call_id | identifiers | |
| tool_name, input summary | string / object | What the reviewer sees |
| requested_at | timestamp | |

| Approval Decision | Type | Notes |
|---|---|---|
| request_id | identifier | |
| decision | enum: allow, deny | |
| scope | enum: once, session | Session scope is remembered (FR-113) |
| reason | string, optional | Default supplied on denial when absent (FR-111) |

### Permission Rule

A persistent allow/deny matcher (FR-114).

| Field | Type | Notes |
|---|---|---|
| matcher | tool-name pattern | |
| effect | enum: allow, deny | |
| scope | enum: user, project, session-local | More local scope wins; deny beats allow within a scope |

### Skill / Execution Profile

| Skill | Type | Notes |
|---|---|---|
| name | string | Conflicts resolved by source specificity (FR-052) |
| description | string | |
| instructions | text | Closed-list variable substitution applies (FR-054) |
| source | enum/ordered source ref | |
| size | integer | Validated against a cap at load (FR-051) |
| profile | Execution Profile | |

| Execution Profile | Type | Notes |
|---|---|---|
| autonomous_invocation | enum: allowed, forbidden | FR-055; research A1 |
| approval_required | boolean | Honored by Gateway + Human Approval (FR-055) |

### Memory Entry

| Field | Type | Notes |
|---|---|---|
| type | enum (open set; defaults: user, project, reference, feedback) | Drives fallback ordering (FR-072) |
| name | string | Required; malformed entries are skipped (FR-071) |
| description | string | Required; used for relevance selection (FR-072) |
| body | text | Injected at assembly time only (FR-073) |

### Artifact / Replacement Record

| Artifact | Type | Notes |
|---|---|---|
| reference | identifier | Stable; retrievable after the run (FR-093) |
| session_id, call_id | identifiers | Originating association (FR-090) |
| size | integer | |
| media_kind | enum: text, image, binary | |
| created_at | timestamp | |
| location | opaque | Owned by Artifact Storage |

| Replacement Record | Type | Notes |
|---|---|---|
| artifact reference | identifier | |
| replaced_call_id | identifier | |
| preview | bounded text | What remains in conversation (FR-091) |
| decided_at | timestamp | |
| frozen | always true | Decisions never change across resume (FR-092) |

### Trace Step

Metadata-only timed record (FR-101, FR-103).

| Field | Type | Notes |
|---|---|---|
| kind | enum: run, turn, model-call, tool-call | Nested run → turn → call |
| parent | step ref, optional | |
| started_at / ended_at | timestamps | |
| attributes | low-cardinality metadata | Names, counts, durations, error *types* only |

## Relationships

- Session 1—N Checkpoint Records (ordered by sequence); 1—N Artifacts; 1—N Runtime Events.
- History is *derived*: reconstructing a session replays its Checkpoint Records (FR-081),
  repairing any tool-call without a tool-result via a synthetic error result (FR-082).
- Tool Result 0..1 Artifact (when offloaded); Replacement Record N—1 Artifact.
- Approval Request 1—1 Approval Decision (or denied-by-disconnect, FR-115).
- Skill N—1 Execution Profile (embedded); Memory Entries are session-independent (FR-070).

## State Machines

### Session lifecycle (FR-010)

```text
created ──► active ──► suspended ──► active (resumed, FR-081)
                │            │
                ▼            ▼
            terminated   terminated        (terminal; reason recorded, FR-001)
```

Consumer attachment (attached/detached) is orthogonal to lifecycle: detach suspends
driving; reattach replays history (FR-014) and resumes the single driving consumer (A8).

### Tool call lifecycle (FR-020–FR-026, FR-110)

```text
requested ──► validated ──► decided ──► executing ──► completed
    │             │            │            │
    │ invalid     │ unknown    │ denied     ├──► failed (execution error, FR-032)
    ▼             ▼            ▼            └──► timed-out (FR-024)
 failed        failed       failed
(validation) (unknown-tool) (policy-denial — run continues, FR-111)
```

Every failure path produces a Normalized Error result; none of them ends the run.

### Approval lifecycle (FR-112–FR-115)

```text
pending ──► decided (allow | deny; scope once | session)
    │
    └──► denied-by-disconnect (reviewer channel closed, FR-115)
```
