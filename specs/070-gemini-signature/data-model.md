# Data Model: Gemini Signature

## Provider Signature

| Field | Type | Rules |
| ----- | ---- | ----- |
| `provider_signature` | `str | None` | Optional opaque provider metadata. `None` means absent. If present, it must be a non-empty string supplied by the provider path. |

The value is not interpreted by LoopPlane. It exists only to let the same provider validate or
continue a later multi-turn tool-call context.

## ToolCallRequest

`ToolCallRequest` gains optional provider metadata so a model adapter can return a signature with a
tool-call increment before the Agent Loop records it in history.

Existing fields remain unchanged:

- `call_id`
- `tool_name`
- `input`

Rules:

- `input` remains the only gateway-facing tool argument dictionary.
- `provider_signature` is copied to history but never merged into `input`.
- A missing or unusable signature remains absent.

## ToolCallBlock

`ToolCallBlock` gains the same optional `provider_signature` field.

Rules:

- Existing unsigned tool-call serialized content must stay unchanged.
- A present signature must round-trip through runtime events and checkpoint records.
- The field is provider metadata, not tool state and not a tool result.

## Gemini Function Call Part

Gemini request/response mapping uses provider-native locations:

- Decode: read a non-empty signature from the provider function-call part when present.
- Replay: emit the preserved signature on the provider function-call part.
- Fallback: emit the existing skip sentinel when no signature is present.

## State Transitions

```text
Gemini stream emits function_call + signature
  -> Gemini decoder emits ToolCallRequest(provider_signature=...)
  -> Agent Loop records ToolCallBlock(provider_signature=...)
  -> event/checkpoint serialization preserves the tool-call block
  -> later Gemini request mapping replays the signature

Gemini stream emits function_call without signature
  -> ToolCallRequest(provider_signature=None)
  -> ToolCallBlock without observable signature metadata
  -> later Gemini request mapping uses the existing fallback
```

## Rollback

Rollback removes the optional metadata field and Gemini capture/replay behavior. Existing unsigned
tool-call content remains valid because it does not depend on the field.
