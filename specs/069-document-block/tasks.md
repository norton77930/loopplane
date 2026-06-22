# Tasks: Document Block

**Feature**: 069-document-block | **Spec**: [spec.md](spec.md) | **Plan**:
[plan.md](plan.md) | **ADR**:
[0011](../../docs/adr/0011-document-block-content-model.md)

**Scope**: additive `DocumentBlock` model input. Adds a minimal content-block union member,
public exports, event/checkpoint round-trip coverage, and provider-boundary mapping. No Tool
Gateway changes, no artifact-store binary durability, no OCR/text extraction, no web upload UX/API
assembly change, no runtime event type, no termination reason, and no `SCHEMA_VERSION` bump.

**Tests**: required. Write/verify failing focused tests before implementation.

## Phase 1: Setup & shared fixtures

**Purpose**: Create the focused test surface and reusable safe sample data for all stories.

- [ ] T001 Create `tests/unit/test_document_block.py` with shared helpers for base64 PDF bytes, a public-safe document name, mixed `Message` content, and JSON serialization assertions.

---

## Phase 2: Foundational content model

**Purpose**: Add the additive content-model shape that all stories depend on.

- [ ] T002 Add failing validation and discriminated-union tests in `tests/unit/test_document_block.py` for `DocumentBlock(kind="document", media, format, name=None)`, non-empty `media`, non-empty `format`, public-safe `name`, and existing text/image/tool/summary block round-trips.
- [ ] T003 Implement `DocumentBlock` in `src/loopplane/model/content.py` with non-empty `media` and `format`, public-safe optional `name`, and membership in `ContentBlock` without adding it to `OutputBlock`.
- [ ] T004 Export `DocumentBlock` from `src/loopplane/model/__init__.py` and `src/loopplane/host/__init__.py` so hosts can construct document-bearing prompts through the existing host seam.

**Checkpoint**: The content union accepts documents, while every pre-existing block kind still serializes and validates unchanged.

---

## Phase 3: User Story 1 - Send Documents As Model Context (Priority: P1) MVP

**Goal**: A host can submit text plus document content in one user message and the runtime preserves block order to the model boundary.

**Independent Test**: Construct a document-bearing prompt, serialize/deserialize it through the runtime content path, and verify text/document order reaches a `ModelRequest`.

### Tests for User Story 1

- [ ] T005 [US1] Add failing tests in `tests/unit/test_document_block.py` proving a `ModelRequest` preserves text/document/image ordering and existing non-document content behavior is unchanged.
- [ ] T006 [US1] Add a failing `UserInputEvent` document round-trip test in `tests/contract/test_runtime_events.py` asserting `SCHEMA_VERSION` and `RUNTIME_EVENT_TYPES` are unchanged.
- [ ] T007 [US1] Add a failing checkpoint/rebuild document round-trip test in `tests/contract/test_checkpoint.py` proving `UserInputRecord` preserves document-bearing user history.

### Implementation for User Story 1

- [ ] T008 [US1] Verify `src/loopplane/model/boundary.py`, `src/loopplane/events/envelope.py`, and `src/loopplane/checkpoint/records.py` carry `DocumentBlock` through the existing `ContentBlock` union without schema-version or event-vocabulary edits.
- [ ] T009 [US1] Run `uv run pytest -q tests/unit/test_document_block.py tests/contract/test_runtime_events.py tests/contract/test_checkpoint.py` and confirm US1 tests pass.

**Checkpoint**: MVP complete - document-bearing user input reaches the model/content/event/checkpoint boundaries losslessly.

---

## Phase 4: User Story 2 - Provider-Specific Document Handling (Priority: P1)

**Goal**: Native-capable adapters map documents natively; unsupported adapters fail before provider submission without dropping or converting the document.

**Independent Test**: Offline mapping fixtures show Anthropic and Gemini native request shapes, and OpenAI chat-compatible mapping raises a public-safe unsupported-content error before any client request is built.

### Tests for User Story 2

- [ ] T010 [P] [US2] Add a failing document mapping test in `tests/unit/test_anthropic_mapping.py` for Anthropic native document source output.
- [ ] T011 [P] [US2] Add a failing document mapping test in `tests/unit/test_gemini_mapping.py` for Gemini inline data output.
- [ ] T012 [P] [US2] Add failing unsupported-document tests in `tests/unit/test_openai_mapping.py` proving OpenAI chat-compatible mapping raises before provider submission and does not include raw bytes, extracted text, private paths, or credentials in the message.

### Implementation for User Story 2

- [ ] T013 [US2] Map `DocumentBlock` to Anthropic native document content in `src/loopplane/adapters/anthropic/mapping.py`.
- [ ] T014 [US2] Map `DocumentBlock` to Gemini native inline data in `src/loopplane/adapters/gemini/mapping.py`.
- [ ] T015 [US2] Add an OpenAI chat-compatible unsupported-document guard in `src/loopplane/adapters/openai/mapping.py` that raises a generic public-safe error instead of dropping, stringifying, or converting the document.
- [ ] T016 [US2] Run `uv run pytest -q tests/unit/test_anthropic_mapping.py tests/unit/test_gemini_mapping.py tests/unit/test_openai_mapping.py` and confirm US2 tests pass.

**Checkpoint**: Provider-capable paths preserve document metadata; unsupported paths fail safely before any provider request.

---

## Phase 5: User Story 3 - Public-Safe Document References (Priority: P2)

**Goal**: Document-bearing content and failures never expose private paths, credentials, raw document bytes, or extracted text through diagnostics, logs, docs, events, or checkpoints.

**Independent Test**: Serialize document-bearing content and unsupported-provider failures, then assert only intended public-safe fields are visible.

### Tests for User Story 3

- [ ] T017 [US3] Add public-safety assertions in `tests/unit/test_document_block.py` for unsafe `DocumentBlock.name` values and serialized document metadata.
- [ ] T018 [US3] Add public-safety assertions in `tests/unit/test_openai_mapping.py` that unsupported-document errors do not contain the base64 payload, document text excerpts, private path-like names, or credential-like substrings.

### Implementation for User Story 3

- [ ] T019 [US3] Harden `DocumentBlock.name` validation in `src/loopplane/model/content.py` so display names remain optional, relative, and public-safe.
- [ ] T020 [US3] Review `src/loopplane/events/emitter.py`, `src/loopplane/checkpoint/rebuild.py`, and provider mapping errors for document-specific public-safety leaks; update only if tests expose a leak.

**Checkpoint**: Document metadata is public-safe and unsupported-provider failures remain generic.

---

## Phase 6: Polish & gates

- [ ] T021 Update `docs/api-reference.md` for the new `DocumentBlock` public exports from `loopplane.model` and `loopplane.host`.
- [ ] T022 Run focused validation from `specs/069-document-block/quickstart.md`.
- [ ] T023 Run full gates: `uv run ruff check`, `uv run ruff format --check src tests`, `uv run mypy src`, and `uv run pytest -q`.
- [ ] T024 Run board audits: `git diff --check`, `openspec/` scan, public-safety scan, and local `sensitive-scan.txt` if present.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 fixtures and blocks all user stories.
- **US1 (Phase 3)**: Depends on Phase 2 content model and exports.
- **US2 (Phase 4)**: Depends on Phase 2 content model and can proceed after `DocumentBlock` exists.
- **US3 (Phase 5)**: Depends on Phase 2 validation and US2 unsupported-provider behavior.
- **Polish (Phase 6)**: Depends on all desired stories.

### User Story Dependencies

- **US1**: MVP. Establishes host/runtime/event/checkpoint preservation for document-bearing input.
- **US2**: Builds on the content block and adapter mapping surfaces; independent from checkpoint logic after Phase 2.
- **US3**: Builds on validation and unsupported-provider behavior to prove public-safety constraints.

### Parallel Opportunities

- T010, T011, and T012 are in separate mapping test files and can be authored in parallel after Phase 2.
- T013 and T014 touch separate provider mapping files and can be implemented in parallel after their tests exist.
- T006 and T007 touch separate contract test files and can be implemented in parallel after T003.
- T021 documentation can be prepared after exports are finalized.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 only.
3. Validate with `uv run pytest -q tests/unit/test_document_block.py tests/contract/test_runtime_events.py tests/contract/test_checkpoint.py`.
4. Confirm `SCHEMA_VERSION` and runtime event vocabulary are unchanged.

### Incremental Delivery

1. Add the content model and exports.
2. Add runtime/event/checkpoint preservation.
3. Add native Anthropic/Gemini mappings and OpenAI unsupported failure.
4. Add public-safety hardening.
5. Run quickstart, full gates, and board audits.

## Cross-Artifact Analysis (gate)

Pending `/speckit-analyze`.
