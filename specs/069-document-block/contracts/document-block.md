# Contract: Document Block

## Content Contract

| Scenario | Expected outcome |
| -------- | ---------------- |
| User message contains text then document | The model request preserves text then document order. |
| User message contains multiple documents | The model request preserves all document blocks in order. |
| Existing non-document content is used | Existing behavior and serialized shape remain unchanged. |
| Document media is empty | The block is rejected by validation. |
| Document media type is empty | The block is rejected by validation. |

## Provider Mapping Contract

| Provider path | Document behavior |
| ------------- | ----------------- |
| Anthropic native mapping | Emits a native document block with the media type and base64 bytes. |
| Gemini native mapping | Emits native inline data with the media type and base64 bytes. |
| OpenAI chat-compatible mapping | Fails safely before provider submission; document is not dropped or converted. |

Unsupported-provider failures must be public-safe. They may identify that document input is
unsupported, but must not include raw document bytes, extracted text, private local paths, or
credentials.

## Event And Checkpoint Contract

- `SCHEMA_VERSION` remains unchanged.
- No new runtime event type is added.
- `user-input` remains the event that carries the document-bearing user message.
- Checkpoint/rebuild preserves document-bearing user history.

## Public API Contract

- `DocumentBlock` is exported from the model package and host seam if the host seam already exports
  content block types.
- API reference documentation must list the new public export when exposed.
