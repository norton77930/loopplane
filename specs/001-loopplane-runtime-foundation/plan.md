# Implementation Plan: Agent Harness Runtime Foundation

**Branch**: `001-loopplane-runtime-foundation` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-loopplane-runtime-foundation/spec.md`

## Summary

Build LoopPlane's phase-1 Agent Harness Runtime as a single embeddable Python library:
thirteen bounded components (Agent Loop, Runtime Controller, Dispatcher, Tool Gateway,
Internal and MCP tool adapters, Skill Execution Profile, Runtime Event Bus, Memory,
Checkpoint, Artifact Storage, Observability, Human Approval) plus a passive extension
surface for future loop-engineering layers. Technical approach: asyncio + anyio structured
concurrency, pydantic-modeled events and records, JSON-Schema-validated tool inputs,
filesystem-only durability (append-only line records + artifact sidecars), optional
OpenTelemetry overlay, and a scripted model substitute as the primary test instrument. All
design decisions and ambiguity resolutions are recorded in [research.md](./research.md);
entity shapes in [data-model.md](./data-model.md); interface semantics in
[contracts/](./contracts/).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: anyio (structured concurrency); pydantic v2 (event/record/config
models); jsonschema (tool-input validation); `mcp` official SDK (confined to the MCP Tool
Adapter; optional extra); opentelemetry-api (optional extra, lazy-imported)

**Storage**: Local filesystem only — append-only line-oriented JSON session records plus
artifact sidecar files under a runtime-owned, host-overridable base directory. No database.

**Testing**: pytest + anyio pytest plugin; `tests/contract/` (one suite per contract doc),
`tests/unit/`, `tests/integration/`; scripted model substitute as a first-class fixture;
golden event-sequence, crash/resume, telemetry-sentinel, and public-safety scan tests.

**Target Platform**: Cross-platform library (Windows, Linux, macOS) embedded in host
processes; no host, transport, or UI dependency in the core (NFR-005).

**Project Type**: Single project — one distributable library package, src-layout.

**Performance Goals**: Interactive streaming — increments delivered promptly subject only
to the no-reorder batching rule (FR-015); negligible overhead from disabled optional
subsystems (NFR-002); test suite fast enough to run on every change.

**Constraints**: Deterministic event ordering (NFR-001); metadata-only telemetry (FR-103);
crash consistency (NFR-003); lossless serialization (NFR-006); public-safe documentation
(NFR-004).

**Scale/Scope**: Single process; one driving consumer per session; many resumable sessions
on disk (NFR-008). Thirteen components, 75 functional requirements (IDs FR-001–FR-122,
gapped numbering), 5 user stories.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after
design (both checks performed in this conversion pass).*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan/tasks derive from approved spec.md; every task cites FRs or contract docs; traceability to the private reference recorded in reference-analysis.md |
| II | Greenfield Implementation | PASS | No legacy code is copied; all artifacts re-derive intent only; implementation tasks reference LoopPlane artifacts exclusively |
| III | Agent Harness Before Loop Automation | PASS | Scheduler/validator/evaluator/auto-iteration excluded (FR-121); extension surface is passive subscription + lifecycle only (research A7); the only future-layer artifact is a demonstration consumer (FR-122) |
| IV | Runtime Boundary Clarity | PASS | spec.md Runtime Boundaries table assigns single ownership per component; project structure maps one package per component; interaction only via declared interfaces/events |
| V | Tool Gateway Ownership | PASS | contracts/tool-gateway.md defines the sole execution pipeline; a skeletal Gateway exists from the first loop milestone so no bypass is ever built (Phase C note below); adapters implement a 3-operation SPI inside the Gateway |
| VI | Runtime Event Bus Ownership | PASS | contracts/runtime-events.md is a closed, versioned vocabulary; the loop emits normalized events only; consumers adapt on their side (FR-061–FR-062) |
| VII | Public-Safe Documentation | PASS | All artifacts rewritten public-safe; automated blocklist scan is a permanent test (SC-006); the private reference stays untracked |
| VIII | No SDK Replacement | PASS | Runtime core is self-built; `mcp` is a protocol client confined behind the adapter boundary; anyio/pydantic/jsonschema are libraries, not agent frameworks (research R2–R4) |
| IX | Reference, Not Clone | PASS | Concepts re-derived through reference-analysis.md; deliberate divergences recorded (Controller/Dispatcher named split — research A2; Gateway unification — capability map) |
| X | Testable Evolution | PASS | Every phase below has required test tasks, a validation gate, and a rollback note; delivery is incremental by user story |

**Post-design re-check**: PASS — design artifacts (research, data-model, contracts)
introduce no violations. Complexity Tracking is empty.

## Architecture Boundaries

Component ownership and prohibitions are normative in
[spec.md → Runtime Boundaries](./spec.md#runtime-boundaries). The dependency direction is
strictly inward-out:

```text
hosts (future) ──► Controller/Dispatcher ──► Agent Loop ──► Model boundary
                          │                      │
                          ▼                      ▼
                   Runtime Event Bus ◄── Tool Gateway ──► adapters (internal, MCP)
                          │                      │
        consumers: streaming/history/trace      ▼
        observability, future layers      Human Approval
                          
Checkpoint / Artifact Storage  ◄── recording boundary (Controller side; never the loop)
Memory / Skills ──► prompt assembly only (durable history stays verbatim)
```

Allowed interactions (everything else is prohibited reach-through):

- Agent Loop calls **only** the model boundary and the Tool Gateway; it emits events and
  returns history deltas — it never persists, formats, or authorizes.
- Tool Gateway is the only caller of adapter `invoke`; Human Approval is consulted only by
  the Gateway's decide stage.
- Checkpoint and Artifact Storage are written only through the recording boundary
  (FR-094).
- Observability, history, replay, and future layers consume the Event Bus only.

## Selected Phase-1 Scope

In scope: the thirteen components, the baseline internal tool set, MCP-based external
tools, the scripted model substitute plus one separately validated real-model integration,
and the passive demonstration consumer. Out of scope (deferred or dropped per
[reference-analysis.md §3](./reference-analysis.md)): hosts and UIs, lifecycle hook
interception, sandboxing, cost governance, sub-agent orchestration, conversation recall,
plugin packaging, multi-tenant concerns, and all loop automation (constitution III).

## Design Decisions

Authoritative record in [research.md](./research.md): R1 toolchain, R2 concurrency,
R3 modeling/validation, R4 MCP SDK confinement, R5 observability, R6 storage, R7 testing;
A1–A10 ambiguity resolutions. Plan-specific sequencing decisions:

- **D1 — Skeletal Gateway from day one.** The first loop milestone ships a minimal Gateway
  (registry + resolve + execute + allow-all policy seam) rather than letting the loop call
  tools directly; governance stages are then added inside the chokepoint. This guarantees
  FR-020/SC-002 are structurally true at every commit, never retrofitted.
- **D2 — Compaction lands with prompt assembly.** FR-008 (compaction + single overflow
  retry) and FR-073 (pristine history) both belong to the assembly cluster, so they are
  implemented together in the memory/skills phase rather than the first loop phase.
- **D3 — Events before everything.** The event vocabulary and serialization are the first
  implemented artifact; every later component is built against contract tests that assert
  its emissions.

## Project Structure

### Documentation (this feature)

```text
specs/001-loopplane-runtime-foundation/
├── spec.md                  # Feature specification (updated in this pass)
├── plan.md                  # This file
├── research.md              # Phase 0: decisions + ambiguity resolutions
├── data-model.md            # Phase 1: entities + state machines
├── reference-analysis.md    # Provenance: private-reference conversion record
├── contracts/               # Phase 1: 8 interface contracts
└── tasks.md                 # Phase 2: milestone-ordered tasks
```

### Source Code (repository root; created during implementation, not by this plan)

```text
pyproject.toml
src/loopplane/
├── errors.py            # Normalized Error shape (FR-025)
├── context.py           # Run Context (data-model.md)
├── events/              # Event envelope + vocabulary + serde (contracts/runtime-events.md)
├── model/               # Model boundary protocol, content blocks, scripted substitute
├── loop/                # Agent Loop: turn cycle, partitioning, assembly, compaction
├── controller/          # Runtime Controller + Dispatcher (contracts/run-lifecycle.md)
├── gateway/             # Tool Gateway pipeline (contracts/tool-gateway.md)
├── tools/               # Internal Tool Adapter + baseline tools (FR-030–FR-034)
├── adapters/
│   └── mcp/             # MCP Tool Adapter (FR-040–FR-045)
├── skills/              # Skill loading/merge/advertisement + execution profiles
├── memory/              # Memory store, selection, injection, write tool
├── checkpoint/          # Records, resume, repair, listing (contracts/checkpoint.md)
├── artifacts/           # Artifact store + replacement budget (contracts/artifacts.md)
├── observability/       # Optional OTel overlay (FR-100–FR-104)
└── approval/            # Policy decisions + pending interactions (contracts/approval.md)

tests/
├── contract/            # One suite per contracts/ document + cross-cutting suites
│                        #   (public-safety scan, observability gating)
├── unit/
└── integration/         # Scripted end-to-end runs, crash/resume, gating matrix

docs/                    # Embedding quickstart; real-model validation procedure
examples/                # Demonstration consumer (FR-120–FR-122)
```

**Structure Decision**: Single library package, one sub-package per runtime component, so
the package graph mirrors the Runtime Boundaries table and boundary violations are visible
as imports.

## Implementation Phases

Each phase ends with its tests green, a validation gate, and a documented rollback
(constitution X). Detailed tasks in [tasks.md](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| A — Setup | Package scaffold, tooling (ruff/mypy/pytest), CI on Windows + Linux, public-safety scan test | Lint/type/test runners green | Revert scaffold commits |
| B — Foundational | Event envelope + vocabulary + serde; Normalized Error; Run Context; content blocks; model boundary + scripted substitute | runtime-events + model-boundary contract tests pass; serde round-trip property tests | Revert; nothing depends on it yet |
| C — US1 loop core | Skeletal Gateway (D1); Agent Loop FR-001–FR-007; Controller create/drive/terminate; minimal Dispatcher; echo-style tool | US1 acceptance scenarios green against the substitute; golden event sequences stable | Revert phase; foundational layer unaffected |
| D — US2 governance | Full Gateway pipeline (validate/decide/timeout/normalize/size-manage); Human Approval + pending interactions + questions; baseline internal tools incl. stale-write guard; MCP adapter | US2 acceptance + approval/tool-gateway contract tests green; SC-002 audit test | Revert to skeletal Gateway; default policy remains allow-all in tests only |
| E — US3 durability | Checkpoint records + resume/repair/listing; Artifact Storage + replacement budget; Dispatcher replay + batching | US3 acceptance + checkpoint/artifacts contract tests; crash/resume integration tests (SC-003) | Revert; sessions created during the phase are discardable test data |
| F — US4 memory & skills | Prompt assembler (FR-073); Memory; Skills + execution profiles; compaction + overflow retry + post-compaction re-establishment (D2) | US4 acceptance green; compaction edge cases; verbatim-history assertions | Disable via default-off gating; revert leaves core loop intact |
| G — US5 observability | Optional OTel overlay: spans, metrics, strict metadata-only | US5 acceptance; zero-behavior-change equality test; sentinel scan (SC-004) | Remove optional extra; disabled path is the default already |
| H — Polish | Demonstration consumer (FR-122); gating matrix test (SC-007); embedding quickstart doc; public-safety scan pass (SC-006); separately documented real-model validation | Full suite green on both CI platforms; SC-001–SC-009 each mapped to a passing test | Individual revert per item |

## Testing Strategy

- **Contract tests** (`tests/contract/`): one suite per document in
  [contracts/](./contracts/), plus cross-cutting suites (the public-safety scan and the
  observability gating tests), asserting exactly the semantics those documents promise —
  these are the boundary-integrity gate (constitution IV–VI).
- **Golden event sequences**: scripted-substitute runs asserted increment-by-increment
  (NFR-001); any vocabulary change shows up as a reviewed golden diff plus a version bump
  (FR-065).
- **Crash/resume**: terminate between recorded steps, resume from records alone, compare
  reconstructed state (SC-003).
- **Gating matrix**: identical scripts with optional subsystems off/on must produce
  identical event sequences (SC-007).
- **Privacy**: telemetry sentinel scans (SC-004) and the committed-file public-safety scan
  (SC-006) run as ordinary tests in CI.
- **Success-criteria traceability**: tasks.md ends with a checklist mapping SC-001–SC-009
  to concrete test files.

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Deterministic ordering under parallel tool execution is subtle | Emit per-call events in original request order (FR-005); golden-sequence tests with deliberately racy scripted tools |
| Windows filesystem semantics (locking, rename, paths) | CI runs the full suite on Windows and Linux from Phase A onward (NFR-005) |
| `mcp` SDK evolution breaks the adapter | SDK confined behind the adapter SPI (research R4); contract tests pin adapter behavior, not SDK internals |
| Event vocabulary churn destabilizes consumers | Versioned envelope + additive-only evolution (research A4); unknown-type tolerance (FR-063) |
| Scope creep toward loop automation | Constitution III is a review gate; any automation need becomes a future-phase spec (FR-121) |
| Hot-path overhead from validation/serialization | Increments carry lean payloads; benchmark before optimizing; observability is no-op by default (FR-100) |

Rollback posture: small task-scoped commits on this feature branch; each phase independently
revertible; optional subsystems are default-off (natural feature gates); stored records carry
`schema_version` so reverting code never corrupts previously written sessions (unknown or
newer records are skipped with diagnostics per FR-083's tolerance posture).

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
