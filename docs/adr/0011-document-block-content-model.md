# ADR 0011: DocumentBlock content model

- **Status**: Accepted (2026-06-22)
- **Deciders**: LoopPlane maintainer; specs 069 and 070 roadmap batch.
- **Supersedes / superseded by**: narrows ADR 0001 D2 for document input; 070 will extend this ADR
  for provider tool-call signatures.
- **Related**: Constitution IV (Runtime Boundary Clarity), V (Tool Gateway Ownership), VI (Runtime
  Event Bus Ownership), VII (Public-Safe Documentation), X (Testable Evolution).

## Context

ADR 0001 shipped image input and explicitly deferred PDF/document input because OpenAI
chat-completions had no native base64-PDF path and because binary artifact durability was not ready.
The roadmap now authorizes the P2 document unit as a narrow additive content-model change. The
primary goal is model-context document input, not tool-output binary durability, document search,
OCR, or extraction.

The existing runtime already carries `ContentBlock` values through host input, history,
checkpoint/event serialization, prompt assembly, and provider mappings. Adding document input
therefore changes the loop-model content boundary and needs this ADR, but it does not require a new
runtime event, Tool Gateway path, or SDK/framework replacement.

## Decision

### D1 - Add a minimal `DocumentBlock`

Add `DocumentBlock(kind="document", media, format, name=None)` to the model content union. The
shape mirrors `ImageBlock`: `media` is base64 document bytes, `format` is the media type, and `name`
is optional public-safe display metadata. No private local path, credential, raw extracted text, or
storage-specific locator is part of the block.

### D2 - Keep runtime events unchanged

`DocumentBlock` is an additive member of the existing `ContentBlock` union carried by the existing
`user-input` event and checkpoint records. No new event type, termination reason, or `SCHEMA_VERSION`
bump is introduced. Tests must prove lossless event/checkpoint round-trip and preserve existing
non-document behavior.

### D3 - Provider adapters own document mapping

Document-to-provider mapping stays inside model-provider adapters:

- Anthropic maps PDF/document blocks to the native document content shape.
- Gemini maps document blocks to native inline data where the current provider path supports it.
- OpenAI chat-compatible mapping fails safely before provider submission because the current
  chat-completions path has no native document block.

Unsupported paths must not silently drop, stringify, or replace the document.

### D4 - No Tool Gateway or artifact-store binary expansion

This unit does not add document execution, retrieval, or binary handoff to the Tool Gateway. It also
does not make the artifact store binary-capable. Those are separate follow-ups for tool output and
durable binary storage. Model input can be represented directly in the content block.

### D5 - Public-safe failure

Unsupported document input and unreadable/invalid document data fail with generic public-safe
messages. Diagnostics and errors must not include raw document content, private paths, credentials,
or extracted text.

## Consequences

### Positive

- Hosts get a first-class document input shape for document-capable models.
- Event vocabulary and schema version stay stable.
- Existing text/image/tool content behavior remains unchanged.
- Unsupported providers fail explicitly instead of losing user context silently.

### Negative / trade-offs

- OpenAI chat-compatible models cannot receive documents through this path until a future
  Responses/Files API or extraction strategy is specified.
- Large durable binary artifact storage remains out of scope.
- Base64 document input increases request/event payload size; host size limits and follow-up binary
  storage remain important.

### Follow-ups

1. OpenAI Responses/Files API or a specified extraction fallback for document-capable OpenAI flows.
2. Binary artifact durability and non-text Tool Gateway oversized-output handoff.
3. Per-provider document capability advertisement beyond the minimal adapter-level checks.

## Alternatives considered

- **Keep PDF deferred**: rejected because the roadmap now explicitly authorizes the minimal
  `DocumentBlock` content-model change.
- **Route documents through the Tool Gateway**: rejected because model input is not tool execution;
  this would blur the Gateway boundary.
- **Use only references, never inline media**: rejected for this unit because existing image input
  already uses base64 media blocks and the minimal document shape can follow the same contract while
  keeping binary durability separate.
- **Silently downgrade documents to text**: rejected because it hides loss of context and would
  require extraction behavior outside the feature scope.
