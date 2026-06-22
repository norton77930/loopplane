# Feature Specification: Gemini Signature

**Feature Branch**: `070-gemini-signature`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Native Gemini per-call thought_signature round-trip: add an optional
provider_signature field to ToolCallBlock with default None so non-Gemini behavior stays
byte-identical; preserve the real Gemini per-function_call thought_signature from streamed function
calls, replay it on later Gemini function_call parts, keep the signature out of tool input and Tool
Gateway ownership, and fail/skip safely when no signature is available without changing runtime
event types, termination reasons, or SCHEMA_VERSION."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Continue Gemini Tool Conversations With Real Signatures (Priority: P1)

A host using the native Gemini provider can run a tool-using conversation across multiple turns
without losing the provider's per-tool-call signature that Gemini expects to see again when prior
function calls are replayed.

**Why this priority**: This is the primary defect behind the deferred unit. Without preserving the
real provider signature, Gemini tool conversations rely on a skip sentinel instead of the provider's
own continuity metadata.

**Independent Test**: Can be tested offline by feeding a Gemini-shaped streamed function-call part
with a signature into the decoder, recording the resulting tool call in history, and mapping that
history back into a later Gemini request that echoes the same signature outside the tool arguments.

**Acceptance Scenarios**:

1. **Given** a Gemini stream emits a function call with a native signature, **When** LoopPlane
   converts it into a normalized tool-call request, **Then** the tool name, tool input, and opaque
   provider signature are all preserved.
2. **Given** a prior assistant tool call has a preserved provider signature, **When** Gemini request
   mapping rebuilds history for the next model turn, **Then** the function-call part includes that
   signature at the provider metadata position and does not place it inside tool input.

---

### User Story 2 - Preserve Existing Non-Signed Tool Behavior (Priority: P1)

Existing tool-call conversations that do not carry a Gemini signature continue to behave as they did
before this feature.

**Why this priority**: The content model is shared across all providers. The new field must not
change non-Gemini behavior, existing serialized content without signatures, or the current Gemini
fallback path when a real signature is unavailable.

**Independent Test**: Can be tested with existing OpenAI, Anthropic, scripted-model, and Gemini
mapping fixtures by asserting that a tool call without a provider signature serializes and maps the
same as before, and that Gemini still uses its existing safe fallback when no real signature exists.

**Acceptance Scenarios**:

1. **Given** a tool call has no provider signature, **When** it is serialized, checkpointed, or
   mapped through non-Gemini providers, **Then** the observable output remains unchanged.
2. **Given** Gemini history contains a prior tool call without a provider signature, **When** Gemini
   request mapping rebuilds that history, **Then** it uses the existing skip-sentinel fallback rather
   than inventing or leaking a signature.

---

### User Story 3 - Keep Provider Metadata Out Of Tool Gateway Ownership (Priority: P2)

Provider signature metadata remains model-provider continuity data, not tool input and not Tool
Gateway state.

**Why this priority**: The Tool Gateway validates and executes tool input. Provider-specific model
metadata must not be smuggled into those inputs or become a tool execution concern.

**Independent Test**: Can be tested by inspecting tool-call blocks, gateway-facing tool call
requests, runtime events, and checkpoint records to ensure signatures are represented only as
content-model metadata and never inside tool input or tool-result payloads.

**Acceptance Scenarios**:

1. **Given** a Gemini function call includes a provider signature, **When** the gateway-facing tool
   request is inspected, **Then** the tool input contains only the model-requested tool arguments.
2. **Given** a signature-bearing tool call is recorded or replayed, **When** event and checkpoint
   representations are inspected, **Then** they preserve the metadata needed for model replay
   without adding a new event type, termination reason, or schema version.

### Edge Cases

- A Gemini function-call part has no signature; the existing skip-sentinel behavior remains the
  fallback.
- A Gemini function-call part has an empty or non-string signature; it is treated as absent.
- Multiple Gemini function calls in one turn preserve each call's signature independently and in
  order.
- A signature-bearing assistant tool call is checkpointed and later rebuilt before the next Gemini
  request.
- Existing serialized tool calls without the new metadata remain readable and produce the same
  public shape as before.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST represent provider-specific tool-call continuity metadata as an optional
  field on tool-call content, absent by default.
- **FR-002**: Tool-call content without provider metadata MUST keep the same public serialized shape
  and provider behavior as before this feature.
- **FR-003**: Gemini stream decoding MUST capture a non-empty native function-call signature when
  the provider supplies one.
- **FR-004**: Gemini stream decoding MUST leave the provider signature absent when the provider does
  not supply a usable signature.
- **FR-005**: Gemini request mapping MUST replay a preserved provider signature on the corresponding
  provider function-call part.
- **FR-006**: Gemini request mapping MUST use the existing safe fallback when a prior tool call has
  no preserved provider signature.
- **FR-007**: Provider signatures MUST NOT be inserted into tool input arguments, tool result
  content, or Tool Gateway-owned state.
- **FR-008**: Non-Gemini provider mappings MUST remain unchanged for tool calls that do not carry
  provider metadata.
- **FR-009**: Runtime events and checkpoints MUST preserve signature-bearing tool-call content when
  present.
- **FR-010**: The feature MUST NOT add a runtime event type, termination reason, or
  `SCHEMA_VERSION` bump.
- **FR-011**: Diagnostics and public documentation MUST use synthetic placeholder signatures only
  and MUST NOT include real provider signatures.
- **FR-012**: The feature MUST include offline tests for Gemini decode, Gemini replay, no-signature
  fallback, non-Gemini unchanged behavior, event/checkpoint round-trip, and Tool Gateway input
  separation.

### Key Entities

- **Provider Signature**: Opaque model-provider continuity metadata attached to a tool call so the
  same provider can validate or continue multi-turn tool context later.
- **ToolCallBlock**: The normalized assistant tool-call content block that carries tool identity,
  tool input, and optional provider metadata.
- **Gemini Function Call Part**: The Gemini-native provider request/response part that carries a
  tool function call and, when available, the provider signature metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Gemini signature decode tests preserve the expected signature on the matching
  tool call.
- **SC-002**: 100% of Gemini replay tests emit the preserved signature outside tool arguments.
- **SC-003**: 100% of no-signature Gemini tests continue to emit the existing safe fallback.
- **SC-004**: Existing OpenAI, Anthropic, scripted model, runtime event, and checkpoint tests pass
  without expected-output changes for unsigned tool calls.
- **SC-005**: Public-safety scans over changed files find no real provider signatures, credentials,
  private paths, or raw provider payload dumps.

## Assumptions

- ADR 0011 pre-authorizes the narrow shared content-model change for this unit.
- The provider signature is opaque model-provider metadata; LoopPlane stores and replays it but does
  not interpret it.
- This unit covers the native Gemini adapter only. Other providers ignore absent metadata and are
  not required to support provider signatures.
- The existing Gemini skip-sentinel remains the fallback for old history and provider responses
  that do not include a usable signature.
