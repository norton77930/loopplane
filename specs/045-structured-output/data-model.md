# Data Model: Model-Native Structured Output

All additions are additive; none is a content block or an event.

## ModelRequest.output_schema (new optional field)

Added to the existing `loopplane.model.boundary.ModelRequest` pydantic model.

| Field | Type | Rules |
| ----- | ---- | ----- |
| `output_schema` | `dict[str, object] \| None` | Optional; default `None`. When set, a JSON schema the model's response should conform to. `None` = unconstrained (today's behavior, byte-identical). |

- Backward-compatible: existing constructions omit it; existing `stream_turn` implementations
  ignore it unless they map it.

## Structured-output capability (negotiation)

- `StructuredOutputModel` Protocol (`model/capabilities.py`): a model that defines
  `supports_structured_output() -> bool`.
- `supports_structured_output(model) -> bool`: returns the model's advertised value, else a
  conservative `False` (mirrors `accepts_media`).
- Per-adapter flag (config-backed): `openai`=True, `openrouter`=True, `ollama`=configurable
  (default False), `anthropic`=False (deferred), `gemini`=False (deferred).

## Web/API request field (edge)

- `RunRequest.output_schema` (optional, web/API layer): the host-supplied JSON schema,
  threaded into `ModelRequest.output_schema` for the run.
- Model catalog entry gains a `supports_structured_output` boolean (advertised by `/v1/models`).

## Validation rules (from FRs)

| Rule | Source |
| ---- | ------ |
| Schema optional; absent → unconstrained, byte-identical | FR-001, FR-006 |
| Supported provider + schema → provider request constrained | FR-002 |
| Per-model capability signal exposed | FR-003 |
| Non-supporting provider + schema → clear error at the web/API boundary | FR-004 |
| Output verifiable via the unit-005 JSON-schema validator | FR-005 |
| No event-schema / content-model change | FR-007 |
| Malformed schema → rejected fail-fast before any model call | FR-008 |

## State transitions

None — structured output is stateless per request (no persisted entity).
