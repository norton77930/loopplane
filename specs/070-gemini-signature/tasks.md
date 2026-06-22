# Tasks: Gemini Signature

**Feature**: 070-gemini-signature | **Spec**: [spec.md](spec.md) | **Plan**:
[plan.md](plan.md) | **ADR**:
[0011](../../docs/adr/0011-document-block-content-model.md)

**Scope**: additive optional provider metadata for Gemini tool-call continuity. Preserve and replay
Gemini signatures when present; keep unsigned/non-Gemini behavior unchanged; keep metadata out of
Tool Gateway input/state; no new runtime event type, termination reason, dependency, or
`SCHEMA_VERSION` bump.

**Tests**: required. Write/verify failing focused tests before implementation.

## Phase 1: Setup & signature fixtures

**Purpose**: Create focused synthetic fixtures for provider-signature behavior.

- [X] T001 Create shared synthetic provider-signature helpers in `tests/unit/test_gemini_mapping.py` for signed function-call parts, unsigned function-call parts, and signature-bearing `ToolCallBlock` history.

---

## Phase 2: Foundational metadata path

**Purpose**: Add the optional metadata field across the model increment and content-block handoff.

- [X] T002 Add failing tests in `tests/unit/test_gemini_mapping.py` proving `ToolCallRequest` and `ToolCallBlock` can carry an optional non-empty `provider_signature` while keeping tool `input` unchanged.
- [X] T003 Add failing unsigned-shape tests in `tests/contract/test_runtime_events.py` proving tool-call content without `provider_signature` serializes with the same public shape as before.
- [X] T004 Implement optional `provider_signature` on `ToolCallRequest` in `src/loopplane/model/boundary.py` and on `ToolCallBlock` in `src/loopplane/model/content.py`, including absent-by-default validation/serialization.
- [X] T005 Copy `provider_signature` from model increments into assistant history blocks in `src/loopplane/loop/loop.py` without changing gateway-facing `input`.

**Checkpoint**: Tool-call metadata can travel from model increment to history, and unsigned content stays unchanged.

---

## Phase 3: User Story 1 - Continue Gemini Tool Conversations With Real Signatures (Priority: P1) MVP

**Goal**: Gemini captures native signatures from streamed function calls and replays preserved signatures on later request mapping.

**Independent Test**: Feed signed Gemini-shaped function-call parts into the decoder, then map signature-bearing history back to Gemini request content and verify the signature is outside tool arguments.

### Tests for User Story 1

- [X] T006 [US1] Add failing Gemini decoder tests in `tests/unit/test_gemini_mapping.py` for one signed function call and multiple signed function calls preserving independent signatures.
- [X] T007 [US1] Add failing Gemini request-mapping tests in `tests/unit/test_gemini_mapping.py` proving a preserved provider signature is emitted on the function-call part and never inside `function_call.args`.

### Implementation for User Story 1

- [X] T008 [US1] Update `src/loopplane/adapters/gemini/mapping.py` to capture non-empty `thought_signature` metadata from function-call parts into `ToolCallRequest.provider_signature`.
- [X] T009 [US1] Update `src/loopplane/adapters/gemini/mapping.py` to replay `ToolCallBlock.provider_signature` on mapped function-call parts when present.
- [X] T010 [US1] Run `uv run pytest -q tests/unit/test_gemini_mapping.py` and confirm US1 tests pass.

**Checkpoint**: Gemini signed tool calls round-trip through decode and request mapping.

---

## Phase 4: User Story 2 - Preserve Existing Non-Signed Tool Behavior (Priority: P1)

**Goal**: Existing unsigned tool calls and non-Gemini provider mappings remain unchanged.

**Independent Test**: Existing unsigned Gemini fallback tests still expect the skip sentinel; OpenAI, Anthropic, and generic model-boundary tests pass without expected-output changes.

### Tests for User Story 2

- [X] T011 [US2] Add failing/no-regression tests in `tests/unit/test_gemini_mapping.py` for missing, empty, and non-string Gemini signatures using the existing skip-sentinel fallback.
- [X] T012 [US2] Add or verify non-Gemini unchanged tests in `tests/unit/test_openai_mapping.py`, `tests/unit/test_anthropic_mapping.py`, and `tests/contract/test_model_boundary.py` for unsigned tool calls.

### Implementation for User Story 2

- [X] T013 [US2] Ensure `src/loopplane/adapters/gemini/mapping.py` uses `SKIP_THOUGHT_SIGNATURE` only when no preserved signature exists.
- [X] T014 [US2] Verify `src/loopplane/adapters/openai/mapping.py` and `src/loopplane/adapters/anthropic/mapping.py` do not emit or require provider metadata for unsigned tool calls.
- [X] T015 [US2] Run `uv run pytest -q tests/unit/test_gemini_mapping.py tests/unit/test_openai_mapping.py tests/unit/test_anthropic_mapping.py tests/contract/test_model_boundary.py` and confirm US2 tests pass.

**Checkpoint**: Existing non-signed behavior remains stable.

---

## Phase 5: User Story 3 - Keep Provider Metadata Out Of Tool Gateway Ownership (Priority: P2)

**Goal**: Provider signatures persist for model replay but never become tool input, tool output, permission state, or Tool Gateway state.

**Independent Test**: Run a scripted tool call with provider metadata through the loop and assert gateway-facing input is unchanged; event/checkpoint records preserve metadata as content only.

### Tests for User Story 3

- [X] T016 [US3] Add failing gateway-separation coverage in `tests/integration/test_us1_tool_run.py` proving `ToolCallRequest.provider_signature` is copied to assistant history but absent from the executed tool input.
- [X] T017 [US3] Add failing event/checkpoint round-trip tests in `tests/contract/test_runtime_events.py` and `tests/contract/test_checkpoint.py` for signature-bearing tool-call content.

### Implementation for User Story 3

- [X] T018 [US3] Verify `src/loopplane/gateway/gateway.py`, `src/loopplane/events/envelope.py`, and `src/loopplane/checkpoint/records.py` need no gateway/schema changes beyond the existing content union; update only if tests expose a gap.
- [X] T019 [US3] Run `uv run pytest -q tests/integration/test_us1_tool_run.py tests/contract/test_runtime_events.py tests/contract/test_checkpoint.py` and confirm US3 tests pass.

**Checkpoint**: Provider metadata is replayable content metadata, not Gateway-owned tool data.

---

## Phase 6: Polish & gates

- [X] T020 Update `docs/api-reference.md` only if public descriptions for `ToolCallRequest` or `ToolCallBlock` need to mention provider metadata.
- [X] T021 Run focused validation from `specs/070-gemini-signature/quickstart.md`.
- [X] T022 Run full gates: `uv run ruff check`, `uv run ruff format --check src tests`, `uv run mypy src`, and `uv run pytest -q`.
- [X] T023 Run board audits: `git diff --check`, `openspec/` scan, public-safety scan, and local `sensitive-scan.txt` if present.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 fixtures and blocks all user stories.
- **US1 (Phase 3)**: Depends on Phase 2 metadata fields.
- **US2 (Phase 4)**: Depends on Phase 2 and can be validated alongside US1 once mapping exists.
- **US3 (Phase 5)**: Depends on Phase 2 loop handoff and US1 metadata replay.
- **Polish (Phase 6)**: Depends on all desired stories.

### User Story Dependencies

- **US1**: MVP. Establishes Gemini capture/replay of real provider signatures.
- **US2**: Verifies the fallback and non-Gemini unchanged behavior after the metadata field exists.
- **US3**: Verifies boundary integrity for Tool Gateway, events, and checkpoints.

### Parallel Opportunities

- T003 and T017 touch separate contract test files but should be coordinated because both assert content serialization.
- T006 and T007 are in the same Gemini mapping test file; keep serial in this workspace.
- T012 non-Gemini regression checks can run in parallel with Gemini-focused implementation review.
- T020 documentation can run after the public model field behavior is finalized.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 only.
3. Validate with `uv run pytest -q tests/unit/test_gemini_mapping.py`.
4. Confirm the real provider signature appears on the provider function-call part and not in tool arguments.

### Incremental Delivery

1. Add optional metadata field and loop handoff.
2. Add Gemini capture/replay.
3. Verify unsigned fallback and non-Gemini behavior.
4. Verify Tool Gateway/event/checkpoint boundaries.
5. Run quickstart, full gates, and board audits.

## Cross-Artifact Analysis (gate)

Passed `/speckit-analyze`: no blocking cross-artifact inconsistencies.
