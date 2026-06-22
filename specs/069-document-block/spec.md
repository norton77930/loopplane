# Feature Specification: Document Block

**Feature Branch**: `069-document-block`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "DocumentBlock multimodal input for PDF and document attachments: add
a minimal additive DocumentBlock to the content model, preserve existing text/image/tool content
behavior, map native PDF/document input where providers support it, degrade safely where unsupported,
and keep binary handoff public-safe under ADR 0011 without changing runtime event schema or Tool
Gateway ownership."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Send Documents As Model Context (Priority: P1)

A host application can include a document, such as a PDF attachment, alongside text in a user
message so a capable model can answer questions using that document as part of the same turn.

**Why this priority**: This is the core value of the feature. Without a first-class document content
block, document-aware models cannot receive a document through the existing LoopPlane content
boundary.

**Independent Test**: Can be fully tested by creating a user message that contains text plus a
document block, running it through the runtime content path, and verifying the model boundary
receives both blocks without losing the document metadata or changing existing text behavior.

**Acceptance Scenarios**:

1. **Given** a host has a PDF document reference and a text prompt, **When** it submits both as one
   user message, **Then** the model request preserves the text block and the document block in order.
2. **Given** a run includes only existing text, image, tool call, or tool result content, **When** it
   is processed after this feature is enabled, **Then** those existing content types behave as they
   did before.

---

### User Story 2 - Provider-Specific Document Handling (Priority: P1)

A provider adapter that supports document input can map the document block to that provider's native
request shape, while a provider that does not support document input fails safely and clearly instead
of silently dropping or misrepresenting the document.

**Why this priority**: The same runtime content contract must work across providers without hiding
loss of context from the host or user.

**Independent Test**: Can be tested with offline adapter fixtures: one capable adapter receives a
native document request, and one unsupported adapter rejects the same document request with a
public-safe unsupported-content result before any provider call is attempted.

**Acceptance Scenarios**:

1. **Given** a provider adapter declares native document support, **When** a model request includes a
   document block, **Then** the adapter maps the document to the provider's document input without
   requiring text extraction.
2. **Given** a provider adapter does not support document input, **When** a model request includes a
   document block, **Then** the adapter fails safely with a clear unsupported-content outcome and does
   not silently omit the document.

---

### User Story 3 - Public-Safe Document References (Priority: P2)

Document content can be represented without leaking private local paths, credentials, or raw large
binary payloads through diagnostics, logs, or public documentation.

**Why this priority**: Document input often carries private information. The new content block must
respect the existing public-safe and normalized-event boundaries.

**Independent Test**: Can be tested by serializing and replaying document-bearing content and
checking that only intended document metadata and safe references are present, while raw binary data,
private paths, and credentials are absent from diagnostics and public-facing records.

**Acceptance Scenarios**:

1. **Given** a document block is recorded or replayed, **When** the normalized event/checkpoint
   representation is inspected, **Then** it carries only the public-safe document metadata/reference
   required to reconstruct the request.
2. **Given** an adapter rejects an unsupported document, **When** the diagnostic or error is emitted,
   **Then** the message is generic and does not reveal raw document content or private storage
   details.

### Edge Cases

- A document block with an unsupported media type is rejected with a clear, public-safe
  unsupported-content outcome.
- A document reference that cannot be read or resolved fails safely before the provider call.
- Empty or missing document content is rejected rather than sent as an ambiguous empty attachment.
- Multiple document blocks in one request preserve order relative to text and image blocks.
- Existing serialized content without document blocks remains readable after the new block type is
  introduced.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define a first-class `DocumentBlock` content type for document input.
- **FR-002**: A document block MUST carry enough public-safe metadata for model input decisions,
  including document media type and a safe content reference or equivalent safe payload handle.
- **FR-003**: Hosts MUST be able to include document blocks in user message content wherever existing
  user content blocks are accepted.
- **FR-004**: Model requests MUST preserve document blocks in order with adjacent text and image
  blocks.
- **FR-005**: Existing text, image, tool call, tool result, summary, and output block behavior MUST
  remain unchanged when no document block is present.
- **FR-006**: Provider adapters that support native document input MUST map document blocks to their
  native document request representation.
- **FR-007**: Provider adapters that do not support document input MUST fail safely before provider
  submission and MUST NOT silently drop, stringify, or replace the document.
- **FR-008**: Document failures and diagnostics MUST be public-safe: no private paths, credentials,
  raw binary payloads, or document text excerpts may be included in messages.
- **FR-009**: The feature MUST NOT add a new runtime event type, termination reason, or
  `SCHEMA_VERSION` bump.
- **FR-010**: The feature MUST NOT move document handling into the Tool Gateway; model-provider
  adapters own provider-specific document mapping, and the Tool Gateway remains tool-only.
- **FR-011**: The feature MUST include offline tests for content serialization, runtime request
  preservation, native provider mapping, unsupported-provider failure, and default behavior without
  documents.
- **FR-012**: Rollback MUST be possible by removing the document block and provider mappings without
  changing existing non-document content behavior.

### Key Entities

- **DocumentBlock**: A content block representing a document supplied as model context. Key
  attributes include media type, optional display name, and a public-safe content reference or safe
  payload handle.
- **Document Capability**: A provider-adapter capability indicating whether native document input is
  supported for a given provider path.
- **Document Reference**: A safe pointer or handle to document bytes that avoids leaking private
  local paths or credentials in public-facing records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of document-capable adapter tests preserve document metadata and submit a native
  document representation to the provider boundary.
- **SC-002**: 100% of unsupported-adapter tests fail before provider submission and report a
  public-safe unsupported-content outcome.
- **SC-003**: Existing non-document content tests continue to pass with no expected-output changes.
- **SC-004**: Public-safety scans over changed files find no private paths, credentials, raw document
  payloads, or document text excerpts.
- **SC-005**: Runtime event vocabulary and schema-version assertions remain unchanged.

## Assumptions

- ADR 0011 is pre-settled for the minimal additive content-model change required by units 069 and
  070.
- This unit covers document/PDF model input only; OCR, text extraction, document search, and
  summarization workflows are separate features.
- Existing file upload UX/API behavior from earlier units remains separate; this unit defines the
  runtime/model content block and provider boundary behavior.
- Provider support is adapter-specific. Capable adapters map natively; unsupported adapters fail
  safely rather than guessing a conversion.
