# Research: Agent Harness Runtime Foundation (Phase 0)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Date**: 2026-06-13

**Purpose**: Resolve the open ambiguities recorded in
[reference-analysis.md](./reference-analysis.md) §6 and record the technology decisions the
implementation plan depends on. Every decision below is a *plan-level* choice: the feature
spec stays implementation-neutral, and any of these choices can be revisited through the
normal spec-first change process without touching the spec's requirements.

---

## Technology Decisions

### R1 — Language & toolchain

**Decision**: Python 3.12+; a single distributable package in src-layout (`src/loopplane/`);
`pyproject.toml` project metadata; `uv` for development environment and dependency
management; `ruff` (lint + format) and `mypy` (strict on `src/`) as quality gates.

**Rationale**: The project is Python-first by charter. 3.12 provides mature asyncio,
exception groups, and modern typing. Src-layout prevents accidentally importing the repo root
in tests. `uv`/`ruff`/`mypy` are current community-standard tooling with near-zero
configuration.

**Alternatives considered**: 3.11 floor (no consumer requires it; higher floor simplifies
typing); poetry/pip-tools (slower, more configuration than `uv`); flake8 + black (subsumed by
ruff).

### R2 — Concurrency model

**Decision**: asyncio event loop with **anyio** for structured concurrency — task groups,
cancellation scopes, locks, and memory object streams.

**Rationale**: FR-005 (safe-parallel/sequential tool partition) and FR-013 ("cancel in-flight
work, resolve pending approvals, never hang") map directly onto task groups and cancellation
scopes; memory object streams give the Dispatcher's abstract send/receive channels a tested
in-process implementation. anyio is a thin concurrency layer, not an agent framework, so
constitution Principle VIII is untouched.

**Alternatives considered**: raw asyncio (manual cancellation bookkeeping is precisely the
source of the hangs the spec forbids); trio (right semantics, smaller ecosystem — anyio
provides the same model on asyncio); threads (poor fit for streaming and cancellation).

### R3 — Data modeling & validation

**Decision**: **pydantic v2** models for runtime events, checkpoint records, and runtime
configuration. Tool inputs are validated against each tool's declared **JSON Schema** with
undeclared properties rejected (FR-022); schemas from external servers pass through
translation with a safe permissive fallback (FR-044).

**Rationale**: Events and records need lossless, versioned (de)serialization (FR-064,
FR-065); pydantic v2 gives strict typed models with JSON round-trip and discriminated
unions for the event/record vocabularies. Tool inputs are model-generated JSON against
arbitrary declared schemas — exactly what JSON Schema validation exists for. pydantic is a
data library, not an agent framework (constitution Principle VIII compliant).

**Alternatives considered**: dataclasses + hand-rolled serde (reinvents versioned
serialization, error-prone); attrs/cattrs (workable, weaker validation ecosystem);
dynamically generating typed models from each tool's JSON Schema (complex, opaque failure
modes; direct schema validation is closer to the contract).

### R4 — MCP protocol support

**Decision**: Use the official **`mcp` Python SDK** strictly inside the MCP Tool Adapter.
Phase-1 transports: local-process (stdio) and remote streaming HTTP, selected per configured
server entry (resolves **A9**).

**Rationale**: MCP is an open protocol and its reference SDK covers handshake/transport
plumbing that is undifferentiated work. Constitution Principle VIII bans agent frameworks as
the runtime core; a protocol client confined behind the adapter boundary does not shape the
runtime architecture — the Tool Gateway still owns naming, authorization, timeouts, and
error normalization for every external tool (FR-042, FR-045). If the SDK ever becomes a
liability, the adapter is the single replacement point.

**Alternatives considered**: hand-rolled protocol client (high cost, low value, protocol
still evolving); deferring MCP entirely (rejected — external-tool governance is a phase-1
user story).

### R5 — Observability backend

**Decision**: **OpenTelemetry API** as an optional extra (`loopplane[otel]`), imported
lazily; active only when the host explicitly configures an exporter endpoint; the disabled
default is a no-op with zero behavior change (FR-100). Traces: nested run / turn /
model-call / tool-call spans with durations (FR-101). Metrics: token-usage and step
counters with low-cardinality labels only (FR-102). All attributes metadata-only; failures
recorded as error *type* only (FR-103, FR-104).

**Rationale**: OTel is the vendor-neutral standard; the API package alone is
dependency-light; lazy import keeps the core import graph clean when the extra is absent.

**Alternatives considered**: bespoke trace logging (loses the ecosystem); structured logging
only (no span nesting for FR-101); always-on telemetry (violates FR-100).

### R6 — Durable storage

**Decision**: Filesystem-only persistence in phase 1.

- **Checkpoint records**: one JSON document per line, append-only, per session, under a
  runtime-owned default base directory (platform-appropriate user-data location) that hosts
  can override (resolves **A10**). Concurrent-write safety via a per-session async lock
  (FR-084); durability via flush-on-append (FR-080).
- **Artifacts**: sidecar files per session keyed by the originating call identity, with
  their metadata recorded through the same record stream (FR-090, FR-094).

**Rationale**: Append-only line records are crash-consistent, human-inspectable, and isolate
corruption to single lines (FR-083) with zero infrastructure — and they work identically on
Windows and POSIX filesystems (NFR-005).

**Alternatives considered**: SQLite (transactions are attractive, but schema/migration
weight isn't needed yet; the recording boundary keeps the door open); external databases
(out of scope per NFR-008).

### R7 — Test strategy & frameworks

**Decision**: **pytest** with anyio's pytest plugin. Test taxonomy:

- `tests/contract/` — one suite per document in [contracts/](./contracts/), asserting the
  interface semantics those documents promise;
- `tests/unit/` — per-component behavior;
- `tests/integration/` — scripted end-to-end runs.

A **scripted model substitute** implementing the model boundary
([contracts/model-boundary.md](./contracts/model-boundary.md)) from a declarative script of
turns (text, reasoning, tool requests, failures) is a first-class fixture. It enables golden
event-sequence assertions (NFR-001), deterministic cancellation-timing tests (FR-003),
crash/resume tests (terminate the process between steps, resume from records alone —
SC-003), telemetry sentinel scans (SC-004), and identical-behavior comparisons with optional
subsystems on/off (SC-007). Public safety is verified by a blocklist scan over committed
files (SC-006).

**Alternatives considered**: unittest (weaker fixtures/parametrization); recording real
model traffic into fixtures (non-deterministic and risks leaking content).

---

## Ambiguity Resolutions (A1–A10)

Resolutions for the open questions in [reference-analysis.md](./reference-analysis.md) §6.

| ID | Resolution | Rationale |
|---|---|---|
| A1 | The phase-1 execution profile carries exactly two constraints: **autonomous invocation** (may the model invoke the skill on its own) and **approval requirement** (does invocation require a human decision). Richer fields (tool restrictions, isolation modes) are deferred. | The smallest set the Gateway and Human Approval boundary must honor (FR-055); anything more is speculative now. |
| A2 | **Controller and Dispatcher are two named roles with separate contracts.** Phase 1 may implement them within one subsystem, but the lifecycle API (FR-010) and the round-trip driver (FR-011–FR-015) remain independently testable. | The reference grew both inside hosts and extracted the driver late; naming both from the start is a deliberate, recorded divergence (constitution Principle IX). |
| A3 | Defaults: artifact offload threshold **64 KiB** per tool result; aggregate retained-results budget **1 MiB** per session. Both host-configurable; tests configure their own values and pin behavior, not numbers. | Conservative starting values that exercise the offload/replacement machinery without dominating small runs (FR-090, FR-092). |
| A4 | Every event envelope carries a single vocabulary-wide **schema version**. Within a version, evolution is **additive only** (new event types, new optional fields). Removals or renames bump the version and require a contract update plus tests (FR-065); consumers skip unknown types (FR-063). | One version number is easy to reason about and test; additive evolution plus unknown-type tolerance covers forward compatibility. |
| A5 | Relevance ranking is a **deterministic lexical heuristic** (normalized token overlap between the prompt and an entry's name/description) with stable tie-breaking (entry type priority, then name). Failure or an empty result falls back to deterministic type-priority ordering (FR-072). A pluggable ranker seam is deferred. | Deterministic, dependency-free, testable; ranking quality can improve later without contract changes. |
| A6 | The compaction summary marker is **mechanically produced** (a structured digest: turn counts, tool names used, bounded excerpts of the earliest user intents) with no model call. Model-generated summaries are deferred. | Deterministic and free; keeps NFR-001 intact and avoids recursive model dependencies in the loop. |
| A7 | The extension surface is **(a)** subscription to a session's normalized event stream and **(b)** the session lifecycle operations — nothing else (FR-120). No pause/inject/steer controls in phase 1. The demonstration consumer (FR-122) proves sufficiency. | Constitution Principle III: leave seams, implement no automation. A passive surface cannot destabilize the loop. |
| A8 | **Exactly one driving consumer per session.** A reattachment replaces the prior attachment after history replay (FR-014). Concurrent live observers are deferred. | Removes fan-out and ordering questions from phase 1; the event bus design keeps multi-consumer support open. |
| A9 | External tool servers connect over **stdio (local process)** or **streaming HTTP (remote)**, chosen per server configuration entry (FR-040, FR-041). | The two transports the protocol ecosystem actually uses; per-entry selection keeps config explicit. |
| A10 | Checkpoint/artifact storage defaults to a **runtime-owned base directory** in the platform's user-data location, overridable through runtime configuration. Tests always override into temporary directories. | Embedding works out of the box; hosts that care choose their own location; tests stay hermetic. |
