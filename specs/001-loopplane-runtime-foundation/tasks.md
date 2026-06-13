---

description: "Task list for the Agent Harness Runtime Foundation"
---

# Tasks: Agent Harness Runtime Foundation

**Input**: Design documents from `/specs/001-loopplane-runtime-foundation/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Test tasks are REQUIRED. Per Constitution Principle X (Testable Evolution), every
implementation phase MUST include tests and validation tasks. Write each story's tests
first and confirm they fail before implementing.

**Organization**: Phases mirror plan.md (A–H): Setup → Foundational → one phase per user
story (US1–US5) → Polish. Each user story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task belongs to (US1–US5)
- Paths follow plan.md Project Structure (src-layout single package)

---

## Phase 1: Setup (plan Phase A)

**Purpose**: Project scaffold and quality gates; no runtime behavior yet.

- [X] T001 Create the package scaffold per plan.md Project Structure: `pyproject.toml`
      (project metadata, dependencies, optional extras `mcp` and `otel`),
      `src/loopplane/__init__.py`, and the `tests/contract|unit|integration/` tree
- [X] T002 Configure quality gates in `pyproject.toml`: ruff (lint + format), mypy strict on
      `src/`, pytest + anyio plugin defaults
- [X] T003 [P] Add CI running lint, type-check, and tests on Windows and Linux in
      `.github/workflows/ci.yml` (NFR-005)
- [X] T004 [P] Add the public-safety scan as a permanent test in
      `tests/contract/test_public_safety.py`: scans committed files for generic secret
      patterns, network addresses, and absolute local paths, and additionally loads
      patterns from an optional local (gitignored) pattern file (SC-006, constitution VII)

**Checkpoint**: `ruff`, `mypy`, and `pytest` all run green on the empty project.

---

## Phase 2: Foundational (plan Phase B) — BLOCKS all user stories

**Purpose**: The event vocabulary, shared shapes, and the model boundary every story builds
on (plan D3).

- [X] T005 [P] Write contract tests for runtime events in
      `tests/contract/test_runtime_events.py`: envelope fields, closed vocabulary,
      lossless serde round-trip, unknown-type skip, monotonic sequence
      (contracts/runtime-events.md; FR-060, FR-063, FR-064) — confirm they fail
- [X] T006 [P] Write contract tests for the model boundary and scripted substitute in
      `tests/contract/test_model_boundary.py`: scripted turns yield normalized increments,
      usage on turn end, context-capacity query, distinct overflow signal
      (contracts/model-boundary.md) — confirm they fail
- [X] T007 Implement the event envelope + vocabulary + serialization in
      `src/loopplane/events/` (contracts/runtime-events.md)
- [X] T008 [P] Implement the Normalized Error shape in `src/loopplane/errors.py`
      (data-model.md; FR-025)
- [X] T009 [P] Implement the Run Context in `src/loopplane/context.py` (data-model.md)
- [X] T010 [P] Implement content block models (text, image, tool-call, tool-result,
      summary-marker) in `src/loopplane/model/content.py` (data-model.md)
- [X] T011 Implement the model boundary protocol and the scripted substitute in
      `src/loopplane/model/` (contracts/model-boundary.md; research R7)

**Checkpoint**: T005/T006 pass — the vocabulary and the test instrument exist; user-story
phases may start.

---

## Phase 3: User Story 1 — Drive a complete agent run (P1, plan Phase C) 🎯 MVP

**Goal**: A full conversation turn cycle — model reasoning, tool calls, results, follow-up —
observable as ordered normalized events, with cancellation and budgets.

**Independent Test**: One tool-using conversation against the scripted substitute; assert
the exact event sequence and final history.

### Tests for User Story 1 (write first; confirm they fail)

- [X] T012 [P] [US1] Integration test: plain-text run golden event sequence and recorded
      history in `tests/integration/test_us1_plain_run.py` (acceptance 1.1; FR-001, FR-002)
- [X] T013 [P] [US1] Integration test: tool-using run event order and coherent history with
      an echo-style tool in `tests/integration/test_us1_tool_run.py` (acceptance 1.2;
      FR-005, FR-006)
- [X] T014 [P] [US1] Integration tests: cancellation pre-turn and mid-stream, turn-budget
      exhaustion, unknown tool, no orphaned input on empty turns in
      `tests/integration/test_us1_termination.py` (acceptance 1.3–1.5; FR-003, FR-004,
      FR-007)

### Implementation for User Story 1

- [X] T015 [US1] Implement the skeletal Tool Gateway — registry, name resolution, execute,
      allow-all policy seam, `tool-call-*` event emission — in `src/loopplane/gateway/`
      (plan D1; FR-020, FR-021)
- [X] T016 [US1] Implement the Agent Loop turn cycle in `src/loopplane/loop/`: drive the
      model boundary, partition tool calls by declared concurrency safety, execute through
      the Gateway, emit events, maintain history with immutable snapshots, end with exactly
      one terminal event (FR-001–FR-007, FR-031)
- [X] T017 [US1] Implement Runtime Controller session lifecycle (create, drive, terminate;
      in-memory state) in `src/loopplane/controller/controller.py`
      (contracts/run-lifecycle.md; FR-010)
- [X] T018 [US1] Implement the minimal Dispatcher — round-trip over in-process channels,
      `submit-input` and `cancel` handling — in `src/loopplane/controller/dispatcher.py`
      (FR-011, FR-003)
- [X] T019 [US1] Unit tests for partitioning, snapshot immutability, and terminal reasons in
      `tests/unit/test_loop_core.py`

**Checkpoint**: US1 demonstrable end-to-end with scripted model + echo tool; goldens stable.

---

## Phase 4: User Story 2 — Govern every tool call (P2, plan Phase D)

**Goal**: The full Gateway pipeline plus the Human Approval boundary; internal baseline
tools and MCP servers governed identically.

**Independent Test**: One internal tool + one test MCP server under allow/deny/ask
policies; assert gateway decisions, approval round-trips, normalized results.

### Tests for User Story 2 (write first; confirm they fail)

- [X] T020 [P] [US2] Contract tests for the Gateway pipeline in
      `tests/contract/test_tool_gateway.py`: undeclared-parameter rejection, unknown tool,
      timeout, one normalized error shape, no execution path outside the Gateway
      (contracts/tool-gateway.md; FR-022, FR-024, FR-025, SC-002)
- [X] T021 [P] [US2] Contract tests for approval in `tests/contract/test_approval.py`:
      deny-with-reason continues the run, ask round-trip, session-scoped memory, rule
      precedence, reviewer-disconnect denies all pending, question round-trip with
      exactly-one resolution (contracts/approval.md; FR-110–FR-116)
- [X] T022 [P] [US2] Integration tests for US2 acceptance 2.1–2.6 in
      `tests/integration/test_us2_governance.py` (2.3/2.4 live in
      `tests/integration/test_us2_mcp.py`, which owns the MCP fixture)

### Implementation for User Story 2

- [X] T023 [US2] Add the validation stage — JSON Schema with undeclared-property rejection —
      to `src/loopplane/gateway/` (FR-022; research R3)
- [X] T024 [US2] Implement the Human Approval component in `src/loopplane/approval/`:
      decision sources and order, scopes, persistent rules with precedence, denial-as-data
      (contracts/approval.md; FR-110–FR-114)
- [X] T025 [US2] Implement the pending-interaction registry and the question round-trip in
      `src/loopplane/controller/dispatcher.py` + `src/loopplane/approval/` (FR-012,
      FR-013, FR-115, FR-116)
- [X] T026 [US2] Add per-call timeout, error normalization, and `diagnostic` emission to the
      Gateway (FR-024, FR-025)
- [X] T027 [US2] Implement the Internal Tool Adapter and baseline tools — file read, file
      write/edit with the stale-write guard, content search, command execution, ask-user —
      in `src/loopplane/tools/` (FR-030–FR-034)
- [X] T028 [US2] Add output-size management to the Gateway (bounded reduction now; artifact
      handoff activates in US3) in `src/loopplane/gateway/` (FR-026)
- [X] T029 [US2] Implement the MCP Tool Adapter — layered config, connection lifecycle,
      source-qualified names, per-server failure isolation, schema translation with
      fallback — in `src/loopplane/adapters/mcp/` (FR-040–FR-045; research R4)
- [X] T030 [US2] Unit tests for rule precedence and the stale-write guard in
      `tests/unit/test_rules_and_tools.py`; integration test with a local test MCP server
      fixture in `tests/integration/test_us2_mcp.py` (FR-043, FR-045)

**Checkpoint**: every execution path traverses the full pipeline; US1 and US2 pass together.

---

## Phase 5: User Story 3 — Suspend, resume, audit (P3, plan Phase E)

**Goal**: Durable append-as-you-go records, resume with repair, artifact offload with a
frozen replacement budget, replay on reattach.

**Independent Test**: Record a session, kill the process at chosen points, resume from
records alone, compare reconstructed state.

### Tests for User Story 3 (write first; confirm they fail)

- [X] T031 [P] [US3] Contract tests for checkpoint in
      `tests/contract/test_checkpoint.py`: append-as-you-go, resume from records alone,
      dangling-call repair with warning, corrupted-record skip, concurrent-write safety,
      newest-first listing (contracts/checkpoint.md; FR-080–FR-085)
- [X] T032 [P] [US3] Contract tests for artifacts in `tests/contract/test_artifacts.py`:
      threshold offload, preview + stable reference, budget replacement frozen across
      resume, retrieval by reference (contracts/artifacts.md; FR-090–FR-093)
- [X] T033 [P] [US3] Crash/resume integration tests for acceptance 3.1–3.4 in
      `tests/integration/test_us3_resume.py` (SC-003)
- [X] T034 [P] [US3] Contract tests for the run lifecycle in
      `tests/contract/test_run_lifecycle.py`: Controller operations (create, attach,
      drive, detach, resume, terminate, list), single-driving-consumer attach
      replacement, mid-turn submit-input rejection with a diagnostic, disconnect
      semantics (cancel cleanly, deny pending approvals, cancel pending questions,
      never hang), replay brackets with `replay` flags including past user inputs, and
      increment batching that never reorders (contracts/run-lifecycle.md;
      FR-010–FR-015) — the replay and batching assertions are new here and must fail
      before T038 implements them

### Implementation for User Story 3

- [X] T035 [US3] Implement checkpoint records and the recording boundary in
      `src/loopplane/checkpoint/` — the Controller records; the loop never persists
      (FR-080, FR-084, FR-094; research R6)
- [X] T036 [US3] Implement resume, repair, and session listing in
      `src/loopplane/checkpoint/` (FR-081–FR-083, FR-085)
- [X] T037 [US3] Implement Artifact Storage — offload, metadata, replacement budget,
      retrieval — in `src/loopplane/artifacts/`, recording decisions through the
      checkpoint boundary (FR-090–FR-094; research A3)
- [X] T038 [US3] Implement Dispatcher history replay with `replay` flags, replay brackets,
      and the no-reorder batching rule in `src/loopplane/controller/dispatcher.py`
      (FR-014, FR-015)

**Checkpoint**: a killed session resumes losslessly; oversized outputs round-trip via
artifacts.

---

## Phase 6: User Story 4 — Memory and skills under a profile (P4, plan Phase F)

**Goal**: Assembly-time memory injection, declarative skills with execution profiles, and
context compaction — durable history stays verbatim.

**Independent Test**: Seed memory entries and skills, run scripted conversations, assert
prompt assembly, advertisement behavior, and profile enforcement.

### Tests for User Story 4 (write first; confirm they fail)

- [X] T039 [P] [US4] Contract tests for memory in `tests/contract/test_memory.py`: scan
      resilience, deterministic selection with fallback, write-tool semantics, verbatim
      durable history (contracts/memory.md; FR-070–FR-074)
- [X] T040 [P] [US4] Unit tests for skill loading, merge precedence, variable substitution,
      and profile enforcement in `tests/unit/test_skills.py` (FR-050–FR-055)
- [X] T041 [P] [US4] Integration tests for acceptance 4.1–4.4 plus compaction edge cases
      (no call/result split, single overflow retry, post-compaction re-establishment) in
      `tests/integration/test_us4_memory_skills.py` (FR-008, FR-053)

### Implementation for User Story 4

- [X] T042 [US4] Implement the prompt assembler — assembly-time augmentation with pristine
      durable history — in `src/loopplane/loop/assembly.py` (FR-073; plan D2)
- [X] T043 [US4] Implement Memory — store, scan, deterministic selection, injection, and the
      Gateway-governed write tool — in `src/loopplane/memory/` (FR-070–FR-074; research A5)
- [X] T044 [US4] Implement Skills — loading/validation, deterministic merge, incremental
      advertisement within budget, closed-list substitution, execution-profile enforcement
      via Gateway/approval — in `src/loopplane/skills/` (FR-050–FR-055; research A1)
- [X] T045 [US4] Implement history compaction — summary marker, never splitting a call from
      its result, exactly one overflow retry, re-establishment of needed augmentations — in
      `src/loopplane/loop/` (FR-008, FR-053; research A6)

**Checkpoint**: memory/skills runs pass; with both disabled, event sequences are identical
to Phase 5 (NFR-002).

---

## Phase 7: User Story 5 — Metadata-only observability (P5, plan Phase G)

**Goal**: An optional overlay answering "what ran, how long, what failed" while provably
exporting no content.

**Independent Test**: Identical scripted sessions with observability off and on; compare
behavior; scan exported telemetry for planted sentinels.

### Tests for User Story 5 (write first; confirm they fail)

- [X] T046 [P] [US5] Contract tests in `tests/contract/test_observability.py`: disabled ⇒
      event-sequence equality and no overhead path; enabled ⇒ nested run/turn/call spans
      with durations; sentinel content absent from all spans/metrics; error *type* only;
      policy denials excluded from execution-failure metrics (FR-100–FR-104; SC-004)

### Implementation for User Story 5

- [X] T047 [US5] Implement the observability overlay — lazy-imported optional extra,
      env-gated exporter, spans and low-cardinality metrics fed from runtime events — in
      `src/loopplane/observability/` (FR-100–FR-104; research R5)
- [X] T048 [US5] Integration test: trace shape for a tool-using run (acceptance 5.2) in
      `tests/integration/test_us5_trace.py`

**Checkpoint**: all five user stories pass independently and together.

---

## Phase 8: Polish & Cross-Cutting (plan Phase H)

- [X] T049 [P] Build the demonstration consumer — per-run summary from the public extension
      surface only — in `examples/run_summary_consumer.py` with an integration test in
      `tests/integration/test_extension_surface.py` (FR-120–FR-122; SC-009)
- [X] T050 [P] Add the gating matrix test — all optional subsystems off vs on, identical
      event sequences — in `tests/integration/test_gating_matrix.py` (SC-007)
- [X] T051 Write the embedding quickstart in `docs/quickstart.md` and validate it by
      executing its steps against the built package
- [X] T052 Run the public-safety scan over all committed files and resolve any hit
      (SC-006; constitution VII)
- [X] T053 Full-suite validation: both CI platforms green; confirm each of SC-001–SC-009
      maps to at least one passing test and record the mapping at the end of this file
- [ ] T054 Validate one real-model integration following a documented manual procedure in
      `docs/real-model-validation.md` (spec Assumptions; outside CI) — the procedure
      document is delivered; executing it requires real model credentials and remains a
      manual, human-run step

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: setup precedes everything; Phase 2 BLOCKS all user stories (the
  event vocabulary and scripted substitute are universal dependencies).
- **User stories** proceed in priority order P1 → P5; US2 builds on US1's skeletal Gateway;
  US3's replay (T038) depends on US1's Dispatcher; US4's compaction (T045) depends on US1's
  loop; US5 consumes events from all stories but only requires US1 to be meaningful.
- **Within each story**: tests first (and failing), then implementation, then the story
  checkpoint.
- **[P] tasks** touch different files and may run in parallel within their phase.

## Implementation Strategy

Deliver incrementally — US1 alone is a demonstrable MVP (loop + events + cancellation);
each later story adds value without breaking earlier ones; stop at any checkpoint and the
system is consistent and shippable as a library pre-release. Avoid big-bang integration:
every task lands with its tests on the feature branch.

## Success-Criteria Traceability (T053)

| SC | Verified by |
|---|---|
| SC-001 | `tests/integration/test_us1_plain_run.py`, `tests/integration/test_us1_tool_run.py` (single `drive` entry point, golden sequences); `tests/contract/test_run_lifecycle.py::test_attach_replays_history_bracketed_with_replay_flags` (event history alone reconstructs the conversation) |
| SC-002 | `tests/contract/test_tool_gateway.py::test_no_execution_path_outside_the_gateway` (structural audit); `tests/integration/test_us2_mcp.py` (external tools traverse the same pipeline) |
| SC-003 | `tests/integration/test_us3_resume.py` (crash/resume, repair flagged); `tests/contract/test_checkpoint.py` (records-alone rebuild, corrupt-record skip) |
| SC-004 | `tests/contract/test_observability.py::test_sentinel_content_is_absent_from_all_telemetry`, `::test_nested_run_turn_and_call_spans_with_durations`; `tests/integration/test_us5_trace.py` |
| SC-005 | `tests/contract/test_approval.py`; `tests/integration/test_us2_governance.py::test_denied_tool_never_executes_and_the_run_continues`, `::test_ask_policy_round_trip_with_session_memory` |
| SC-006 | `tests/contract/test_public_safety.py` (permanent scan over all committed files) |
| SC-007 | `tests/integration/test_gating_matrix.py` (all optional subsystems on vs core loop alone: identical sequences) |
| SC-008 | `tests/integration/test_us1_termination.py` (pre-turn, mid-stream, and dispatcher round-trip cancellations all end with a `cancelled` terminal event); `tests/contract/test_run_lifecycle.py::test_disconnect_mid_run_denies_pending_approvals_and_never_hangs` |
| SC-009 | `tests/integration/test_extension_surface.py` (stub consumer on the public surface; structural audit of internals references) |
