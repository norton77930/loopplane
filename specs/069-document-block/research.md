# Research: Document Block

## Decision: Add `DocumentBlock` as a minimal content block

**Rationale**: The existing content model already carries typed blocks across host input, history,
events, checkpoints, and provider adapters. A small block shaped like `ImageBlock` keeps the change
additive and easy to serialize. The block carries base64 media, a media type, and optional public-safe
display name; it does not carry private file paths or provider-specific handles.

**Alternatives considered**:
- Keep PDF/document input deferred: rejected because the roadmap explicitly authorizes 069.
- Store only a file reference in the block: rejected for this unit because it would require a new
  binary retrieval contract before provider mapping.
- Extract document text into `TextBlock`: rejected because OCR/extraction is out of scope and would
  silently change user context.

## Decision: Provider adapters own native mapping and unsupported failure

**Rationale**: Provider-specific request shapes belong at the model-provider adapter boundary.
Capable providers can map documents natively; unsupported providers must fail before submission so
the document is not silently dropped or misrepresented.

**Alternatives considered**:
- Enforce support inside the Agent Loop: rejected because the loop should not negotiate provider
  capabilities.
- Move document handling into the Tool Gateway: rejected because document model input is not tool
  execution.

## Decision: Anthropic and Gemini are native-capable; OpenAI chat-compatible mapping is unsupported

**Rationale**: Anthropic has a native document content shape. Gemini's current native mapping already
uses inline data for media-like input and can map document bytes the same way when supported. The
current OpenAI-compatible adapter is chat-completions-shaped, which does not have the required
document block path; fail-safe behavior is more honest than guessing a conversion.

**Alternatives considered**:
- Add OpenAI Responses/Files API now: rejected because it is a larger provider API change outside
  this unit.
- Send document bytes as text or image data to OpenAI-compatible adapters: rejected because it is
  semantically wrong and would hide loss of context.

## Decision: No event schema version bump

**Rationale**: The existing event contract carries `ContentBlock` values inside `user-input`. Adding a
discriminated union member is additive and can be tested with serialization round-trips. No event
type or payload field changes are needed.

**Alternatives considered**:
- Add a document-specific event: rejected because document input is still user input.
- Bump `SCHEMA_VERSION`: rejected because consumers already handle typed content-block unions and no
event vocabulary changes are introduced.

## Decision: No artifact-store binary durability in 069

**Rationale**: The feature's user value is model input. Durable binary artifact output and oversized
tool-output handoff are a different boundary and were explicitly deferred by ADR 0001. Keeping them
out makes this unit smaller and reversible.

**Alternatives considered**:
- Make artifact storage binary-capable first: rejected because it expands scope into tool output and
  storage semantics.
- Store documents in artifacts and put artifact references into `DocumentBlock`: rejected because it
  would couple model input to the artifact subsystem.
