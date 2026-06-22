# Contract: Gemini Signature

## Content Contract

| Scenario | Expected outcome |
| -------- | ---------------- |
| Tool call has no provider signature | Serialized unsigned tool-call content remains unchanged. |
| Tool call has a provider signature | The signature round-trips as provider metadata on the tool call. |
| Tool input is inspected | The signature is absent from `input`. |
| Existing records are read | Tool calls without signature metadata remain valid. |

## Gemini Mapping Contract

| Scenario | Expected outcome |
| -------- | ---------------- |
| Gemini stream function-call part includes a non-empty signature | Decoder emits a tool-call request with the same provider signature. |
| Gemini stream function-call part has no usable signature | Decoder emits a tool-call request without provider metadata. |
| Prior Gemini tool-call block has provider signature | Request mapping emits the real signature on the function-call part. |
| Prior Gemini tool-call block has no provider signature | Request mapping emits the existing skip sentinel. |
| Multiple function calls appear in one turn | Each call keeps its own signature by call order. |

## Non-Gemini Contract

- OpenAI and Anthropic request mapping continue to use only tool name and input.
- Existing scripted model and generic model-boundary tests continue to pass for unsigned tool calls.
- No provider other than Gemini is required to emit or consume provider signatures in this unit.

## Event And Checkpoint Contract

- `SCHEMA_VERSION` remains unchanged.
- No new runtime event type is added.
- Signature-bearing tool-call content round-trips through runtime event serialization.
- Signature-bearing assistant history round-trips through checkpoint/rebuild.
- Unsigned tool-call content keeps the same public serialized shape as before.

## Tool Gateway Contract

- Gateway-facing tool calls receive the same `tool_name` and `input` values as before.
- Provider signatures are never added to tool input, tool output, permission checks, or gateway
  state.
