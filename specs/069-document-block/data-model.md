# Data Model: Document Block

## DocumentBlock

| Field | Type | Rules |
| ----- | ---- | ----- |
| `kind` | literal `"document"` | Discriminator value. |
| `media` | `str` | Base64-encoded document bytes. Must be non-empty. |
| `format` | `str` | Document media type, e.g. `application/pdf`. Must be non-empty. |
| `name` | `str | None` | Optional public-safe display name. Must not be a private path or credential. |

`DocumentBlock` is a model-context content block. It is not a tool execution request, not an
artifact reference, and not extracted text.

## ContentBlock Union

`ContentBlock` gains `DocumentBlock` as an additive member alongside existing text, image, tool
call, tool result, and summary marker blocks.

Validation rules:

- Existing block kinds must continue to deserialize unchanged.
- A document block must round-trip through runtime event serialization and checkpoint records.
- Unknown block kinds remain invalid under the existing discriminated-union behavior.

## Provider Document Capability

| Capability | Meaning |
| ---------- | ------- |
| document-capable | Adapter can map `DocumentBlock` into a native provider document/media input shape. |
| unsupported | Adapter must reject document input before provider submission. |

Capability is provider-adapter behavior, not Tool Gateway behavior.

## State Transitions

```text
host supplies DocumentBlock
  -> history records user content
  -> model request preserves ordered block sequence
  -> provider adapter maps document natively
  -> provider receives document input

host supplies DocumentBlock
  -> unsupported adapter detects document block
  -> run fails safely before provider submission
```

## Rollback

Rollback removes `DocumentBlock` from exports, content union, adapter mappings, and tests. Existing
serialized content without document blocks remains valid because all other block kinds are unchanged.
