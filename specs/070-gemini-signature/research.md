# Research: Gemini Signature

## Decision: Use one optional provider metadata field on tool-call shapes

**Rationale**: Gemini's signature is continuity metadata for a model-emitted tool call. The decoder
emits `ToolCallRequest` increments, and the Agent Loop later stores those as `ToolCallBlock`
history. Both shapes need the same optional metadata so the value can travel from the provider
stream into replayable history without entering tool input.

**Alternatives considered**:
- Store the signature inside tool input: rejected because the Tool Gateway validates and executes
  tool input, and provider metadata is not a tool argument.
- Keep using only the skip sentinel: rejected because the provider supplies a real signature that
  should be preserved when available.
- Add a Gemini-only side table: rejected because checkpoint/replay needs the metadata to travel with
  the content it describes.

## Decision: Preserve unsigned serialized content shape

**Rationale**: `ToolCallBlock` is part of the event/checkpoint content contract. Adding a default
field must not cause old unsigned tool calls to start serializing an explicit absent value. Tests
must assert that unsigned tool-call content keeps the prior public shape.

**Alternatives considered**:
- Serialize an explicit absent value: rejected because it would violate the byte-identical
  requirement for non-Gemini and old-history paths.
- Require migration of old records: rejected because the field can be optional and absent.

## Decision: Gemini replay uses real signature first, fallback second

**Rationale**: When a prior tool call carries a provider signature, Gemini mapping should echo it on
the provider function-call part. When no usable signature exists, the existing skip-sentinel fallback
keeps old history and unsigned calls working.

**Alternatives considered**:
- Fail when a signature is absent: rejected because existing history has no signature and already
  relies on the fallback.
- Invent a signature: rejected because provider metadata must be provider-supplied.

## Decision: No Tool Gateway change

**Rationale**: The signature is a model-provider continuity field. The Gateway should see the same
tool name and input dictionary as before, so permission checks, validation, execution, and tool
result handling remain unchanged.

**Alternatives considered**:
- Add signature parameters to gateway calls: rejected because it would blur provider metadata with
  tool execution.
- Add signature to tool result content: rejected because the signature describes the prior model
  function call, not the tool's result.

## Decision: No runtime event schema version bump

**Rationale**: Runtime events already carry content blocks inside existing event types. The change is
an additive optional content field with unchanged event vocabulary. Tests must prove both
signature-bearing content and unsigned content round-trip correctly.

**Alternatives considered**:
- Add a Gemini signature event: rejected because the metadata belongs to the tool-call content it
  annotates.
- Bump the schema version: rejected because no event vocabulary or payload envelope changes are
  introduced.
